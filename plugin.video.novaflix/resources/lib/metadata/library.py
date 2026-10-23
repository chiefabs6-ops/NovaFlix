"""NovaFlix's catalog facade over TMDB (Plan 2): caching, aired episodes, up next.

Views and the GUI use this, never metadata/tmdb.py directly. Failed calls are never cached,
so the next open tries again.
"""

import datetime

from resources.lib import media
from resources.lib.metadata import browse, tmdb
from resources.lib.storage.cache import Cache

HOUR, DAY = 3600, 24 * 3600
LIST_TTL = 6 * HOUR
FRESH_LIST_TTL = HOUR          # lists that change during the day
FRESH_LISTS = {"now_playing", "airing_today"}
GENRES_TTL = 7 * DAY
SEARCH_TTL = DAY
TITLE_TTL = DAY
SEASON_TTL_RUNNING = 6 * HOUR
SEASON_TTL_FINISHED = 30 * DAY
RUNNING = {"Returning Series", "In Production", "Planned", "Pilot"}
COLLECTION_TTL = 7 * DAY


def _today():
    return datetime.date.today().isoformat()


class Library:
    def __init__(self, directory=None, token=None):
        if directory is None or token is None:
            from resources.lib.kodi import paths, ui
            directory = directory or paths.profile_dir()
            token = ui.setting("tmdb_token") if token is None else token
        self._token = token
        self._cache = Cache(directory)

    @property
    def has_token(self):
        return bool((self._token or "").strip())

    # -- helpers --------------------------------------------------------------------

    def _cached(self, key, ttl, fetch, dump, load):
        cached = self._cache.get(key)
        if cached is not None:
            return load(cached)
        value = fetch()
        self._cache.set(key, dump(value), ttl)
        return value

    def _pages(self, key, ttl, fetch):
        return self._cached(key, ttl, fetch,
                            lambda r: {"titles": [t.to_dict() for t in r[0]], "more": r[1]},
                            lambda c: ([media.Title.from_dict(t) for t in c["titles"]], c["more"]))

    def _genre_map(self, media_type):
        return self._cached(f"tmdb:genres:{media_type}", GENRES_TTL, lambda: tmdb.genres(self._token, media_type),
                            lambda m: {str(k): v for k, v in m.items()},
                            lambda c: {int(k): v for k, v in c.items()})

    def _all_genres(self):
        names = self._genre_map(media.MOVIE)
        names.update(self._genre_map(media.TV))
        return names

    def _details(self, media_type, tmdb_id):
        return self._cached(f"tmdb:title:{media_type}:{int(tmdb_id)}", TITLE_TTL,
                            lambda: tmdb.details(self._token, media_type, tmdb_id),
                            lambda r: {"title": r[0].to_dict(), "more": [t.to_dict() for t in r[1]]},
                            lambda c: (media.Title.from_dict(c["title"]),
                                       [media.Title.from_dict(t) for t in c["more"]]))

    def _season(self, title, number):
        ttl = SEASON_TTL_RUNNING if title.status in RUNNING or title.status is None else SEASON_TTL_FINISHED
        return self._cached(f"tmdb:season:{title.tmdb_id}:{int(number)}", ttl,
                            lambda: tmdb.season(self._token, title.tmdb_id, number),
                            lambda eps: [e.to_dict() for e in eps],
                            lambda c: [media.Episode.from_dict(e) for e in c])

    # -- lists ------------------------------------------------------------------------

    def list(self, name, page=1):
        """(titles, more pages?) for one of tmdb.LISTS."""
        if not self._token:
            return tmdb.list_page(self._token, name, page, genre_names={})  # raises AuthError, no network
        ttl = FRESH_LIST_TTL if name in FRESH_LISTS else LIST_TTL
        return self._pages(f"tmdb:list:{name}:{int(page)}", ttl,
                           lambda: tmdb.list_page(self._token, name, page, genre_names=self._all_genres()))

    def browse(self, name, filters, page=1):
        """(titles, more pages?) for a Popular / Top rated list with sort and filter choices."""
        media_type = browse.LISTS[name][0]
        params = browse.params(name, filters)
        return self._pages(f"tmdb:browse:{name}:{browse.encode(filters)}:{int(page)}", LIST_TTL,
                           lambda: tmdb.discover_page(self._token, media_type, params, page,
                                                      genre_names=self._genre_map(media_type)))

    def genres(self, media_type):
        """[(id, name)] sorted by name."""
        return sorted(self._genre_map(media_type).items(), key=lambda item: item[1])

    def by_genre(self, media_type, genre_id, page=1):
        return self._pages(f"tmdb:genre:{media_type}:{int(genre_id)}:{int(page)}", LIST_TTL,
                           lambda: tmdb.discover(self._token, media_type, genre_id, page,
                                                 genre_names=self._genre_map(media_type)))

    def search(self, text, page=1):
        return self._pages(f"tmdb:search:{text.strip().lower()}:{int(page)}", SEARCH_TTL,
                           lambda: tmdb.search(self._token, text, page, genre_names=self._all_genres()))

    # -- one title ----------------------------------------------------------------------

    def title(self, media_type, tmdb_id):
        return self._details(media_type, tmdb_id)[0]

    def logo(self, media_type, tmdb_id):
        """The title logo image (from the same cached details as the title page), or None."""
        return self.title(media_type, tmdb_id).logo

    def cached_title(self, media_type, tmdb_id):
        """Saved details only, never the network; None if not saved."""
        cached = self._cache.get(f"tmdb:title:{media_type}:{int(tmdb_id)}")
        return media.Title.from_dict(cached["title"]) if cached else None

    def more_like_this(self, media_type, tmdb_id):
        return self._details(media_type, tmdb_id)[1]

    def collection(self, collection_id):
        return self._cached(f"tmdb:collection:{int(collection_id)}", COLLECTION_TTL,
                            lambda: tmdb.collection(self._token, collection_id),
                            lambda c: c.to_dict(), media.Collection.from_dict)

    def season_episodes(self, title, season):
        """Every episode TMDB lists for the season, aired or not (availability needs the air dates)."""
        return self._season(title, season)

    def cached_season_episodes(self, title, season):
        """Saved season only, never the network; None if not saved."""
        cached = self._cache.get(f"tmdb:season:{title.tmdb_id}:{int(season)}")
        return [media.Episode.from_dict(e) for e in cached] if cached is not None else None

    def episodes(self, title, season):
        """Episodes of a season that have aired (air date today or earlier). Undated episodes are
        listed only when the whole season is undated; next to dated ones they are announced, not aired."""
        all_episodes = self._season(title, season)
        if all(not e.air_date for e in all_episodes):
            return all_episodes
        today = _today()
        return [e for e in all_episodes if e.air_date and e.air_date <= today]

    def next_episode(self, title, season, episode):
        """(season, episode) to play after this one if it has aired, else None. Never a special (season 0).
        Gaps in TMDB's numbering are skipped; a next season may continue the numbering."""
        if title.is_movie or season < 1:
            return None
        later_here = [e.number for e in self.episodes(title, season) if e.number > episode]
        if later_here:
            return season, min(later_here)
        later = sorted(s.number for s in title.seasons if s.number > season)
        if later:
            aired = [e.number for e in self.episodes(title, later[0])]
            if aired:
                return later[0], min(aired)
        return None
