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
    titles = [c for c in page.cards if c.action[0] == "title"]
    assert titles[0].action == ("title", kind or first["media_type"], first["id"])
    assert page.more == (raw["page"] < raw["total_pages"]) and page.titles[0].tmdb_id == first["id"]
    assert page.title


def test_home_row_caps_at_twenty_with_view_all(monkeypatch):
    from resources.lib.metadata.library import Library
    many = [media.Title(media_type="tv", tmdb_id=i, title=f"T{i}") for i in range(1, 31)]
    monkeypatch.setattr(Library, "list", lambda self, name, page=1: (many, True))
    row = lists.home_row("popular_tv")
    assert len(row.cards) == 21 and row.cards[-1].kind == "more" and row.cards[-1].action == ("grid", "popular_tv")


def test_genres_page_per_media_type():
    net()
    movie_genres = sorted(fixture("tmdb/genre_movie.json")["genres"], key=lambda g: g["name"])
    tv_genres = sorted(fixture("tmdb/genre_tv.json")["genres"], key=lambda g: g["name"])
    films, shows = lists.load("genres"), lists.load("genres:tv")
    assert len(films.cards) == len(movie_genres) and len(shows.cards) == len(tv_genres)
    assert films.cards[0].action == ("grid", f"genre:movie:{movie_genres[0]['id']}")
    assert shows.cards[0].action == ("grid", f"genre:tv:{tv_genres[0]['id']}")
    assert lists.load("genres:movie").cards[0].action == films.cards[0].action
    assert {c.kind for c in films.cards} == {"genre"}
    genre = lists.load("genre:movie:28")
    assert genre.title == "Action · Movies" and genre.cards and genre.cards[0].action[0] == "title"


class _Shelf:
    def __init__(self, fail=()):
        self.fail = fail

    def by_genre(self, media_type, genre_id, page=1):
        if genre_id in self.fail:
            raise OSError("offline")
        return [media.Title(media_type=media_type, tmdb_id=1, title="No art"),
                media.Title(media_type=media_type, tmdb_id=2, title="Art", backdrop=f"b{genre_id}.jpg")], False


def test_genre_pictures_map_first_backdrop(monkeypatch):
    monkeypatch.setattr(lists, "_library", lambda: _Shelf())
    tiles = [lists.cards.Card(label="Action", kind="genre", action=("grid", "genre:movie:28")),
             lists.cards.Card(label="Drama", kind="genre", action=("grid", "genre:movie:18"))]
    assert lists.genre_pictures(tiles) == {0: "b28.jpg", 1: "b18.jpg"}


def test_genre_pictures_failure_keeps_tiles(monkeypatch):
    monkeypatch.setattr(lists, "_library", lambda: _Shelf(fail=(28,)))
    tiles = [lists.cards.Card(label="Action", kind="genre", action=("grid", "genre:movie:28")),
             lists.cards.Card(label="Drama", kind="genre", action=("grid", "genre:tv:18"))]
    assert lists.genre_pictures(tiles) == {1: "b18.jpg"}


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
    assert card.action == ("watch", "tv", 1396, 2, 1, 0) and card.label2 == "S2 E1 · Checking..."
    assert (card.avail, card.check) == ("checking", ("tv", 1396, 2, 1))


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



# -- availability (availability plan, Task 3) ------------------------------------------------------------

def test_continue_started_episode_is_available_at_once():
    _history(started=(2, 3))
    FakeNet()
    assert lists.load("continue:local").cards[0].avail == "available"


def test_continue_running_show_shows_next_air_date():
    raw = fixture("tmdb/tv_456.json")
    last, nxt = raw["last_episode_to_air"], raw["next_episode_to_air"]
    season = fixture(f"tmdb/tv_456_season_{last['season_number']}.json")
    FakeNet().route(f"/3/tv/456/season/{last['season_number']}", season).route("/3/tv/456", raw)
    h = WatchHistory(paths.profile_dir())
    h.remember_title(media.title_from(raw, media.TV))
    h.save_position("tv", 456, last["season_number"], last["episode_number"], 1300, 1320)
    card = lists.load("continue").cards[0]
    assert card.avail == "upcoming" and card.action == ("title", "tv", 456)
    assert card.label2.startswith(f"S{nxt['season_number']} E{nxt['episode_number']} · Airs ")


