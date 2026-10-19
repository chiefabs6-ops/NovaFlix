"""Catalog facade used by views: AniList + ani.zip + dub index, with caching
(DEC-034). Views never call the raw clients."""

import datetime
import time

from resources.lib.kodi import log, paths
from resources.lib.metadata import anilist, animeschedule, anizip, dubs
from resources.lib.metadata.franchise import Franchise, walk
from resources.lib.models import Episode, RelationNode, Show
from resources.lib.storage.cache import Cache

DAY = 24 * 3600
LIST_TTL = DAY            # browse lists, search results (DEC-034)
FRESH_LIST_TTL = 3600     # airing this season, recently aired (DEC-051)
DETAILS_TTL = DAY
GENRES_TTL = 7 * DAY
EPISODES_TTL_AIRING = 6 * 3600
EPISODES_TTL_FINISHED = 30 * DAY
EPISODES_TTL_FAILED = 3600  # retry ani.zip sooner after a failure
RECENT_WINDOW = 3 * DAY
DUB_SCHEDULE_TTL = DAY     # DEC-056
DUB_SCHEDULE_TTL_FAILED = 3600
DUB_CHECK_WINDOW = 365    # days since start: finished shows older than this are not checked
DUB_HINT_MAX_DAYS = 365   # estimates further ahead are not meaningful (and pass 2038 on 32-bit Kodi)

_SEASONS = ["WINTER", "SPRING", "SUMMER", "FALL"]

_clock = time.time


