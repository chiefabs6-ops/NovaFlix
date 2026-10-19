"""Sending NovaFlix's watch changes to MyAnimeList (M13 spec §5).

Every change is first written to user.db (mal_pending: one row per show, the newest change
wins), then the service sends it: read the MAL entry, apply rules.plan, PUT status + count.
Failures stay queued and are retried every minute and after restarts. Without a MAL login
nothing is queued; with an expired one changes wait for the next login.
"""

import datetime
import threading
import time

from resources.lib import errors
from resources.lib.kodi import log, ui
from resources.lib.myanimelist import auth, rules
from resources.lib.myanimelist.api import MalApi
from resources.lib.storage import db
from resources.lib.storage.cache import Cache
from resources.lib.storage.history import History

KICK_PROPERTY = "novaflix.mal_kick"   # set by the plugin, read by the service: send now
WATCHING_KEY = "mal:me:watching"
OUTAGE_KEY = "mal:outage"
ENTRY_TTL = 600
MAX_PASSES = 3
HEADING = "MyAnimeList"

_clock = time.time
_lock = threading.Lock()


def _thread(fn):
    threading.Thread(target=fn, daemon=True).start()


_spawn = _thread


def entry_key(mal_id):
    return f"mal:entry:{int(mal_id)}"


def _run(directory, sql, args=()):
    conn = db.open_user_db(directory)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def queue(directory, mal_id, kind, episode=0):
    """Remember a change for MyAnimeList and wake the service. Never raises: a MAL problem
    must never break playback or a mark."""
    try:
        if not mal_id or not auth.MalStore(directory).linked:
            return False
        _run(directory, "INSERT OR REPLACE INTO mal_pending (mal_id, kind, episode, queued_at) VALUES (?, ?, ?, ?)",
             (int(mal_id), kind, int(episode or 0), _clock()))
        note_change(directory, int(mal_id), kind, int(episode or 0))
        ui.set_window_property(KICK_PROPERTY, "1")
        log.info(f"MyAnimeList change queued: {mal_id} {kind} {episode}")
        return True
    except Exception as exc:
        log.warning(f"MyAnimeList change not queued: {type(exc).__name__}: {exc}")
        return False


def queue_show(directory, anilist_id, kind, episode=0, mal_id=None):
    """queue() for callers that only know the AniList ID; the MAL ID comes from saved data."""
    try:
        mal_id = mal_id or History(directory).mal_id(anilist_id)
        if not mal_id:
            from resources.lib.metadata.catalog import Catalog
            show = Catalog(directory).cached_show(anilist_id)
            mal_id = show.mal_id if show else None
    except Exception as exc:
        log.warning(f"MyAnimeList change not queued: {type(exc).__name__}: {exc}")
        return False
    return queue(directory, mal_id, kind, episode)


def note_change(directory, mal_id, kind, episode):
    """Apply the change to the cached show entry at once, so pages show it before MAL answers."""
    cache = Cache(directory)
    try:
        entry = cache.get(entry_key(mal_id))
        change = rules.plan(kind, episode, entry) if entry else None
        if change:
            cache.set(entry_key(mal_id), dict(entry, list_status=change[0], watched=change[1]), ENTRY_TTL)
    finally:
        cache.close()


def pending(directory):
    return _run(directory, "SELECT mal_id, kind, episode, queued_at FROM mal_pending ORDER BY queued_at")


def has_pending(directory):
    return bool(_run(directory, "SELECT 1 FROM mal_pending LIMIT 1"))


def clear_queue(directory):
    _run(directory, "DELETE FROM mal_pending")


def start_drain(directory):
    """Send waiting changes in a background thread; at most one sender at a time."""
    if not has_pending(directory) or not _lock.acquire(blocking=False):
        return False

    def run():
        try:
            drain(directory)
        except Exception:
            log.exception("MyAnimeList sync failed")
        finally:
            _lock.release()

    _spawn(run)
    return True


def drain(directory):
    for _ in range(MAX_PASSES):  # changes queued while sending are picked up by the next pass
        rows = pending(directory)
        if not rows:
            return
        store = auth.MalStore(directory)
        if not store.logged_in:
            if store.linked:
                warn_expired(directory)
            return
        if not _send(directory, store, rows):
            return


def _send(directory, store, rows):
    """True when every row was handled; False to stop (offline or logged out)."""
    client = MalApi(store)
    cache = Cache(directory)
    try:
        for mal_id, kind, episode, queued_at in rows:
            try:
                entry = client.entry(mal_id)
                change = rules.plan(kind, episode, entry)
                if change:
                    client.update(mal_id, *change)
                    _announce(entry["title"], *change)
                log.info(f"MyAnimeList {mal_id}: {kind} {episode} -> {change or 'no change'}")
                cache.delete(OUTAGE_KEY)
            except auth.MalLoggedOut:
                warn_expired(directory)
                return False
            except (errors.NetworkError, errors.ServiceUnavailable, errors.RateLimited) as exc:
                log.warning(f"MyAnimeList unreachable: {exc}")
                _warn_outage(cache)
                return False
            except errors.HttpError as exc:
                log.warning(f"MyAnimeList refused the change for {mal_id}; dropped: {exc}")
            # Only the row that was sent: a newer change queued meanwhile stays.
            _run(directory, "DELETE FROM mal_pending WHERE mal_id = ? AND queued_at = ?", (mal_id, queued_at))
            cache.delete(entry_key(mal_id))
        cache.delete(WATCHING_KEY)
        return True
    finally:
        cache.close()


def _announce(title, status, count):
    text = ui.string(30263) % title if status == "completed" else ui.string(30262) % (title, count)
    ui.notify(HEADING, text)


def _warn_outage(cache):
    if cache.get(OUTAGE_KEY):
        return
    ui.notify(HEADING, ui.string(30280), error=True)
    cache.set(OUTAGE_KEY, True, 7 * 86400)


def warn_expired(directory):
    cache = Cache(directory)
    try:
        key = f"mal:expired:{datetime.date.fromtimestamp(_clock()).isoformat()}"
        if cache.get(key):
            return
        ui.notify(HEADING, ui.string(30276), error=True)
        cache.set(key, True, 2 * 86400)
    finally:
        cache.close()


def check_login(directory):
    """Expired login: remind once a day until the owner logs in again or logs out (spec §4.2)."""
    store = auth.MalStore(directory)
    if store.linked and not store.logged_in:
        warn_expired(directory)
