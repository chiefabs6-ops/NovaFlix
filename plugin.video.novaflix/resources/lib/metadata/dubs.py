"""English-dub availability from the community MAL-Dubs list (DEC-025).

The file is AGPL-3.0 licensed, so it is downloaded at runtime and never
bundled. The background service refreshes it at most weekly; views only read
the local copy. A failed download keeps the last good copy.
"""

import json
import os
import time

from resources.lib.kodi import log
from resources.lib.net import http

URL = "https://raw.githubusercontent.com/MAL-Dubs/MAL-Dubs/main/data/dubInfo.json"
FILENAME = "mal_dubs.json"
REFRESH_AFTER_S = 7 * 24 * 3600

DUBBED = "dubbed"
PARTIAL = "partial"


def _path(directory):
    return os.path.join(directory, FILENAME)


def is_stale(directory, now=None):
    path = _path(directory)
    if not os.path.exists(path):
        return True
    return (now or time.time()) - os.path.getmtime(path) > REFRESH_AFTER_S


def refresh(directory):
    """Download a fresh copy. Returns True on success; keeps the old file otherwise."""
    try:
        data = http.get(URL, timeout=20).json()
        dubbed = [int(x) for x in data["dubbed"]]
        incomplete = [int(x) for x in data.get("incomplete", [])]
    except Exception as exc:  # network, JSON or shape problems
        log.warning(f"dub list refresh failed: {type(exc).__name__}: {exc}")
        return False
    tmp = _path(directory) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"dubbed": dubbed, "incomplete": incomplete}, f)
    os.replace(tmp, _path(directory))
    log.info(f"dub list updated: {len(dubbed)} titles")
    return True


class DubIndex:
    def __init__(self, directory):
        self._dubbed = set()
        self._partial = set()
        try:
            with open(_path(directory), encoding="utf-8") as f:
                data = json.load(f)
            self._dubbed = set(data.get("dubbed", []))
            self._partial = set(data.get("incomplete", []))
        except (OSError, ValueError):
            pass  # no list yet: no badges, never an error

    def status(self, mal_id):
        if not mal_id:
            return None
        if mal_id in self._partial:
            return PARTIAL
        if mal_id in self._dubbed:
            return DUBBED
        return None
