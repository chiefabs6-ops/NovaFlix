"""Can a title's next episode (or a movie) be watched? Continue Watching and the title page.

Cheapest first:
1. TMDB air dates (saved title and season): an episode that has not aired is "upcoming".
2. The saved source list of the watch route (views/watch.py): same search, filters and language rule,
   so playing it afterwards opens at once.
3. Otherwise the providers are searched in the background and the result is saved.

States (the skins' "avail" values): available (an English release passes the filters), sub_only (only
releases in another language: "No English audio", still playable), upcoming (not aired; air_date when
TMDB has it), unavailable (aired, the providers answered, nothing passes), unknown (a provider or TMDB
failed). Movies use season 0, episode 0.
"""

import threading
from dataclasses import dataclass

from resources.lib import errors, media
from resources.lib.kodi import log, paths
from resources.lib.metadata import library as library_mod
from resources.lib.metadata.library import Library
from resources.lib.models import Candidate
from resources.lib.sources import discovery, language, ranking
from resources.lib.storage.cache import Cache

AVAILABLE, NO_ENGLISH, UPCOMING, UNAVAILABLE, UNKNOWN = "available", "sub_only", "upcoming", "unavailable", "unknown"
FAILED_TTL = 10 * 60      # all providers failed: do not search again on every Home open
SEARCHES_AT_ONCE = 2      # each search already runs its providers in parallel

_slots = threading.BoundedSemaphore(SEARCHES_AT_ONCE)


@dataclass
class Availability:
    state: str
    air_date: str = ""  # upcoming: TMDB "YYYY-MM-DD" when known


def _failed_key(media_type, tmdb_id, season, episode):
    return f"avail_failed:{media_type}:{tmdb_id}:{season}:{episode}"


def aired(air_date, today):
    """True (aired), False (air date in the future) or None (no date)."""
    if not air_date:
        return None
    return air_date <= today


def _episode(episodes, number):
    return next((e for e in episodes or [] if e.number == number), None)


def _titles(title, episode):
    return [title.title] + ([episode.title] if episode is not None and episode.title else [])


def _filters():
    from resources.lib.views import sources
    return sources._settings()[0]


def _verdict(candidates, outcomes, titles, filters):
    kept, _ = language.split(candidates, title=titles)
    if ranking.build(kept, filters, False, titles=titles).shown:
        return AVAILABLE
    if not kept and ranking.build(candidates, filters, False, titles=titles).shown:
        return NO_ENGLISH  # the source list shows these with "No English audio"
    answered = any(v in ("ok", "empty") for v in outcomes.values())
    failed = any(v == "failed" for v in outcomes.values())
    return UNAVAILABLE if answered and not failed else UNKNOWN


def _air_state(title, season_episodes, episode):
    """Availability(UPCOMING) when not aired yet, else None (aired or unknown date: search)."""
    if title.is_movie:
        date = title.date
    else:
        found = _episode(season_episodes, episode)
        date = found.air_date if found else None
    if aired(date, library_mod._today()) is False:
        return Availability(UPCOMING, date)
    return None


def _saved(title, season_episodes, season, episode, cache, filters):
    from resources.lib.views import watch
    upcoming = _air_state(title, season_episodes, episode)
    if upcoming:
        return upcoming
    found = cache.get(watch._cache_key(title, season or None, episode or None))
    if found is not None:
        titles = _titles(title, _episode(season_episodes, episode))
        return Availability(_verdict([Candidate.from_dict(c) for c in found["candidates"]], found["outcomes"], titles,
                                     filters))
    if cache.get(_failed_key(title.media_type, title.tmdb_id, season, episode)) is not None:
        return Availability(UNKNOWN)
    return None


def cached(media_type, tmdb_id, season, episode, directory=None):
    """The state from saved data only; None when a search is needed."""
    return cached_episodes(media_type, tmdb_id, season, [episode], directory).get(episode)


def cached_episodes(media_type, tmdb_id, season, numbers, directory=None):
    """{episode: Availability} from saved data only, for the episodes that need no search. A failing read
    (locked cache.db, an old saved format) means no saved results, never an error for the screen."""
    try:
        return _cached_episodes(media_type, tmdb_id, season, numbers, directory or paths.profile_dir())
    except Exception as exc:
        log.warning(f"saved availability of {media_type}:{tmdb_id} unreadable: {type(exc).__name__}: {exc}")
        return {}


def _cached_episodes(media_type, tmdb_id, season, numbers, directory):
    lib = Library(directory, token="")  # saved data only: never the network
    title = lib.cached_title(media_type, tmdb_id)
    if title is None:
        return {}
    season_episodes = None if title.is_movie else lib.cached_season_episodes(title, season)
    if not title.is_movie and season_episodes is None:
        return {}
    cache = Cache(directory)
    try:
        out, filters = {}, _filters()  # settings read once for the whole season
        for number in numbers:
            known = _saved(title, season_episodes, season, number, cache, filters)
            if known is not None:
                out[number] = known
        return out
    finally:
        cache.close()


def check(media_type, tmdb_id, season, episode, directory=None):
    """The state, searching the providers when nothing is saved (background threads only).
    Never raises: anything unexpected is UNKNOWN."""
    try:
        return _check(media_type, int(tmdb_id), int(season or 0), int(episode or 0), directory or paths.profile_dir())
    except Exception as exc:
        log.warning(f"availability of {media_type}:{tmdb_id} S{season}E{episode} unknown: {type(exc).__name__}: {exc}")
        return Availability(UNKNOWN)


def _check(media_type, tmdb_id, season, episode, directory):
    from resources.lib.views import sources, watch
    known = cached(media_type, tmdb_id, season, episode, directory)
    if known is not None:
        return known
    lib = Library(directory)
    try:
        title = lib.title(media_type, tmdb_id)
        season_episodes = None if title.is_movie else lib.season_episodes(title, season)
    except errors.NovaFlixError as exc:
        log.warning(f"availability: {media_type}:{tmdb_id} details unavailable: {type(exc).__name__}")
        return Availability(UNKNOWN)
    upcoming = _air_state(title, season_episodes, episode)
    if upcoming:
        return upcoming
    if not title.imdb_id:
        return Availability(UNAVAILABLE)  # the watch route cannot search it either (string 30405)
    found = _episode(season_episodes, episode)
    with _slots:
        known = cached(media_type, tmdb_id, season, episode, directory)  # another card may have searched it meanwhile
        if known is not None:
            return known
        cache = Cache(directory)
        try:
            _, found_settings = sources._settings()
            s, e = (None, None) if title.is_movie else (season, episode)
            wanted = discovery.for_title(title, s, e, found.title if found else None)
            outcomes, candidates = watch.discover_and_save(wanted, title, s, e, found_settings, cache, lambda: False)
            if not any(v in ("ok", "empty") for v in outcomes.values()):
                cache.set(_failed_key(media_type, tmdb_id, season, episode), True, FAILED_TTL)
        finally:
            cache.close()
    state = _verdict(candidates, outcomes, _titles(title, found), _filters())
    log.info(f"availability of {media_type}:{tmdb_id} S{season}E{episode}: {state} ({len(candidates)} sources)")
    return Availability(state)
