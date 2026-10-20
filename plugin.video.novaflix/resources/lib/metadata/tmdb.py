"""TMDB API v3 client (Plan 2). Thin: one function per use, parsing in media.py.

The token is passed in on every call (Library reads it from settings), so this module never
touches Kodi. A 32-hex value is a v3 API key (query parameter); anything else is a Read Access
Token (Bearer header). Either way it is registered for redaction before the first request.
This product uses the TMDB API but is not endorsed or certified by TMDB.
"""

import re

from resources.lib import errors, media, redact
from resources.lib.net import http

API = "https://api.themoviedb.org/3"
LANGUAGE = "en-US"
REGION = "IE"
LISTS = {
    "trending": "/trending/all/week",
    "popular_movies": "/movie/popular",
    "popular_tv": "/tv/popular",
    "now_playing": "/movie/now_playing",
    "upcoming": "/movie/upcoming",
    "airing_today": "/tv/airing_today",
    "top_movies": "/movie/top_rated",
    "top_tv": "/tv/top_rated",
}
REGIONAL = {"now_playing", "upcoming"}
_V3_KEY = re.compile(r"[0-9a-f]{32}")


def get(token, path, **params):
    token = (token or "").strip()
    if not token:
        raise errors.AuthError("TMDB key missing")
    redact.register_secret(token)
    params = dict(params, language=LANGUAGE)
    headers = {"Accept": "application/json"}
    if _V3_KEY.fullmatch(token):
        params["api_key"] = token
    else:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return http.get(f"{API}{path}", params=params, headers=headers).json() or {}
    except errors.HttpError as exc:
        if exc.status == 401:
            raise errors.AuthError("TMDB rejected the key") from None
        raise


def _media_type(name):
    path = LISTS[name]
    return None if path.startswith("/trending/") else (media.MOVIE if path.startswith("/movie/") else media.TV)


def _page(data, genre_names, media_type=None):
    titles = media.titles_from(data.get("results"), genre_names=genre_names, media_type=media_type)
    return titles, (data.get("page") or 1) < (data.get("total_pages") or 0)


def _all_genres(token):
    names = genres(token, media.MOVIE)
    names.update(genres(token, media.TV))
    return names


def genres(token, media_type):
    """{genre id: name} for movies or TV."""
    return {g["id"]: g["name"] for g in get(token, f"/genre/{media_type}/list").get("genres") or []}


def list_page(token, name, page=1, genre_names=None):
    """(titles, more pages?) for one of LISTS."""
    params = {"page": int(page)}
    if name in REGIONAL:
        params["region"] = REGION
    data = get(token, LISTS[name], **params)
    return _page(data, _all_genres(token) if genre_names is None else genre_names, _media_type(name))


def discover(token, media_type, genre_id, page=1, genre_names=None):
    return discover_page(token, media_type, {"with_genres": int(genre_id), "sort_by": "popularity.desc"}, page,
                         genre_names)


def discover_page(token, media_type, params, page=1, genre_names=None):
    """(titles, more pages?) from /discover with the given parameters (metadata/browse.py)."""
    data = get(token, f"/discover/{media_type}", **dict(params, page=int(page)))
    return _page(data, genres(token, media_type) if genre_names is None else genre_names, media_type)


def search(token, text, page=1, genre_names=None):
    """Movies and shows matching the text (people are dropped)."""
    data = get(token, "/search/multi", query=text.strip(), page=int(page), include_adult="false")
    return _page(data, _all_genres(token) if genre_names is None else genre_names)


def details(token, media_type, tmdb_id):
    """(Title with IMDb id, recommended Titles)."""
    data = get(token, f"/{media_type}/{int(tmdb_id)}", append_to_response="external_ids,recommendations")
    title = media.title_from(data, media_type)
    more = media.titles_from((data.get("recommendations") or {}).get("results"), media_type=media_type)
    return title, more


def season(token, tmdb_id, number):
    data = get(token, f"/tv/{int(tmdb_id)}/season/{int(number)}")
    return media.episodes_from(data.get("episodes"), tmdb_id)


def collection(token, collection_id):
    return media.collection_from(get(token, f"/collection/{int(collection_id)}"))
