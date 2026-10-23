"""Library facade (Plan 2): caching, aired episodes and up next across seasons."""

import copy

import pytest

from helpers import FakeNet, Replies, fixture
from resources.lib import errors, media
from resources.lib.metadata import library
from resources.lib.metadata.library import Library

TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"


def genre_routes(net):
    return (net.route("/3/genre/movie/list", fixture("tmdb/genre_movie.json"))
            .route("/3/genre/tv/list", fixture("tmdb/genre_tv.json")))


def breaking_bad(seasons=None):
    data = copy.deepcopy(fixture("tmdb/tv_1396.json"))
    if seasons is not None:
        data["seasons"] = [s for s in data["seasons"] if s["season_number"] in seasons]
    return data


def bb_net(seasons=None):
    return (FakeNet().route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
            .route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json"))
            .route("/3/tv/1396", breaking_bad(seasons)))


def test_lists_are_cached():
    net = genre_routes(FakeNet().route("/3/movie/popular", fixture("tmdb/movie_popular.json")))
    first, more = Library(token=TOKEN).list("popular_movies")
    calls = len(net.calls)
    again, more_again = Library(token=TOKEN).list("popular_movies")
    assert len(net.calls) == calls and [t.key for t in again] == [t.key for t in first] and more == more_again
    assert first[0].genres  # genre names filled from the cached genre lists


def test_failed_call_is_not_cached():
    raw = fixture("tmdb/movie_popular.json")
    genre_routes(FakeNet().route("/3/movie/popular", Replies((404, {"status_message": "x"}), (200, raw))))
    with pytest.raises(errors.HttpError):
        Library(token=TOKEN).list("popular_movies")
    titles, _ = Library(token=TOKEN).list("popular_movies")
    assert titles


def test_title_and_more_like_this_share_one_request():
    net = FakeNet().route("/3/movie/438631", fixture("tmdb/movie_438631.json"))
    lib = Library(token=TOKEN)
    assert lib.title(media.MOVIE, 438631).key == "movie:438631"
    assert lib.more_like_this(media.MOVIE, 438631)
    assert net.count("/3/movie/438631") == 1
    assert lib.cached_title(media.MOVIE, 438631).imdb_id and lib.cached_title(media.TV, 1) is None


def test_episodes_hide_unaired(monkeypatch):
    bb_net()
    monkeypatch.setattr(library, "_today", lambda: "2009-03-15")
    lib = Library(token=TOKEN)
    raw = fixture("tmdb/tv_1396_season_2.json")["episodes"]
    expected = [e["episode_number"] for e in raw if e["air_date"] <= "2009-03-15"]
    assert [e.number for e in lib.episodes(lib.title(media.TV, 1396), 2)] == expected and expected


def test_episodes_without_dates_are_listed(monkeypatch):
    season = copy.deepcopy(fixture("tmdb/tv_1396_season_2.json"))
    for e in season["episodes"]:
        e["air_date"] = None
    FakeNet().route("/3/tv/1396/season/2", season).route("/3/tv/1396", breaking_bad())
    lib = Library(token=TOKEN)
    assert len(lib.episodes(lib.title(media.TV, 1396), 2)) == len(season["episodes"])


def test_next_episode_within_season():
    bb_net()
    lib = Library(token=TOKEN)
    assert lib.next_episode(lib.title(media.TV, 1396), 1, 3) == (1, 4)


def test_next_episode_crosses_season():
    bb_net()
    lib = Library(token=TOKEN)
    last = len(fixture("tmdb/tv_1396_season_1.json")["episodes"])
    assert lib.next_episode(lib.title(media.TV, 1396), 1, last) == (2, 1)


def test_next_episode_none_at_series_end():
    bb_net(seasons={0, 1, 2})
    lib = Library(token=TOKEN)
    last = len(fixture("tmdb/tv_1396_season_2.json")["episodes"])
    assert lib.next_episode(lib.title(media.TV, 1396), 2, last) is None


def test_next_episode_none_when_next_season_unaired(monkeypatch):
    bb_net()
    first_s2 = fixture("tmdb/tv_1396_season_2.json")["episodes"][0]["air_date"]
    monkeypatch.setattr(library, "_today", lambda: "2009-03-01")
    assert first_s2 > "2009-03-01"
    lib = Library(token=TOKEN)
    assert lib.next_episode(lib.title(media.TV, 1396), 1, 7) is None


