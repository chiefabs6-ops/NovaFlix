"""Sort and filter choices for the Popular / Top rated lists (metadata/browse.py)."""

import datetime

import pytest

from resources.lib.metadata import browse
from resources.lib.metadata.browse import Filters

TODAY = datetime.date(2026, 10, 20)


def test_encode_and_parse_round_trip():
    f = Filters(sort="newest", genre=28, year="2020s", rating=7)
    assert browse.encode(f) == "sort=newest;genre=28;year=2020s;rating=7"
    assert browse.parse(browse.encode(f)) == f
    assert browse.key("popular_movies", f) == "popular_movies:sort=newest;genre=28;year=2020s;rating=7"
    assert browse.key("popular_movies", Filters()) == "popular_movies" and not Filters().active


@pytest.mark.parametrize("text", ["", None, "junk", "sort=sideways", "genre=abc", "rating=9", "year=1850s",
                                  ";;=;", "sort=newest;sort"])
def test_bad_keys_are_ignored(text):
    f = browse.parse(text)
    assert f.sort in ("", "newest") and f.genre == 0 and f.year == "" and f.rating == 0


def test_picking_the_lists_own_order_clears_the_sort():
    assert browse.with_sort("popular_movies", Filters(sort="newest"), "popular").sort == ""
    assert browse.with_sort("top_tv", Filters(), "rating").sort == ""
    assert browse.with_sort("top_tv", Filters(), "newest").sort == "newest"
    assert browse.sort_of("top_movies", Filters()) == "rating"


def test_newest_movies_leave_out_unreleased_ones():
    p = browse.params("popular_movies", Filters(sort="newest"), TODAY)
    assert p["sort_by"] == "primary_release_date.desc" and p["primary_release_date.lte"] == "2026-10-20"
    assert p["vote_count.gte"] == 50 and p["include_adult"] == "false"


def test_tv_uses_first_air_date_and_name():
    p = browse.params("popular_tv", Filters(sort="oldest", year="1990s"), TODAY)
    assert p["sort_by"] == "first_air_date.asc"
    assert (p["first_air_date.gte"], p["first_air_date.lte"]) == ("1990-01-01", "1999-12-31")
    assert browse.params("top_tv", Filters(sort="title"), TODAY)["sort_by"] == "name.asc"
    assert browse.params("top_movies", Filters(sort="title"), TODAY)["sort_by"] == "title.asc"


def test_top_rated_and_rating_choices_need_enough_votes():
    assert browse.params("top_movies", Filters(), TODAY)["sort_by"] == "vote_average.desc"
    assert browse.params("top_movies", Filters(), TODAY)["vote_count.gte"] == 300
    p = browse.params("popular_movies", Filters(rating=8), TODAY)
    assert p["vote_average.gte"] == 8 and p["vote_count.gte"] == 300


def test_year_choices():
    assert browse.params("popular_movies", Filters(year="this_year"), TODAY)["primary_release_date.gte"] == "2026-01-01"
    p = browse.params("popular_movies", Filters(year="older"), TODAY)
    assert p["primary_release_date.lte"] == "1979-12-31" and "primary_release_date.gte" not in p
    p = browse.params("popular_movies", Filters(year="2020s"), TODAY)
    assert p["primary_release_date.lte"] == "2026-10-20"  # this decade ends today


def test_genre():
    assert browse.params("popular_tv", Filters(genre=18), TODAY)["with_genres"] == 18
