"""Playing the owner's chosen source (DEC-004, DEC-019, DEC-020, DEC-024).

Outcomes returned to the source list:
  PLAYED  -> Kodi has the stream URL
  BACK    -> show the source list again (bad source, declined download)
  STOP    -> owner cancelled; leave the list
"""

import json
import time

from resources.lib.debrid.resolver import AmbiguousFile, BadSource, NotReady, Resolver
from resources.lib.debrid import service
from resources.lib.kodi import log, paths, ui
from resources.lib.playback.monitor import HANDOFF_PROPERTY
from resources.lib.storage import db
from resources.lib.storage.added import AddedTorrents
from resources.lib.storage.history import History

PLAYED, BACK, STOP = "played", "back", "stop"
POLL_S = 5                 # ~12 RD calls a minute while downloading (limit 250/min)
STALL_S = 10 * 60          # Q15b: ask after 10 minutes without progress

_clock = time.monotonic


def _speed(n):
    if not n:
        return None
    return f"{n / 1e6:.1f} MB/s" if n >= 1e6 else f"{n / 1e3:.0f} KB/s"


def download_and_wait(resolver, torrent_id, candidate, wanted, heading, wait=None):
    """Modal progress until downloaded (Q15c). Returns (url, filename) or an outcome."""
    progress = ui.Progress(heading, ui.string(30180) % service.label())
    wait = wait or progress.wait
    last_percent, last_change = -1, _clock()
    try:
        while True:
            status, percent, speed, seeders, info = resolver.progress(torrent_id)
            if status == "downloaded":
                return resolver.finish(torrent_id, candidate, wanted, info)
            if percent != last_percent:
                last_percent, last_change = percent, _clock()
            parts = [ui.string(30181) % percent, _speed(speed),
                     (ui.string(30182) % seeders) if seeders is not None else None]
            progress.update(int(percent), " · ".join(p for p in parts if p))
            if _clock() - last_change > STALL_S:
                choice = ui.select(ui.string(30183), [ui.string(30184), ui.string(30185) % service.label(), ui.string(30186)])
                if choice == 0:
                    last_change = _clock()
                elif choice == 1:
                    resolver.keep(torrent_id)
                    return STOP
                else:
                    resolver.remove(torrent_id)
                    return BACK
            if wait(POLL_S):
                # Q15a: ask each time whether to keep the download.
                if ui.confirm(heading, ui.string(30187) % (service.label(), service.label())):
                    resolver.keep(torrent_id)
                    ui.notify(service.label(), ui.string(30188) % (service.label(), service.label()))
                else:
                    resolver.remove(torrent_id)
                return STOP
    finally:
        progress.close()


def mark_blocked(info_hash):
    """Remember a refusal so the list hides it (same cache as the pre-check, DEC-053)."""
    from resources.lib.sources import precheck
    from resources.lib.storage.cache import Cache
    Cache(paths.profile_dir()).set(precheck.cache_key(info_hash), precheck.BLOCKED, precheck.TTL[precheck.BLOCKED])


def remember_choice(anilist_id, number, candidate):
    """DEC-024: next episode pins the same release group + resolution."""
    conn = db.open_user_db(paths.profile_dir())
    try:
        conn.execute(
            "INSERT INTO show_prefs (anilist_id, last_release_group, last_resolution, last_episode_played, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(anilist_id) DO UPDATE SET last_release_group = excluded.last_release_group, "
            "last_resolution = excluded.last_resolution, last_episode_played = excluded.last_episode_played, "
            "updated_at = excluded.updated_at",
            (int(anilist_id), candidate.release_group, candidate.resolution, number, time.time()))
    finally:
        conn.close()


def play_candidate(request, rd, show, wanted, candidate, heading):
    resolver = Resolver(rd, AddedTorrents(paths.profile_dir()))
    chosen_file, torrent_id = None, None
    while True:
        try:
            url, filename = resolver.resolve(candidate, wanted, chosen_file, torrent_id)
            break
        except AmbiguousFile as exc:
            index = ui.select(ui.string(30189), [path for _, path in exc.files])
            if index < 0:
                resolver.remove(exc.torrent_id)
                return BACK
            chosen_file, torrent_id = exc.files[index][0], exc.torrent_id
        except NotReady as exc:
            if not ui.confirm(heading, ui.string(30190) % service.label()):
                resolver.remove(exc.torrent_id)
                return BACK
            result = download_and_wait(resolver, exc.torrent_id, candidate, wanted, heading)
            if result in (STOP, BACK):
                return result
            url, filename = result
            break
        except BadSource as exc:
            log.info(f"source not playable: {exc}")
            if "blocked" in str(exc) and candidate.info_hash:
                mark_blocked(candidate.info_hash)
            ui.ok(heading, ui.string(30191) % str(exc))
            return BACK

    added = AddedTorrents(paths.profile_dir())
    ours = resolver.torrent_id
    handoff = {"anilist_id": show.anilist_id, "episode": wanted.number, "mal_id": show.mal_id}
    resume = int(request.params.get("resume") or 0)
    if resume > 0:
        handoff["resume_s"] = resume  # M12 screens: AniVerse asks about resuming, the service seeks
    if ours and added.is_ours(ours) and not added.is_kept(ours):
        handoff["cleanup_torrent"] = str(ours)
    ui.set_window_property(HANDOFF_PROPERTY, json.dumps(handoff))  # IDs only (SEC-15)
    remember_choice(show.anilist_id, wanted.number, candidate)
    History(paths.profile_dir()).remember_show(show)  # Continue Watching (DEC-029)
    log.info(f"playing {show.anilist_id} ep {wanted.number} via {candidate.origin}")
    ui.resolve(request.handle, url, {
        "Title": filename or show.title,
        "TvShowTitle": None if show.is_movie else show.title,
        "Episode": None if show.is_movie else wanted.number,
        "MediaType": "movie" if show.is_movie else "episode",
    }, {"poster": show.poster, "thumb": show.poster, "fanart": show.banner})
    return PLAYED


def play_account_file(request, rd, torrent_id, file_id):
    """My Real-Debrid file: already downloaded, owner-added -> never removed."""
    from resources.lib.models import Candidate
    candidate = Candidate(origin="rdcloud", release_name="", rd_torrent_id=torrent_id, rd_file_id=int(file_id))
    resolver = Resolver(rd, AddedTorrents(paths.profile_dir()))
    try:
        url, filename = resolver.resolve(candidate, None)
    except BadSource as exc:
        ui.ok(service.label(), ui.string(30191) % str(exc))
        ui.resolve_failed(request.handle)
        return
    ui.resolve(request.handle, url, {"Title": filename, "MediaType": "video"}, {})
