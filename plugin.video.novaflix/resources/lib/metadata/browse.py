"""Sort and filter choices for the Popular and Top rated lists. Pure functions, no Kodi.

With no choices the lists stay TMDB's own (/movie/popular, /tv/top_rated...). With any
choice they come from TMDB /discover, with the parameters built here. Choices travel
in the grid key: "popular_movies:sort=newest;genre=28;year=2020s;rating=7".
Unreleased titles are always left out of a filtered list: nothing can be played yet.
"""

import datetime
from dataclasses import dataclass, replace

from resources.lib import media

# list name -> (media type, the list's own order)
LISTS = {"popular_movies": (media.MOVIE, "popular"), "popular_tv": (media.TV, "popular"),
         "top_movies": (media.MOVIE, "rating"), "top_tv": (media.TV, "rating")}
SORTS = ["popular", "rating", "newest", "oldest", "title"]
YEARS = ["this_year", "2020s", "2010s", "2000s", "1990s", "1980s", "older"]
RATINGS = [6, 7, 8]
# Fewer votes than this and a title is too obscure for these lists; rating orders need more,
# or a film with three 10/10 votes tops them.
MIN_VOTES = {"popular": 50, "rating": 300}
RATING_MIN_VOTES = 300


@dataclass(frozen=True)
class Filters:
    sort: str = ""      # "" = the list's own order
    genre: int = 0      # TMDB genre id; 0 = any
    year: str = ""      # one of YEARS; "" = any
    rating: int = 0     # minimum TMDB rating (0-10); 0 = any

    @property
    def active(self):
        return self != Filters()


def parse(text):
    """Filters from a grid key's argument; unknown or malformed parts are ignored."""
    values = {}
    for part in (text or "").split(";"):
        name, _, value = part.partition("=")
        if name == "sort" and value in SORTS:
            values["sort"] = value
        elif name == "genre" and value.isdigit():
            values["genre"] = int(value)
        elif name == "year" and value in YEARS:
            values["year"] = value
        elif name == "rating" and value.isdigit() and int(value) in RATINGS:
            values["rating"] = int(value)
    return Filters(**values)


def encode(filters):
    parts = [("sort", filters.sort), ("genre", filters.genre), ("year", filters.year), ("rating", filters.rating)]
    return ";".join(f"{k}={v}" for k, v in parts if v)


def key(list_name, filters):
    """The grid key for a list with these choices; the plain list name without any."""
    return f"{list_name}:{encode(filters)}" if filters.active else list_name


def with_sort(list_name, filters, sort):
    """Picking the list's own order clears the choice, so the key stays short."""
    return replace(filters, sort="" if sort == LISTS[list_name][1] else sort)


def sort_of(list_name, filters):
    return filters.sort or LISTS[list_name][1]


def _years(year, today):
    """(first day, last day) of a YEARS choice; None = open."""
    if year == "this_year":
        return f"{today.year}-01-01", None
    if year == "older":
        return None, "1979-12-31"
    if year.endswith("s") and year[:4].isdigit():
        start = int(year[:4])
        return f"{start}-01-01", f"{start + 9}-12-31"
    return None, None


def params(list_name, filters, today=None):
    """TMDB /discover parameters for the list with these choices."""
    media_type, own = LISTS[list_name]
    today = today or datetime.date.today()
    date = "primary_release_date" if media_type == media.MOVIE else "first_air_date"
    sort = filters.sort or own
    sort_by = {"popular": "popularity.desc", "rating": "vote_average.desc", "newest": f"{date}.desc",
               "oldest": f"{date}.asc", "title": "title.asc" if media_type == media.MOVIE else "name.asc"}[sort]
    votes = MIN_VOTES[own]
    if sort == "rating" or filters.rating:
        votes = max(votes, RATING_MIN_VOTES)
    out = {"sort_by": sort_by, "include_adult": "false", "vote_count.gte": votes}
    first, last = _years(filters.year, today)
    last = min(last, today.isoformat()) if last else today.isoformat()
    if first:
        out[f"{date}.gte"] = first
    out[f"{date}.lte"] = last
    if filters.genre:
        out["with_genres"] = filters.genre
    if filters.rating:
        out["vote_average.gte"] = filters.rating
    return out
