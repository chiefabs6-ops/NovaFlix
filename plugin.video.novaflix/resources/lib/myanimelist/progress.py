"""MyAnimeList progress shown in NovaFlix (M13 spec §6). Read-only and quiet: without a login,
or when MAL cannot be reached, NovaFlix shows its own history only. Local history is never changed."""

from resources.lib import errors
from resources.lib.kodi import log, paths
from resources.lib.metadata import mal
from resources.lib.myanimelist import auth, rules, sync
from resources.lib.myanimelist.api import MalApi
from resources.lib.storage.cache import Cache
from resources.lib.storage.history import History

STATUS_STRINGS = {"watching": 30070, "plan_to_watch": 30071, "completed": 30072,
                  "on_hold": 30073, "dropped": 30074}
INACTIVE = ("completed", "dropped", "on_hold")
WATCHING_TTL = 1800
FAILED_TTL = 60  # MAL down: do not make every page open wait again


def show_entry(mal_id, directory=None, network=True):
    """The owner's MAL entry for one show (cached 10 minutes), or None.
    network=False: saved entry only (callers on the GUI thread)."""
    if not mal_id:
        return None
    directory = directory or paths.profile_dir()
    store = auth.MalStore(directory)
    if not store.logged_in:
        return None
    cache = Cache(directory)
    try:
        cached = cache.get(sync.entry_key(mal_id))
        if cached is not None:
            return cached or None  # {} = a recent failure
        if not network:
            return None
        try:
            entry = MalApi(store).entry(mal_id)
        except errors.NovaFlixError as exc:
            log.warning(f"MyAnimeList entry unavailable: {type(exc).__name__}: {exc}")
            cache.set(sync.entry_key(mal_id), {}, FAILED_TTL)
            return None
        cache.set(sync.entry_key(mal_id), entry, sync.ENTRY_TTL)
        return entry
    finally:
        cache.close()


def apply(entry, kind, episode):
    """The entry as it will be once a local change reaches MAL."""
    change = rules.plan(kind, episode, entry) if entry else None
    return dict(entry, list_status=change[0], watched=change[1]) if change else entry


def merge_states(states, entry):
    """History.states() plus episodes 1..MAL count counted as watched."""
    count = int((entry or {}).get("watched") or 0)
    if not count:
        return states
    merged = dict(states)
    for number in range(1, count + 1):
        _, duration, watched = merged.get(number, (0.0, 0.0, False))
        if not watched:
            merged[number] = (0.0, duration, True)
    return merged


def mal_line(entry, text):
    """'MAL: Watching · 7/28 · ★ 8' (score only when set); '' when the show is not on the list."""
    if not entry or not entry.get("list_status"):
        return ""
    status = entry["list_status"]
    label = text(STATUS_STRINGS[status]) if status in STATUS_STRINGS else status
    parts = [text(30264) % label, f"{entry.get('watched', 0)}/{entry.get('num_episodes') or '?'}"]
    if entry.get("score"):
        parts.append(f"★ {entry['score']}")
    return " · ".join(parts)


def watching(directory=None, network=True):
    """The owner's MAL "Watching" list (cached 30 minutes); [] when logged out or unreachable."""
    directory = directory or paths.profile_dir()
    store = auth.MalStore(directory)
    if not store.logged_in:
        return []
    cache = Cache(directory)
    try:
        cached = cache.get(sync.WATCHING_KEY)
        if cached is not None:
            return [mal.MalEntry(**e) for e in cached]
        if not network:
            return []
        try:
            entries = MalApi(store).watching()
        except errors.NovaFlixError as exc:
            log.warning(f"MyAnimeList watching list unavailable: {type(exc).__name__}: {exc}")
            return []
        cache.set(sync.WATCHING_KEY, [e.__dict__ for e in entries], WATCHING_TTL)
        return entries
    finally:
        cache.close()


def merge_continue(local_rows, entries, shows):
    """One row per show, the further progress wins, newest activity first.
    A MAL-only show becomes "watched episode N" so its card offers episode N + 1."""
    rows = {r["anilist_id"]: r for r in local_rows}
    for entry in entries:
        show = shows.get(entry.mal_id)
        if not show:
            continue
        mine = rows.get(show.anilist_id)
        mal_row = {"anilist_id": show.anilist_id, "title": mine["title"] if mine else show.title,
                   "poster": mine["poster"] if mine else show.poster, "mal_id": entry.mal_id,
                   "episode": entry.watched, "position_s": 0.0, "duration_s": 0.0, "watched": True,
                   "episodes_total": show.episodes_total, "updated_at": entry.updated_at}
        if mine is None:
            rows[show.anilist_id] = mal_row
            continue
        done = mine["episode"] if mine["watched"] else mine["episode"] - 1
        latest = max(mine["updated_at"], entry.updated_at)
        if entry.watched > done:
            rows[show.anilist_id] = dict(mal_row, updated_at=latest)
        else:
            rows[show.anilist_id] = dict(mine, updated_at=latest)
    return sorted(rows.values(), key=lambda r: r["updated_at"], reverse=True)


def started(row):
    """Owner rule: a show counts as started once an episode is part-watched in NovaFlix, or at
    least 2 episodes are done. Only episode 1 done (MAL count 1) is not started yet."""
    if not row["watched"] and (row["position_s"] or 0) > 0:
        return True
    done = row["episode"] if row["watched"] else row["episode"] - 1
    return done >= 2


def inactive(row, directory=None):
    """The saved MAL entry says Completed, Dropped or On Hold (no network: GUI thread safe)."""
    entry = show_entry(row.get("mal_id"), directory, network=False)
    return bool(entry and entry.get("list_status") in INACTIVE)


def continue_rows(directory=None, network=True):
    """Continue Watching rows: NovaFlix history merged with the MAL "Watching" list.
    network=False uses saved MAL data only (Home's first paint, refresh after playback)."""
    directory = directory or paths.profile_dir()
    local = History(directory).continue_watching()
    entries = watching(directory, network)
    if not entries:
        return local
    try:
        from resources.lib.metadata.catalog import Catalog
        shows = Catalog(directory).by_mal_ids([e.mal_id for e in entries], network=network)
    except errors.NovaFlixError as exc:
        log.warning(f"MyAnimeList shows not matched to AniList: {type(exc).__name__}: {exc}")
        return local
    return merge_continue(local, entries, shows)
