"""ani.zip episode details and cross-provider IDs (DEC-046).

Unofficial, keyless, undocumented service. Episode keys are "1".."N" for
regular episodes and "S1".. for specials; only regular ones are used here.
"""

from resources.lib.models import Episode
from resources.lib.net import http

URL = "https://api.ani.zip/mappings"


def fetch(anilist_id):
    return http.get(URL, params={"anilist_id": int(anilist_id)}).json() or {}


def _title(value):
    if isinstance(value, dict):
        return value.get("en") or value.get("x-jat") or None
    return value or None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def episodes(data, anilist_id):
    """Regular episodes by number (specials and junk keys dropped)."""
    count = _int(data.get("episodeCount"))
    out = {}
    for key, ep in (data.get("episodes") or {}).items():
        if not key.isdigit():
            continue
        number = int(key)
        if number < 1 or (count and number > count):
            continue
        out[number] = Episode(
            anilist_id=int(anilist_id),
            number=number,
            title=_title(ep.get("title")),
            air_date=ep.get("airDate") or ep.get("airdate"),
            thumbnail=ep.get("image"),
            overview=ep.get("overview") or ep.get("summary"),
            runtime_min=_int(ep.get("runtime") or ep.get("length")),
            absolute_number=_int(ep.get("absoluteEpisodeNumber")),
            tvdb_season=_int(ep.get("seasonNumber")),
            tvdb_episode=_int(ep.get("episodeNumber")),
        )
    return out


def mappings(data):
    return data.get("mappings") or {}


def fanart(data):
    for image in data.get("images") or []:
        if image.get("coverType") == "Fanart" and image.get("url"):
            return image["url"]
    return None