def season_for(date):
    """AniList seasons: WINTER Jan-Mar, SPRING Apr-Jun, SUMMER Jul-Sep, FALL Oct-Dec."""
    return _SEASONS[(date.month - 1) // 3], date.year


def next_season(season, year):
    index = _SEASONS.index(season)
    return (_SEASONS[0], year + 1) if index == 3 else (_SEASONS[index + 1], year)


class Catalog:
    def __init__(self, directory=None):
        self._dir = directory or paths.profile_dir()
        self._cache = Cache(self._dir)
        self._dubs = None

    # -- lists ---------------------------------------------------------------

    def _page(self, key, ttl, **query):
        cached = self._cache.get(key)
        if cached is not None:
            return [Show.from_dict(s) for s in cached["shows"]], cached["more"]
        shows, more = anilist.media_page(**query)
        self._cache.set(key, {"shows": [s.to_dict() for s in shows], "more": more}, ttl)
        return shows, more

    def airing_this_season(self, page=1):
        season, year = season_for(datetime.date.fromtimestamp(_clock()))
        return self._page(f"season:{season}:{year}:{page}", FRESH_LIST_TTL,
                          page=page, season=season, season_year=year, sort=["POPULARITY_DESC"])

    def upcoming(self, page=1):
        season, year = next_season(*season_for(datetime.date.fromtimestamp(_clock())))
        return self._page(f"season:{season}:{year}:{page}", LIST_TTL,
                          page=page, season=season, season_year=year, sort=["POPULARITY_DESC"])

    def trending(self, page=1):
        return self._page(f"trending:{page}", LIST_TTL, page=page, sort=["TRENDING_DESC"])

    def popular(self, page=1):
        return self._page(f"popular:{page}", LIST_TTL, page=page, sort=["POPULARITY_DESC"])

    def by_genre(self, genre, page=1):
        return self._page(f"genre:{genre}:{page}", LIST_TTL, page=page, genre=genre, sort=["POPULARITY_DESC"])

    def search(self, text, page=1):
        # AniList matches English, romaji, native titles and synonyms server-side.
        return self._page(f"search:{text.strip().lower()}:{page}", LIST_TTL,
                          page=page, search=text.strip(), sort=["SEARCH_MATCH"])

    def genres(self):
        cached = self._cache.get("genres")
        if cached is None:
            cached = anilist.genres()
            self._cache.set("genres", cached, GENRES_TTL)
        return cached

    def recently_aired(self):
        """[(Show, episode, airing_at)] from the last 3 days, newest first."""
        key = "recent"
        cached = self._cache.get(key)
        if cached is not None:
            return [(Show.from_dict(s), ep, at) for s, ep, at in cached]
        now = int(_clock())
        items, _ = anilist.recently_aired(now - RECENT_WINDOW, now)
        self._cache.set(key, [(s.to_dict(), ep, at) for s, ep, at in items], FRESH_LIST_TTL)
        return items

    # -- one show --------------------------------------------------------------

    def show(self, anilist_id):
        key = f"show:v2:{anilist_id}"  # v2: relations carry mal_id
        cached = self._cache.get(key)
        if cached is not None:
            return Show.from_dict(cached)
        show = anilist.details(anilist_id)
        self._cache.set(key, show.to_dict(), DETAILS_TTL)
        return show

    def cached_show(self, anilist_id):
        """Saved details only, never the network (M12 Home art); None if not saved."""
        cached = self._cache.get(f"show:v2:{anilist_id}")
        return Show.from_dict(cached) if cached else None

    def franchise(self, anilist_id):
        """Whole franchise as rows (M14, DEC-062). Partial results (AniList failed mid-walk)
        are returned but not saved, so the next open tries again."""
        key = f"franchise:v1:{anilist_id}"
        cached = self._cache.get(key)
        if cached is not None:
            return Franchise.from_dict(cached)
        result = walk(anilist_id, self._relation_nodes)
        if result.partial:
            log.warning(f"franchise {anilist_id}: AniList failed mid-walk, showing what was found")
        else:
            self._cache.set(key, result.to_dict(), DETAILS_TTL)
        if result.capped:
            log.warning(f"franchise {anilist_id}: capped at {sum(len(e) for e in result.rows.values())} entries")
        return result

    def _relation_nodes(self, ids):
        found, missing = {}, []
        for node_id in ids:
            cached = self._cache.get(f"relnode:{node_id}")
            if cached is None:
                missing.append(node_id)
            else:
                found[node_id] = RelationNode.from_dict(cached)
        if missing:
            fetched = anilist.relation_nodes(missing)
            for node_id, node in fetched.items():
                self._cache.set(f"relnode:{node_id}", node.to_dict(), DETAILS_TTL)
            found.update(fetched)
        return found

    def by_mal_ids(self, mal_ids, network=True):
        """{mal_id: Show}, cached per MAL ID; unknown IDs are absent. network=False: cached mappings only."""
        found, missing = {}, []
        for mal_id in mal_ids:
            cached = self._cache.get(f"mal2show:{mal_id}")
            if cached is None:
                missing.append(mal_id)
            elif cached:
                found[mal_id] = Show.from_dict(cached)
        if missing and network:
            fetched = anilist.by_mal_ids(missing)
            for mal_id in missing:
                show = fetched.get(int(mal_id))
                # Remember misses too ({}), so they are not re-queried every time.
                self._cache.set(f"mal2show:{mal_id}", show.to_dict() if show else {}, DETAILS_TTL)
                if show:
                    found[mal_id] = show
        return found

    def _anizip(self, show):
        key = f"anizip:v2:{show.anilist_id}"  # v2: episodes carry TVDB season/episode
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        try:
            data = anizip.fetch(show.anilist_id)
        except Exception as exc:
            # DEC-046: fall back to numbers only; never fail the episode list.
            log.warning(f"ani.zip unavailable for {show.anilist_id}: {type(exc).__name__}")
            self._cache.set(key, {}, EPISODES_TTL_FAILED)
            return {}
        parsed = {
            "episodes": {str(n): e.to_dict() for n, e in anizip.episodes(data, show.anilist_id).items()},
            "mappings": anizip.mappings(data),
            "fanart": anizip.fanart(data),
        }
        ttl = EPISODES_TTL_FINISHED if show.status == "FINISHED" else EPISODES_TTL_AIRING
        self._cache.set(key, parsed, ttl)
        return parsed

    def episodes(self, show):
        """Aired episodes 1..N for this entry (DEC-013)."""
        if show.is_movie:
            return [Episode(anilist_id=show.anilist_id, number=1, title=show.title,
                            runtime_min=show.duration_min, overview=show.description)]
        details = {int(k): Episode.from_dict(v) for k, v in self._anizip(show).get("episodes", {}).items()}
        count = show.aired_episodes
        if count is None:
            today = datetime.date.fromtimestamp(_clock()).isoformat()
            aired = [n for n, e in details.items() if e.air_date and e.air_date <= today]
            count = max(aired) if aired else (show.episodes_total or 0)
        return [details.get(n) or Episode(anilist_id=show.anilist_id, number=n) for n in range(1, count + 1)]

    def fanart(self, show):
        return show.banner or self._anizip(show).get("fanart")

    def mappings(self, show):
        return self._anizip(show).get("mappings", {})

    def dub_status(self, show):
        """Works for Show and ShowRef (both carry mal_id)."""
        if self._dubs is None:
            self._dubs = dubs.DubIndex(self._dir)
        return self._dubs.status(show.mal_id)

    def dub_estimates(self, show, numbers):
        """{episode number: estimated dub release timestamp} for episodes not yet
        dubbed (DEC-056). Any failure means no hints, never an error."""
        if not show.mal_id or show.is_movie or not self._may_have_pending_dub(show):
            return {}
        key = f"dubschedule:{show.mal_id}"
        schedule = self._cache.get(key)
        if schedule is None:
            try:
                entry = animeschedule.fetch(show.mal_id)
                schedule = (animeschedule.dub_schedule(entry) if entry else None) or {}
                self._cache.set(key, schedule, DUB_SCHEDULE_TTL)
            except Exception as exc:
                log.warning(f"AnimeSchedule unavailable for MAL {show.mal_id}: {type(exc).__name__}")
                self._cache.set(key, {}, DUB_SCHEDULE_TTL_FAILED)
                return {}
        if not schedule:
            return {}
        now = _clock()
        premiere = datetime.datetime.fromisoformat(schedule["premier"]).timestamp()
        if now - premiere > DUB_CHECK_WINDOW * DAY:
            return {}  # long-running dub: its pace is not weekly from the premiere
        horizon = now + DUB_HINT_MAX_DAYS * DAY
        out = {}
        for number, date in animeschedule.estimates(schedule, numbers).items():
            if now < date.timestamp() <= horizon:
                out[number] = date.timestamp()
        return out

    @staticmethod
    def _may_have_pending_dub(show):
        if show.status in ("RELEASING", "HIATUS"):
            return True
        try:
            started = datetime.date.fromisoformat(show.start_date or "")
        except ValueError:
            return False
        return (datetime.date.fromtimestamp(_clock()) - started).days <= DUB_CHECK_WINDOW
