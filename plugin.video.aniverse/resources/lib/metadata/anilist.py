"""AniList GraphQL client (DEC-011): catalog, search, seasons, details.

Docs: https://docs.anilist.co/ — no key needed for public data.
"""

import re

from resources.lib import errors
from resources.lib.models import ANIME_FORMATS, CATALOG_FORMATS, RelationNode, Show, ShowRef
from resources.lib.net import http

URL = "https://graphql.anilist.co"
PER_PAGE = 30

_MEDIA = """
id idMal format status episodes duration season seasonYear averageScore genres isAdult
title { romaji english native } synonyms description(asHtml: false)
coverImage { extraLarge large } bannerImage
startDate { year month day } nextAiringEpisode { episode airingAt }
"""

_PAGE_QUERY = """
query ($page: Int, $perPage: Int, $sort: [MediaSort], $season: MediaSeason, $seasonYear: Int,
       $genre: String, $search: String, $formats: [MediaFormat]) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(type: ANIME, isAdult: false, sort: $sort, season: $season, seasonYear: $seasonYear,
          genre: $genre, search: $search, format_in: $formats) { %s }
  }
}""" % _MEDIA

_DETAILS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    %s
    relations { edges { relationType node { id idMal type format title { romaji english } coverImage { large } } } }
  }
}""" % _MEDIA

_AIRING_QUERY = """
query ($page: Int, $from: Int, $to: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    airingSchedules(airingAt_greater: $from, airingAt_lesser: $to, sort: [TIME_DESC]) {
      episode airingAt media { %s }
    }
  }
}""" % _MEDIA

_BY_MAL_QUERY = """
query ($ids: [Int], $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(idMal_in: $ids, type: ANIME) { %s }
  }
}""" % _MEDIA

_RELATIONS_QUERY = """
query ($ids: [Int], $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(id_in: $ids, type: ANIME) {
      id idMal format title { romaji english native } coverImage { large } startDate { year month day }
      relations { edges { relationType node { id type format } } }
    }
  }
}"""

_GENRES_QUERY = "{ GenreCollection }"
EXCLUDED_GENRES = {"Hentai"}


def _query(query, variables=None):
    resp = http.post(URL, json_body={"query": query, "variables": variables or {}},
                     headers={"Accept": "application/json"})
    payload = resp.json() or {}
    if payload.get("errors"):
        # GraphQL errors arrive with HTTP 200; messages contain no secrets.
        raise errors.HttpError(f"AniList error: {payload['errors'][0].get('message', 'unknown')}", resp.status, payload)
    return payload.get("data") or {}


def display_title(title):
    """English first, romaji fallback (DEC-012)."""
    title = title or {}
    return title.get("english") or title.get("romaji") or title.get("native") or "?"


def clean_description(text):
    if not text:
        return None
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?i>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def _date(d):
    if not d or not d.get("year"):
        return None
    if d.get("month") and d.get("day"):
        return f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}"
    return str(d["year"])


def _watchable(node):
    """Manga, novels and music videos are not watchable here."""
    return node.get("type", "ANIME") == "ANIME" and node.get("format") in ANIME_FORMATS and node.get("format") != "MUSIC"


def to_show(media):
    title = media.get("title") or {}
    nxt = media.get("nextAiringEpisode") or {}
    cover = media.get("coverImage") or {}
    relations = []
    for edge in ((media.get("relations") or {}).get("edges") or []):
        node = edge.get("node") or {}
        if not _watchable(node):
            continue
        relations.append(ShowRef(
            anilist_id=node["id"], relation=edge.get("relationType") or "OTHER", format=node.get("format"),
            title=display_title(node.get("title")), poster=(node.get("coverImage") or {}).get("large"),
            mal_id=node.get("idMal")))
    return Show(
        anilist_id=media["id"],
        title=display_title(title),
        title_romaji=title.get("romaji"),
        title_english=title.get("english"),
        title_native=title.get("native"),
        synonyms=media.get("synonyms") or [],
        mal_id=media.get("idMal"),
        format=media.get("format"),
        status=media.get("status"),
        episodes_total=media.get("episodes"),
        duration_min=media.get("duration"),
        season=media.get("season"),
        year=media.get("seasonYear") or (media.get("startDate") or {}).get("year"),
        score=media.get("averageScore"),
        genres=media.get("genres") or [],
        description=clean_description(media.get("description")),
        poster=cover.get("extraLarge") or cover.get("large"),
        banner=media.get("bannerImage"),
        start_date=_date(media.get("startDate")),
        next_episode=nxt.get("episode"),
        next_airing_at=nxt.get("airingAt"),
        relations=relations,
    )


def media_page(page=1, sort=None, season=None, season_year=None, genre=None, search=None):
    variables = {
        "page": page, "perPage": PER_PAGE, "sort": sort, "season": season, "seasonYear": season_year,
        "genre": genre, "search": search, "formats": list(CATALOG_FORMATS),
    }
    data = _query(_PAGE_QUERY, {k: v for k, v in variables.items() if v is not None})
    page_data = data.get("Page") or {}
    shows = [to_show(m) for m in page_data.get("media") or [] if not m.get("isAdult")]
    return shows, bool((page_data.get("pageInfo") or {}).get("hasNextPage"))


def details(anilist_id):
    media = _query(_DETAILS_QUERY, {"id": int(anilist_id)}).get("Media")
    if not media:
        raise errors.HttpError(f"AniList has no anime {anilist_id}", 404)
    return to_show(media)


def recently_aired(start, end, page=1):
    """[(Show, episode, airing_at)] newest first, catalog formats only."""
    data = _query(_AIRING_QUERY, {"page": page, "from": int(start), "to": int(end)})
    page_data = data.get("Page") or {}
    out = []
    for item in page_data.get("airingSchedules") or []:
        media = item.get("media") or {}
        if media.get("isAdult") or media.get("format") not in CATALOG_FORMATS:
            continue
        out.append((to_show(media), item.get("episode"), item.get("airingAt")))
    return out, bool((page_data.get("pageInfo") or {}).get("hasNextPage"))


def genres():
    return [g for g in _query(_GENRES_QUERY).get("GenreCollection") or [] if g not in EXCLUDED_GENRES]


def by_mal_ids(mal_ids):
    """{mal_id: Show} for the given MAL IDs; IDs AniList doesn't know are absent."""
    out = {}
    ids = sorted({int(i) for i in mal_ids})
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        data = _query(_BY_MAL_QUERY, {"ids": chunk, "page": 1})
        for media in (data.get("Page") or {}).get("media") or []:
            if media.get("idMal"):
                out[int(media["idMal"])] = to_show(media)
    return out


def _start(d):
    if not d or not d.get("year"):
        return None
    return (d["year"], d.get("month") or 0, d.get("day") or 0)


def relation_nodes(ids):
    """{anilist_id: RelationNode} for the given IDs (M14); IDs AniList doesn't return are absent."""
    out = {}
    ids = sorted({int(i) for i in ids})
    for begin in range(0, len(ids), 50):
        data = _query(_RELATIONS_QUERY, {"ids": ids[begin:begin + 50], "page": 1})
        for media in (data.get("Page") or {}).get("media") or []:
            edges = [(edge.get("relationType") or "OTHER", edge["node"]["id"])
                     for edge in ((media.get("relations") or {}).get("edges") or [])
                     if _watchable(edge.get("node") or {})]
            out[media["id"]] = RelationNode(
                anilist_id=media["id"], title=display_title(media.get("title")), format=media.get("format"),
                mal_id=media.get("idMal"), poster=(media.get("coverImage") or {}).get("large"),
                start=_start(media.get("startDate")), edges=edges)
    return out