def test_next_episode_never_specials():
    bb_net(seasons={0, 1, 2})
    lib = Library(token=TOKEN)
    title = lib.title(media.TV, 1396)
    assert lib.next_episode(title, 0, 1) is None
    last = len(fixture("tmdb/tv_1396_season_2.json")["episodes"])
    assert lib.next_episode(title, 2, last) is None  # season 0 (specials) is listed, but never next


def test_missing_token_needs_no_network():
    net = FakeNet()
    with pytest.raises(errors.AuthError):
        Library(token="").list("popular_movies")
    assert net.calls == []


def test_genres_sorted_by_name_and_collection_cached():
    raw = fixture("tmdb/collection.json")
    net = genre_routes(FakeNet()).route(f"/3/collection/{raw['id']}", raw)
    lib = Library(token=TOKEN)
    names = [name for _, name in lib.genres(media.TV)]
    assert names == sorted(names)
    lib.collection(raw["id"])
    lib.collection(raw["id"])
    assert net.count("/3/collection/") == 1


def test_undated_episode_in_a_dated_season_is_not_aired(monkeypatch):
    # TMDB lists announced episodes with air_date null ("TBA") next to dated ones.
    season = copy.deepcopy(fixture("tmdb/tv_1396_season_2.json"))
    season["episodes"][-1]["air_date"] = None
    FakeNet().route("/3/tv/1396/season/2", season).route("/3/tv/1396", breaking_bad())
    lib = Library(token=TOKEN)
    title = lib.title(media.TV, 1396)
    numbers = [e.number for e in lib.episodes(title, 2)]
    last = season["episodes"][-1]["episode_number"]
    assert last not in numbers and numbers
    assert lib.next_episode(title, 2, last - 1) is None


def test_next_episode_skips_a_gap_in_numbering():
    season = copy.deepcopy(fixture("tmdb/tv_1396_season_1.json"))
    season["episodes"] = [e for e in season["episodes"] if e["episode_number"] != 4]
    FakeNet().route("/3/tv/1396/season/1", season).route("/3/tv/1396", breaking_bad())
    lib = Library(token=TOKEN)
    assert lib.next_episode(lib.title(media.TV, 1396), 1, 3) == (1, 5)


def test_next_season_starting_above_one():
    s2 = copy.deepcopy(fixture("tmdb/tv_1396_season_2.json"))
    for e in s2["episodes"]:
        e["episode_number"] += 7  # continues the numbering of season 1
    (FakeNet().route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
     .route("/3/tv/1396/season/2", s2).route("/3/tv/1396", breaking_bad()))
    lib = Library(token=TOKEN)
    assert lib.next_episode(lib.title(media.TV, 1396), 1, 7) == (2, 8)


# -- Cinematic UI: title logos (0.4.0) ------------------------------------------------------------

def _with_logos(logos):
    data = copy.deepcopy(fixture("tmdb/movie_438631.json"))
    data["images"] = {"logos": logos}
    return data


def test_details_reads_english_logo():
    FakeNet().route("/3/movie/438631", _with_logos([
        {"iso_639_1": "pl", "file_path": "/pl.png"}, {"iso_639_1": None, "file_path": "/none.png"},
        {"iso_639_1": "en", "file_path": "/en.png"}]))
    lib = Library(token=TOKEN)
    assert lib.logo(media.MOVIE, 438631) == "https://image.tmdb.org/t/p/w500/en.png"


def test_logo_falls_back_to_one_without_language():
    FakeNet().route("/3/movie/438631", _with_logos([{"iso_639_1": "pl", "file_path": "/pl.png"},
                                                    {"iso_639_1": None, "file_path": "/none.png"}]))
    assert Library(token=TOKEN).logo(media.MOVIE, 438631).endswith("/none.png")


def test_details_ask_for_logos():
    net = FakeNet().route("/3/movie/438631", _with_logos([]))
    assert Library(token=TOKEN).logo(media.MOVIE, 438631) is None
    url = net.calls[-1][1]
    assert "images" in url and "include_image_language=en%2Cnull" in url


def test_cached_title_without_logo_loads():
    data = media.title_from(fixture("tmdb/movie_438631.json"), media.MOVIE).to_dict()
    data.pop("logo", None)
    assert media.Title.from_dict(data).logo is None
