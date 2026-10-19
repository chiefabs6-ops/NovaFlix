"""Pre-check sources with Real-Debrid before listing them (DEC-053).

For each torrent source, in list order, until `needed` playable ones are found:
add the magnet, wait briefly for the file list, select the episode file, read
the status, then delete the torrent again (only if this check created it).
Results are cached so reopening an episode costs almost nothing.
"""

import threading
import time

from resources.lib import errors
from resources.lib.debrid import resolver
from resources.lib.kodi import log

BLOCKED, READY, DOWNLOAD, UNKNOWN = "blocked", "ready", "download", "unknown"
PLAYABLE = (READY, DOWNLOAD)
TTL = {BLOCKED: 30 * 24 * 3600, READY: 3600, DOWNLOAD: 3600}
FILE_LIST_WAIT_S = 5
CONCURRENCY = 4

_sleep = time.sleep
_clock = time.monotonic


def cache_key(info_hash):
    return f"rd_check:{info_hash}"


def cached_status(cache, candidate):
    if candidate.origin == "rdcloud":
        return READY
    return cache.get(cache_key(candidate.info_hash)) if candidate.info_hash else None


def _check_one(rd, candidate, wanted, existing_hashes):
    """One torrent: returns a status. Never leaves a torrent it created behind."""
    if candidate.info_hash in existing_hashes:
        return READY if existing_hashes[candidate.info_hash] == "downloaded" else DOWNLOAD
    torrent_id = None
    try:
        try:
            torrent_id = rd.add_magnet(f"magnet:?xt=urn:btih:{candidate.info_hash}")
        except errors.HttpError as exc:
            if resolver._blocked(exc):
                return BLOCKED
            raise
        deadline = _clock() + FILE_LIST_WAIT_S
        while True:
            info = rd.torrent_info(torrent_id)
            status = info.get("status")
            if status in resolver.BROKEN:
                return BLOCKED if status == "virus" else UNKNOWN
            if status != "magnet_conversion":
                break
            if _clock() > deadline:
                return UNKNOWN
            _sleep(1)
        if status == "waiting_files_selection":
            try:
                file_id = resolver.pick_file(info.get("files") or [], candidate, wanted)
            except resolver.AmbiguousFile:
                file_id = "all"
            except resolver.BadSource:
                return UNKNOWN
            try:
                rd.select_files(torrent_id, file_id if file_id == "all" else [file_id])
            except errors.HttpError as exc:
                if resolver._blocked(exc):
                    return BLOCKED
                raise
            status = rd.torrent_info(torrent_id).get("status")
        if status == resolver.READY:
            return READY
        if status in resolver.IN_PROGRESS:
            return DOWNLOAD
        return UNKNOWN
    finally:
        if torrent_id:
            try:
                rd.delete_torrent(torrent_id)
            except errors.AniVerseError as exc:
                log.warning(f"pre-check cleanup failed: {exc}")


def run_cache_lookup(client, candidates, wanted, cache):
    """TorBox: one free checkcached call for every source; nothing is added (DEC-054)."""
    hashes = [c.info_hash for c in candidates if c.origin != "rdcloud" and c.info_hash
              and cached_status(cache, c) is None]
    if not hashes:
        return {}
    try:
        cached = client.cached(hashes)
    except errors.AniVerseError as exc:
        log.warning(f"cache lookup failed: {exc}")
        return {}
    results = {h: (READY if h in cached else DOWNLOAD) for h in hashes}
    for h, status in results.items():
        cache.set(cache_key(h), status, TTL[status])
    log.info(f"cache lookup: {len(hashes)} checked, {sum(s == READY for s in results.values())} cached")
    return results


def run(rd, candidates, wanted, cache, needed=2, cancelled=lambda: False, on_progress=lambda done, ok: None):
    """{info_hash: status} for the candidates checked. Stops at `needed` playable."""
    if hasattr(rd, "cached"):
        return run_cache_lookup(rd, candidates, wanted, cache)
    results = {}
    playable = sum(1 for c in candidates if cached_status(cache, c) in PLAYABLE)
    queue = [c for c in candidates if c.origin != "rdcloud" and c.info_hash and cached_status(cache, c) is None]
    if playable >= needed or not queue:
        return results
    try:
        existing = {(t.get("hash") or "").lower(): t.get("status") for t in rd.torrents()}
    except errors.AniVerseError as exc:
        log.warning(f"pre-check skipped: {exc}")
        return results

    lock = threading.Lock()
    state = {"playable": playable, "done": 0, "stop": False}

    def worker():
        while True:
            with lock:
                if state["stop"] or not queue or state["playable"] >= needed or cancelled():
                    return
                candidate = queue.pop(0)
            try:
                status = _check_one(rd, candidate, wanted, existing)
            except errors.RateLimited:
                with lock:
                    state["stop"] = True  # Real-Debrid asked to slow down: stop checking
                return
            except errors.AniVerseError as exc:
                log.warning(f"pre-check failed for one source: {exc}")
                status = UNKNOWN
            with lock:
                results[candidate.info_hash] = status
                state["done"] += 1
                if status in PLAYABLE:
                    state["playable"] += 1
                on_progress(state["done"], state["playable"])

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(CONCURRENCY)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # SQLite connections belong to the thread that opened them: write here.
    for info_hash, status in results.items():
        if status in TTL:
            cache.set(cache_key(info_hash), status, TTL[status])
    blocked = sum(1 for s in results.values() if s == BLOCKED)
    log.info(f"pre-check: {len(results)} checked, {state['playable']} playable, {blocked} blocked")
    return results
