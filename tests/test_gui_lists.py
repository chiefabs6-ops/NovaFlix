"""Screen data for TV shows and movies (Plan 4, Task 3): TMDB lists, Continue Watching, My List,
genres, search, More like this and My TorBox."""

import copy

import pytest
import xbmcaddon

from helpers import FakeNet, fixture
from resources.lib import media
from resources.lib.gui import lists
from resources.lib.kodi import paths
from resources.lib.storage import searches
from resources.lib.storage.mylist import MyList
from resources.lib.storage.watching import WatchHistory

TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"


@pytest.fixture(autouse=True)
def tmdb_key():
    xbmcaddon.settings["tmdb_token"] = TOKEN


def net():
    return (FakeNet().route("/3/genre/movie/list", fixture("tmdb/genre_movie.json"))
            .route("/3/genre/tv/list", fixture("tmdb/genre_tv.json"))
            .route("/3/trending/all/week", fixture("tmdb/trending_all_week.json"))
            .route("/3/movie/popular", fixture("tmdb/movie_popular.json"))
            .route("/3/tv/popular", fixture("tmdb/tv_popular.json"))
            .route("/3/movie/top_rated", fixture("tmdb/movie_top_rated.json"))
            .route("/3/tv/top_rated", fixture("tmdb/tv_top_rated.json"))
            .route("/3/tv/airing_today", fixture("tmdb/tv_airing_today.json"))
            .route("/3/discover/movie", fixture("tmdb/discover_movie_28.json"))
            .route("/3/search/multi", fixture("tmdb/search_multi_dune.json"))
            .route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
            .route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json"))
            .route("/3/tv/1396", fixture("tmdb/tv_1396.json"))
            .route("/3/movie/438631", fixture("tmdb/movie_438631.json"))
            .route("/3/collection/", fixture("tmdb/collection.json")))


@pytest.mark.parametrize("key,path,kind", [("trending", "tmdb/trending_all_week.json", None),
                                           ("popular_movies", "tmdb/movie_popular.json", "movie"),
                                           ("popular_tv", "tmdb/tv_popular.json", "tv"),
                                           ("top_movies", "tmdb/movie_top_rated.json", "movie"),
                                           ("top_tv", "tmdb/tv_top_rated.json", "tv"),
                                           ("airing_today", "tmdb/tv_airing_today.json", "tv")])
def test_list_pages_hold_title_cards(key, path, kind):
    net()
    raw = fixture(path)
    page = lists.load(key)
    first = raw["results"][0]
    assert page.cards[0].action == ("title", kind or first["media_type"], first["id"])
    assert page.more == (raw["page"] < raw["total_pages"]) and page.titles[0].tmdb_id == first["id"]
    assert page.title


def test_home_row_caps_at_twenty_with_view_all(monkeypatch):
    from resources.lib.metadata.library import Library
    many = [media.Title(media_type="tv", tmdb_id=i, title=f"T{i}") for i in range(1, 31)]
    monkeypatch.setattr(Library, "list", lambda self, name, page=1: (many, True))
    row = lists.home_row("popular_tv")
    assert len(row.cards) == 21 and row.cards[-1].kind == "more" and row.cards[-1].action == ("grid", "popular_tv")


def test_genres_tiles_movies_then_tv():
    net()
    page = lists.load("genres")
    movie_genres = sorted(fixture("tmdb/genre_movie.json")["genres"], key=lambda g: g["name"])
    tv_genres = sorted(fixture("tmdb/genre_tv.json")["genres"], key=lambda g: g["name"])
    assert len(page.cards) == len(movie_genres) + len(tv_genres)
    assert page.cards[0].action == ("grid", f"genre:movie:{movie_genres[0]['id']}")
    assert page.cards[0].label2 == "Movies" and page.cards[-1].label2 == "TV shows"
    genre = lists.load("genre:movie:28")
    assert genre.title == "Action · Movies" and genre.cards and genre.cards[0].action[0] == "title"


def test_search_tiles_and_results_remember_text():
    net()
    tiles = lists.load("search")
    assert [c.action[0] for c in tiles.cards[:2]] == ["search_new", "search_phone"]
    page = lists.load("search:dune")
    assert page.title == "Results for dune" and page.cards
    assert searches.recent(paths.profile_dir()) == ["dune"]
    assert lists.load("search").cards[-1].action == ("grid", "search:dune")


def test_my_list_cards_and_empty_text():
    assert lists.load("mylist").empty and not lists.load("mylist").cards
    MyList(paths.profile_dir()).add(media.title_from(fixture("tmdb/tv_1396.json"), media.TV))
    assert lists.load("mylist").cards[0].action == ("title", "tv", 1396)


def _history(started=None, watched=None):
    h = WatchHistory(paths.profile_dir())
    h.remember_title(media.title_from(fixture("tmdb/tv_1396.json"), media.TV))
    if started:
        h.save_position("tv", 1396, *started, 600, 2800)
    if watched:
        h.save_position("tv", 1396, *watched, 2790, 2800)
    return h


def test_continue_started_episode_resumes():
    _history(started=(2, 3))
    FakeNet()  # local data only
    card = lists.load("continue:local").cards[0]
    assert card.action == ("watch", "tv", 1396, 2, 3, 600) and card.label2.startswith("Resume S2 E3")


def test_continue_watched_episode_offers_next_across_season():
    net()
    _history(watched=(1, 7))
    card = lists.load("continue").cards[0]
    assert card.action == ("watch", "tv", 1396, 2, 1, 0) and card.label2 == "Next: S2 E1"


def test_continue_local_without_saved_next_opens_title_page():
    _history(watched=(1, 7))
    FakeNet()  # any network call would raise
    card = lists.load("continue:local").cards[0]
    assert card.action == ("title", "tv", 1396)


def test_continue_caught_up_and_watched_movie_are_left_out():
    tv = copy.deepcopy(fixture("tmdb/tv_1396.json"))
    tv["seasons"] = [s for s in tv["seasons"] if s["season_number"] in (0, 1, 2)]
    FakeNet().route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json")).route("/3/tv/1396", tv)
    last = len(fixture("tmdb/tv_1396_season_2.json")["episodes"])
    _history(watched=(2, last))
    h = WatchHistory(paths.profile_dir())
    h.remember_title(media.title_from(fixture("tmdb/movie_438631.json"), media.MOVIE))
    h.save_position("movie", 438631, 0, 0, 9000, 9100)
    assert lists.load("continue").cards == []


def test_more_like_this_rows():
    net()
    dune = lists.more_like_this("movie", 438631)
    collection = fixture("tmdb/collection.json")
    assert [title for title, _ in dune.rows] == [f"{collection['name']}", "More like this"]
    assert dune.rows[0][1][0].action[0] == "title"
    bb = lists.more_like_this("tv", 1396)
    assert [title for title, _ in bb.rows] == ["More like this"] and bb.title == "Breaking Bad"


def test_missing_tmdb_key_raises():
    xbmcaddon.settings["tmdb_token"] = ""
    FakeNet()
    with pytest.raises(lists.TmdbKeyMissing):
        lists.load("trending")


def test_torbox_without_key_raises():
    xbmcaddon.settings["torbox_api_key"] = ""
    with pytest.raises(lists.ServiceMissing):
        lists.load("torbox")
