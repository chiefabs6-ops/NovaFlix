"""Record TMDB responses as test fixtures (developer machine only; never packaged).

Usage:  .venv\\Scripts\\python tools\\record_tmdb.py
Reads TMDB_TOKEN from .env (git-ignored). The token is never printed and is removed from
every saved response. Long result lists are cut to keep the fixtures small.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "tests", "fixtures", "tmdb")
API = "https://api.themoviedb.org/3"
MAX_RESULTS, MAX_PARTS = 6, 8
DROPPED = {"crew", "guest_stars"}  # per-episode cast lists: large and unused


def read_token():
    with open(os.path.join(ROOT, ".env"), encoding="utf-8-sig") as f:
        for line in f:
            name, _, value = line.strip().partition("=")
            if name == "TMDB_TOKEN":
                return value.strip().strip("\"'")
    raise SystemExit("TMDB_TOKEN missing from .env")


def fetch(token, path, **params):
    """(status, data). A 32-hex token is a v3 API key; anything else is a Read Access Token."""
    params = dict(params, language="en-US")
    headers = {"Accept": "application/json"}
    if re.fullmatch(r"[0-9a-f]{32}", token):
        params["api_key"] = token
    else:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def trim(data):
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if key in DROPPED:
                continue
            if key == "results" and isinstance(value, list):
                value = value[:MAX_RESULTS]
            elif key == "parts" and isinstance(value, list):
                value = value[:MAX_PARTS]
            out[key] = trim(value)
        return out
    if isinstance(data, list):
        return [trim(v) for v in data]
    return data


def save(token, name, data):
    text = json.dumps(trim(data), indent=1, ensure_ascii=False)
    text = text.replace(token, "REDACTED")
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    print(f"{name}  {len(text)} bytes")


def record(token, name, path, **params):
    status, data = fetch(token, path, **params)
    if status != 200:
        raise SystemExit(f"{name}: HTTP {status}")
    save(token, name, data)
    return data


def main():
    token = read_token()
    os.makedirs(OUT, exist_ok=True)
    simple = [
        ("trending_all_week.json", "/trending/all/week", {}),
        ("movie_popular.json", "/movie/popular", {}),
        ("tv_popular.json", "/tv/popular", {}),
        ("movie_now_playing.json", "/movie/now_playing", {"region": "IE"}),
        ("movie_upcoming.json", "/movie/upcoming", {"region": "IE"}),
        ("tv_airing_today.json", "/tv/airing_today", {}),
        ("movie_top_rated.json", "/movie/top_rated", {}),
        ("tv_top_rated.json", "/tv/top_rated", {}),
        ("genre_movie.json", "/genre/movie/list", {}),
        ("genre_tv.json", "/genre/tv/list", {}),
        ("discover_movie_28.json", "/discover/movie", {"with_genres": 28, "sort_by": "popularity.desc"}),
        ("search_multi_dune.json", "/search/multi", {"query": "dune"}),
        ("tv_1396_season_1.json", "/tv/1396/season/1", {}),
        ("tv_1396_season_2.json", "/tv/1396/season/2", {}),
    ]
    for name, path, params in simple:
        record(token, name, path, **params)
    details = {"append_to_response": "external_ids,recommendations"}
    dune = record(token, "movie_438631.json", "/movie/438631", **details)
    record(token, "collection.json", f"/collection/{dune['belongs_to_collection']['id']}")
    record(token, "tv_1396.json", "/tv/1396", **details)
    simpsons = record(token, "tv_456.json", "/tv/456", **details)
    last = max(s["season_number"] for s in simpsons["seasons"])
    record(token, f"tv_456_season_{last}.json", f"/tv/456/season/{last}")
    status, data = fetch("invalid", "/movie/popular")
    if status != 401:
        raise SystemExit(f"unauthorized.json: expected 401, got {status}")
    save(token, "unauthorized.json", data)


if __name__ == "__main__":
    main()
