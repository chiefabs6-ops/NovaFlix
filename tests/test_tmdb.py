"""TMDB client (Plan 2): auth, language/region, paging, details, seasons, collections."""

import pytest
import xbmc

from helpers import FakeNet, fixture
from resources.lib import errors, media
from resources.lib.metadata import tmdb

TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"
V3_KEY = "0123456789abcdef0123456789abcdef"


def test_missing_token_raises_before_network():
    net = FakeNet()
    with pytest.raises(errors.AuthError):
        tmdb.get("", "/movie/popular")
    assert net.calls == []


def test_bearer_token_header_and_language():
    net = FakeNet().route("/3/movie/popular", fixture("tmdb/movie_popular.json"))
    tmdb.get(TOKEN, "/movie/popular")
    assert net.headers[0]["Authorization"] == f"Bearer {TOKEN}"
    assert "language=en-US" in net.calls[0][1] and TOKEN not in net.calls[0][1]


def test_v3_key_goes_in_query():
    net = FakeNet().route("/3/movie/popular", fixture("tmdb/movie_popular.json"))
    tmdb.get(V3_KEY, "/movie/popular")
    assert f"api_key={V3_KEY}" in net.calls[0][1] and "Authorization" not in net.headers[0]


def test_rejected_token_is_auth_error():
    FakeNet().route("/3/movie/popular", fixture("tmdb/unauthorized.json"), status=401)
    with pytest.raises(errors.AuthError):
        tmdb.get(TOKEN, "/movie/popular")


def test_token_is_redacted_in_errors():
    FakeNet().route("/3/movie/popular", {"status_message": "boom"}, status=404)
    with pytest.raises(errors.HttpError) as caught:
        tmdb.get(V3_KEY, "/movie/popular")
    assert V3_KEY not in str(caught.value)
    assert all(V3_KEY not in message for _, message in xbmc.log_records)


def test_regional_lists_send_region():
    net = (FakeNet().route("/3/movie/now_playing", fixture("tmdb/movie_now_playing.json"))
           .route("/3/movie/popular", fixture("tmdb/movie_popular.json")))
    tmdb.list_page(TOKEN, "now_playing", genre_names={})
    tmdb.list_page(TOKEN, "popular_movies", genre_names={})
    assert "region=IE" in net.calls[0][1] and "region=" not in net.calls[1][1]


def test_list_page_reports_more_pages_and_genre_names():
    raw = fixture("tmdb/movie_popular.json")
    net = (FakeNet().route("/3/movie/popular", raw)
           .route("/3/genre/movie/list", fixture("tmdb/genre_movie.json"))
           .route("/3/genre/tv/list", fixture("tmdb/genre_tv.json")))
    titles, more = tmdb.list_page(TOKEN, "popular_movies")
    assert more == (raw["page"] < raw["total_pages"]) and len(titles) == len(raw["results"])
    assert titles[0].genres and all(t.media_type == media.MOVIE for t in titles)
    assert "page=1" in next(url for _, url, _ in net.calls if "/movie/popular" in url)


def test_trending_mixes_movies_and_shows():
    FakeNet().route("/3/trending/all/week", fixture("tmdb/trending_all_week.json"))
    titles, _ = tmdb.list_page(TOKEN, "trending", genre_names={})
    assert {t.media_type for t in titles} <= {media.MOVIE, media.TV} and titles


def test_genres_and_discover():
    net = (FakeNet().route("/3/genre/movie/list", fixture("tmdb/genre_movie.json"))
           .route("/3/discover/movie", fixture("tmdb/discover_movie_28.json")))
    names = tmdb.genres(TOKEN, media.MOVIE)
    assert names[28] == "Action"
    titles, _ = tmdb.discover(TOKEN, media.MOVIE, 28, genre_names=names)
    assert titles and "with_genres=28" in net.calls[-1][1] and all(t.is_movie for t in titles)


def test_details_returns_title_and_recommendations():
    raw = fixture("tmdb/movie_438631.json")
    net = FakeNet().route("/3/movie/438631", raw)
    title, more = tmdb.details(TOKEN, media.MOVIE, 438631)
    assert title.key == "movie:438631" and title.imdb_id == raw["external_ids"]["imdb_id"]
    assert [t.tmdb_id for t in more] == [r["id"] for r in raw["recommendations"]["results"]]
    assert "append_to_response=external_ids%2Crecommendations" in net.calls[0][1]


def test_search_returns_movies_and_shows_only():
    raw = fixture("tmdb/search_multi_dune.json")
    raw = dict(raw, results=raw["results"] + [{"id": 9, "media_type": "person", "name": "P"}])
    net = FakeNet().route("/3/search/multi", raw)
    titles, _ = tmdb.search(TOKEN, "dune", genre_names={})
    assert len(titles) == len(raw["results"]) - 1 and "query=dune" in net.calls[0][1]


def test_season_and_collection():
    raw = fixture("tmdb/collection.json")
    FakeNet().route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json")).route(
        f"/3/collection/{raw['id']}", raw)
    episodes = tmdb.season(TOKEN, 1396, 2)
    assert episodes[0].season == 2 and episodes[0].number == 1
    assert tmdb.collection(TOKEN, raw["id"]).name == raw["name"]
