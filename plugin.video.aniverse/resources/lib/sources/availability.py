"""Can the next Continue Watching episode be watched? (Continue Watching availability)

Two steps, cheapest first:
1. AniList airing data (the cached show details) says whether the episode exists and has aired.
   A scheduled time only says when it airs, never that it can be watched.
2. For an aired episode, the configured providers are searched with the same search, filters and
   cache as the source list (views/sources.py), so playing it afterwards opens at once.

States: available (with "Dub only" on: a dubbed or dual-audio source), sub_only (Dub only on,
only sources not marked dub/dual pass the filters), upcoming (not aired; airing_at when AniList has the time), unavailable (aired,
the providers answered and nothing passes the filters), unknown (a provider failed or metadata
cannot tell), finished (past the last episode of a finished series).
"""

import threading
import time
from dataclasses import dataclass

from resources.lib import errors
from resources.lib.kodi import log, paths
from resources.lib.models import Candidate
from resources.lib.storage.cache import Cache

AVAILABLE, UPCOMING, UNAVAILABLE, UNKNOWN, FINISHED = "available", "upcoming", "unavailable", "unknown", "finished"
SUB_ONLY = "sub_only"
FAILED_TTL = 10 * 60      # all providers failed: do not search again on every Home open
SEARCHES_AT_ONCE = 2      # each search already runs its providers in parallel

_clock = time.time
_slots = threading.BoundedSemaphore(SEARCHES_AT_ONCE)


@dataclass
class Availability:
    state: str
    airing_at: int = 0  # upcoming: AniList's airing time of this episode, 0 when not known


def _failed_key(anilist_id, number):
    return f"avail_failed:{anilist_id}:{number}"


def aired(show, number, now=None):
    """True (aired), False (not aired yet), FINISHED (no such episode: past the end of a finished
    series) or None (AniList cannot tell)."""
    now = _clock() if now is None else now
    if show.episodes_total and number > show.episodes_total and show.status in ("FINISHED", "CANCELLED"):
        return FINISHED
    if show.is_movie and number != 1:
        return FINISHED
    if show.status == "NOT_YET_RELEASED":
        return False
    if show.status == "FINISHED":
        return True
    if show.next_episode:
        if number < show.next_episode:
            return True
        if number == show.next_episode:
            # Saved details can be a day old: once the time has passed it has aired.
            return bool(show.next_airing_at and now >= show.next_airing_at)
        # Further ahead. Saved schedule still in the future: certainly not aired; else unknown.
        return False if show.next_airing_at and now < show.next_airing_at else None
    return None


def _upcoming(show, number):
    return Availability(UPCOMING, (show.next_airing_at or 0) if show.next_episode == number else 0)


def _verdict(candidates, outcomes, has_aired, settings=None):
    from resources.lib.sources import ranking
    from resources.lib.views import sources
    filters, _, dub_only = settings or sources._settings()
    # Same rules as the source list: with Dub only on, only dub / dual-audio sources count.
    result = ranking.build(candidates, filters, dub_only)
    if result.shown:
        return AVAILABLE
    if dub_only and result.hidden_non_dub:
        return SUB_ONLY
    answered = any(v in ("ok", "empty") for v in outcomes.values())
    failed = any(v == "failed" for v in outcomes.values())
    if answered and not failed and has_aired:
        return UNAVAILABLE
    return UNKNOWN


def cached(anilist_id, number, directory=None):
    """The state from saved data only (GUI thread, first paint); None when a search is needed."""
    return cached_episodes(anilist_id, [number], directory).get(number)


def cached_episodes(anilist_id, numbers, directory=None):
    """{number: state} from saved data only, for the episodes that need no search (show page
    episode row). One read of the show and the cache for all of them."""
    from resources.lib.metadata.catalog import Catalog
    from resources.lib.views import sources
    directory = directory or paths.profile_dir()
    show = Catalog(directory).cached_show(anilist_id)
    if show is None:
        return {}
    cache = Cache(directory)
    try:
        out, settings = {}, sources._settings()
        for number in numbers:
            known = _saved(show, number, cache, settings)
            if known is not None:
                out[number] = known
        return out
    finally:
        cache.close()


def _saved(show, number, cache, settings):
    from resources.lib.views import sources
    has_aired = aired(show, number)
    if has_aired == FINISHED:
        return Availability(FINISHED)
    if has_aired is False:
        return _upcoming(show, number)
    found = cache.get(sources._cache_key(show, number))
    if found is not None:
        return Availability(_verdict([Candidate.from_dict(c) for c in found["candidates"]],
                                     found["outcomes"], has_aired, settings))
    if cache.get(_failed_key(show.anilist_id, number)) is not None:
        return Availability(UNKNOWN)
    return None


def check(anilist_id, number, directory=None):
    """The state, searching the providers when nothing is saved (background threads only).
    Never raises: anything unexpected is UNKNOWN."""
    try:
        return _check(anilist_id, number, directory or paths.profile_dir())
    except Exception as exc:
        log.warning(f"availability of {anilist_id} episode {number} unknown: {type(exc).__name__}: {exc}")
        return Availability(UNKNOWN)


def _check(anilist_id, number, directory):
    from resources.lib.metadata.catalog import Catalog
    from resources.lib.views import sources
    known = cached(anilist_id, number, directory)
    if known is not None:
        return known
    catalog = Catalog(directory)
    try:
        show = catalog.show(anilist_id)
    except errors.AniVerseError as exc:
        log.warning(f"availability: show {anilist_id} details unavailable: {type(exc).__name__}")
        return Availability(UNKNOWN)
    has_aired = aired(show, number)
    if has_aired == FINISHED:
        return Availability(FINISHED)
    if has_aired is False:
        return _upcoming(show, number)
    with _slots:
        known = cached(anilist_id, number, directory)  # another card may have searched it meanwhile
        if known is not None:
            return known
        cache = Cache(directory)
        try:
            _, found_settings, _ = sources._settings()
            outcomes, candidates = sources._discover(sources._wanted(show, catalog, number), found_settings,
                                                     cache, lambda: False)
            if not any(v in ("ok", "empty") for v in outcomes.values()):
                cache.set(_failed_key(anilist_id, number), True, FAILED_TTL)
        finally:
            cache.close()
    state = _verdict(candidates, outcomes, has_aired)
    log.info(f"availability of {anilist_id} episode {number}: {state} ({len(candidates)} sources)")
    return Availability(state)