def test_continue_uses_saved_availability(monkeypatch):
    from resources.lib.sources import availability as av
    monkeypatch.setattr(av, "cached", lambda m, i, s, e, directory=None: av.Availability(av.AVAILABLE))
    net()
    _history(watched=(1, 7))
    card = lists.load("continue").cards[0]
    assert card.avail == "available" and card.label2 == "S2 E1 · Available"


def test_popular_list_starts_with_filter_and_sort():
    n = net()
    page = lists.load("popular_movies")
    tile = page.cards[0]
    assert tile.kind == "tile" and tile.label == "Filter & sort" and tile.action == ("filter", "popular_movies", "")
    assert tile.label2 == "Sort, genre, year, rating"
    assert any("/3/movie/popular" in url for _, url, _ in n.calls)
    assert not lists.load("popular_movies", 2).cards[0].kind == "tile"  # first page only


def test_filtered_list_comes_from_discover():
    n = net()
    page = lists.load("popular_movies:sort=newest;genre=28;year=2020s;rating=7")
    url = next(url for _, url, _ in n.calls if "/3/discover/movie" in url)
    for part in ("sort_by=primary_release_date.desc", "with_genres=28", "primary_release_date.gte=2020-01-01",
                 "vote_average.gte=7"):
        assert part in url
    assert page.title == "Popular movies · Action · 2020s · Rated 7+ · Newest first"
    assert page.cards[0].label2 == "Action · 2020s · Rated 7+ · Newest first"
    assert page.cards[0].action == ("filter", "popular_movies", "sort=newest;genre=28;year=2020s;rating=7")
    assert len(page.cards) > 1 and page.cards[1].action[0] == "title"


def test_home_rows_have_no_filter_tile():
    net()
    assert all(c.action[0] != "filter" for c in lists.home_row("popular_movies").cards)


def test_genre_pictures_do_not_repeat(monkeypatch):
    class Same:
        def by_genre(self, media_type, genre_id, page=1):
            return [media.Title(media_type=media_type, tmdb_id=1, title="A", backdrop="same.jpg"),
                    media.Title(media_type=media_type, tmdb_id=2, title="B", backdrop=f"b{genre_id}.jpg")], False
    monkeypatch.setattr(lists, "_library", lambda: Same())
    tiles = [lists.cards.Card(label=n, kind="genre", action=("grid", f"genre:movie:{i}")) for i, n in ((28, "A"), (12, "B"))]
    assert lists.genre_pictures(tiles) == {0: "same.jpg", 1: "b12.jpg"}


def test_my_list_cards_carry_the_title_details(monkeypatch):
    MyList(paths.profile_dir()).add(media.Title(media_type="movie", tmdb_id=1, title="A", poster="p1.jpg"))
    MyList(paths.profile_dir()).add(media.Title(media_type="movie", tmdb_id=2, title="B", poster="p2.jpg"))

    class Shelf:
        has_token = True

        def title(self, media_type, tmdb_id):
            if tmdb_id == 2:
                raise OSError("offline")
            return media.Title(media_type=media_type, tmdb_id=tmdb_id, title="A", poster="p1.jpg",
                               backdrop="b1.jpg", overview="Plot.", rating=7.5, genres=["Drama"])
    monkeypatch.setattr(lists, "_library", lambda: Shelf())
    cards = {c.label: c for c in lists.load("mylist").cards}
    assert cards["A"].wide == "b1.jpg" and cards["A"].plot == "Plot." and cards["A"].rating == "★ 7.5"
    assert cards["B"].poster == "p2.jpg" and cards["B"].wide is None  # offline: the saved card
