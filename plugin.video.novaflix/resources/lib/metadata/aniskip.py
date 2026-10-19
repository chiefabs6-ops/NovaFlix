"""Opening/ending times from AniSkip (DEC-041), keyed by MAL ID + episode.

AniSkip answers with the submissions closest to the length we send, but that
can still be another cut of the episode (live 2026-10-11: asked for 1400 s,
got a 1420 s submission with a different opening time). Only intervals whose
submission length is within TOLERANCE_S of the playing file are used.
Any failure means no skip button, never a playback problem.
"""

from resources.lib import errors
from resources.lib.kodi import log
from resources.lib.net import http
from resources.lib.storage.cache import Cache

URL = "https://api.aniskip.com/v2/skip-times/{mal_id}/{episode}"
TOLERANCE_S = 5.0
TTL = 30 * 24 * 3600           # architecture §9
MISS_TTL = 24 * 3600
TYPES = ("op", "ed")


def fetch(mal_id, episode, length_s):
    """[{type, start, end, length}] as AniSkip returns them; [] if none."""
    resp = http.get(URL.format(mal_id=int(mal_id), episode=int(episode)),
                    params=[("types[]", t) for t in TYPES] + [("episodeLength", int(round(length_s)))])
    data = resp.json() or {}
    out = []
    for r in data.get("results") or []:
        interval = r.get("interval") or {}
        try:
            out.append({"type": r["skipType"], "start": float(interval["startTime"]),
                        "end": float(interval["endTime"]), "length": float(r.get("episodeLength") or 0)})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def matching(intervals, duration_s, tolerance=TOLERANCE_S):
    """Intervals usable for a file of this duration, one per type."""
    out = {}
    for item in intervals:
        if item["type"] not in TYPES or item["type"] in out:
            continue
        if abs(item["length"] - duration_s) <= tolerance and 0 <= item["start"] < item["end"] <= duration_s + tolerance:
            out[item["type"]] = item
    return list(out.values())


def skip_times(directory, mal_id, episode, duration_s):
    """Cached lookup for the player monitor. Never raises."""
    if not mal_id or not duration_s:
        return []
    key = f"aniskip:{int(mal_id)}:{int(episode)}:{int(round(duration_s))}"
    try:
        cache = Cache(directory)
        try:
            intervals = cache.get(key)
            if intervals is None:
                try:
                    intervals = fetch(mal_id, episode, duration_s)
                except errors.HttpError as exc:
                    if exc.status != 404:  # 404 = nothing submitted
                        raise
                    intervals = []
                cache.set(key, intervals, TTL if intervals else MISS_TTL)
        finally:
            cache.close()
        return matching(intervals, duration_s)
    except Exception as exc:
        log.warning(f"AniSkip unavailable: {type(exc).__name__}")
        return []
