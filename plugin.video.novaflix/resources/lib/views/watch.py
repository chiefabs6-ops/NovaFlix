"""Source list and playback for TMDB movies and episodes (Plan 3): plugin route `watch`.

Params: type (movie | tv), id (TMDB id), s / e (TMDB season / episode; not for movies),
resume (seconds), refresh=1 (search again instead of using saved sources).
Releases are found by IMDb id (Torrentio), only English ones are listed (sources/language.py),
the owner picks (DEC-004) and TorBox plays it through the shared resolver.
"""

from resources.lib import errors, router
from resources.lib.debrid import service
from resources.lib.debrid.resolver import Resolver
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata.library import Library
from resources.lib.models import Candidate
from resources.lib.sources import discovery, language
from resources.lib.storage.added import AddedTorrents
from resources.lib.storage.cache import Cache
from resources.lib.storage.watching import WatchHistory
from resources.lib.views import play, sources

CANDIDATE_TTL = sources.CANDIDATE_TTL


def watch_url(media_type, tmdb_id, season=None, episode=None, resume=None):
    return router.build_url("watch", type=media_type, id=tmdb_id, s=season, e=episode,
                            resume=int(resume) if resume else None)


def _cache_key(title, season, episode):
    return f"sources:t1:{title.key}:{season or 0}:{episode or 0}"


def _heading(title, season, episode):
    return title.title if title.is_movie else f"{title.title} — {ui.string(30404) % (season, episode)}"


def _discover(wanted, title, season, episode, found_settings, cache, cancelled):
    outcomes, candidates = discovery.discover(wanted, found_settings, service.client(), cancelled=cancelled)
    # Don't cache an all-failed result: next open should try again.
    if any(v in ("ok", "empty") for v in outcomes.values()):
        cache.set(_cache_key(title, season, episode),
                  {"candidates": [c.to_dict() for c in candidates], "outcomes": outcomes}, CANDIDATE_TTL)
    return outcomes, candidates


def _find(wanted, title, season, episode, found_settings, refresh):
    cache = Cache(paths.profile_dir())
    cached = None if refresh else cache.get(_cache_key(title, season, episode))
    if cached is not None:
        return [Candidate.from_dict(c) for c in cached["candidates"]], cached["outcomes"]
    progress = ui.Progress(title.title, ui.string(30146))
    try:
        outcomes, candidates = _discover(wanted, title, season, episode, found_settings, cache, progress.cancelled)
    finally:
        progress.close()
    return candidates, outcomes


def presearch(title, season, episode, cancelled=lambda: False):
    """Up next: fill the source cache for an episode without any UI, so its list opens at once.
    Runs in the service; failures are only logged."""
    try:
        if not title.imdb_id:
            return
        cache = Cache(paths.profile_dir())
        if cache.get(_cache_key(title, season, episode)) is not None:
            return
        _, found_settings, _ = sources._settings()
        _, candidates = _discover(discovery.for_title(title, season, episode), title, season, episode,
                                  found_settings, cache, cancelled)
        log.info(f"pre-searched {title.key} S{season}E{episode}: {len(candidates)} sources")
    except Exception as exc:
        log.warning(f"pre-search failed: {type(exc).__name__}: {exc}")


def choose(request):
    """Movie or episode selected: find releases, let the owner pick (DEC-004), then play."""
    if not _choose(request):
        ui.resolve_failed(request.handle)


def _number(value):
    return int(value) if value not in (None, "") else None


def _choose(request):
    params = request.params
    media_type, tmdb_id = params["type"], int(params["id"])
    season, episode = _number(params.get("s")), _number(params.get("e"))
    library = Library()
    title = library.title(media_type, tmdb_id)
    heading_base = _heading(title, season, episode)
    if not title.imdb_id:
        ui.ok(heading_base, ui.string(30405))
        return False
    episode_name = None if title.is_movie else _episode_name(library, title, season, episode)
    wanted = discovery.for_title(title, season, episode, episode_name)
    filters, found_settings, _ = sources._settings()
    candidates, outcomes = _find(wanted, title, season, episode, found_settings, params.get("refresh") == "1")
    sources._report(outcomes)
    kept, hidden = language.split(candidates, title=wanted.titles)
    if candidates and not kept:
        ui.ok(heading_base, ui.string(30406))
        return False
    history = WatchHistory(paths.profile_dir())
    last_group, last_resolution = history.last_choice(media_type, tmdb_id)
    note = ui.string(30403) % hidden if hidden else None
    return sources.pick_source(
        request, service.client(), wanted, kept, filters, False, last_group, last_resolution, heading_base,
        lambda rd, picked: _play(request, rd, library, title, season, episode, wanted, picked, heading_base), note)


def _episode_name(library, title, season, episode):
    try:
        return next((e.title for e in library.episodes(title, season) if e.number == episode), None)
    except errors.NovaFlixError:
        return None


def _play(request, rd, library, title, season, episode, wanted, candidate, heading):
    resolver = Resolver(rd, AddedTorrents(paths.profile_dir()))
    result = play.resolve_choice(resolver, candidate, wanted, heading)
    if result in (play.STOP, play.BACK):
        return result
    url, filename = result
    play.hand_off(request, resolver, {"type": title.media_type, "id": title.tmdb_id,
                                      "season": season or 0, "episode": episode or 0})
    history = WatchHistory(paths.profile_dir())
    history.remember_choice(title.media_type, title.tmdb_id, candidate)  # DEC-024
    history.remember_title(title)                                       # Continue Watching
    log.info(f"playing {title.key} S{season or 0}E{episode or 0} via {candidate.origin}")
    if title.is_movie:
        info = {"Title": title.title, "Year": title.year, "MediaType": "movie"}
    else:
        info = {"Title": _episode_name(library, title, season, episode) or filename or title.title,
                "TvShowTitle": title.title, "Season": season, "Episode": episode, "MediaType": "episode"}
    ui.resolve(request.handle, url, info, {"poster": title.poster, "thumb": title.poster, "fanart": title.backdrop})
    return play.PLAYED
