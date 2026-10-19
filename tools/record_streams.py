"""Record Torrentio stream lists by IMDb id as test fixtures (developer machine only; never packaged).

Usage:  .venv\Scripts\python tools\record_streams.py
Torrentio is public and needs no key; no debrid options are used.
"""

import json
import os
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "tests", "fixtures", "torrentio")
BASE = "https://torrentio.strem.fun"
MAX_STREAMS = 40
RECORD = {
    "series_tt0903747_2_3.json": "/stream/series/tt0903747:2:3.json",  # Breaking Bad S2E3
    "movie_tt1160419.json": "/stream/movie/tt1160419.json",            # Dune (2021)
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, path in RECORD.items():
        request = urllib.request.Request(BASE + path, headers={"User-Agent": "NovaFlix-dev"})
        with urllib.request.urlopen(request, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        data["streams"] = (data.get("streams") or [])[:MAX_STREAMS]
        text = json.dumps(data, indent=1, ensure_ascii=False)
        with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print(f"{name}  {len(data['streams'])} streams")


if __name__ == "__main__":
    main()
