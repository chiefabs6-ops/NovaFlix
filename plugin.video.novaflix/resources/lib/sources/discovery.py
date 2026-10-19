"""Runs the discovery providers in parallel with time limits (DEC-003).

Each provider fails on its own: one being down never hides the others'
results. Returns candidates plus a per-provider outcome for messages.
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional

from resources.lib import errors
from resources.lib.kodi import log
from resources.lib.net import http
from resources.lib.sources import nyaa, rdcloud, torrentio

PROVIDER_TIMEOUT = 12
TOTAL_TIMEOUT = 15

OK, EMPTY, FAILED, SKIPPED = "ok", "empty", "failed", "skipped"


@dataclass
class Wanted:
    show: object
    number: int
    absolute: Optional[int] = None
    tvdb: Optional[tuple] = None
    kitsu_id: Optional[int] = None
    imdb_id: Optional[str] = None     # NovaFlix titles (TMDB); anime entries use kitsu_id
    season: Optional[int] = None

    @property
    def is_movie(self):
        return self.show.is_movie

    @property
    def is_title(self):
        return hasattr(self.show, "tmdb_id")


def for_title(title, season=None, episode=None):
    """What to look for: a TMDB movie, or one episode of a TMDB show (TMDB season/episode numbers)."""
    if title.is_movie:
        return Wanted(show=title, number=1, imdb_id=title.imdb_id)
    return Wanted(show=title, number=int(episode), tvdb=(int(season), int(episode)), imdb_id=title.imdb_id,
                  season=int(season))


@dataclass
class Settings:
    torrentio_enabled: bool = True
    torrentio_url: str = torrentio.DEFAULT_BASE
    nyaa_enabled: bool = True


def from_torrentio(wanted, settings):
    if wanted.is_title:
        if not wanted.imdb_id:
            return SKIPPED, []
        url = torrentio.imdb_url(settings.torrentio_url, wanted.imdb_id, wanted.season, wanted.number, wanted.is_movie)
    elif wanted.kitsu_id:
        url = torrentio.url(settings.torrentio_url, wanted.kitsu_id, wanted.number, wanted.is_movie)
    else:
        return SKIPPED, []
    resp = http.get(url, timeout=PROVIDER_TIMEOUT)
    return OK, torrentio.parse_streams(resp.json(), wanted.number, wanted.absolute, wanted.tvdb, wanted.is_movie)


def from_nyaa(wanted, settings):
    if wanted.is_title:
        return SKIPPED, []  # Nyaa is an anime tracker
    title = wanted.show.title_romaji or wanted.show.title
    resp = http.get(nyaa.URL, params={"page": "rss", "q": nyaa.query_for(title, wanted.number, wanted.is_movie),
                                      "c": "1_2", "f": "0"}, timeout=PROVIDER_TIMEOUT)
    return OK, nyaa.parse_rss(resp.text, wanted.number, wanted.absolute, wanted.tvdb, wanted.is_movie)


def from_rdcloud(wanted, client):
    if client is None:
        return SKIPPED, []
    torrents = client.torrents()
    out = []
    for t in rdcloud.matching_torrents(torrents, wanted.show):
        info = client.torrent_info(t["id"])
        out.extend(rdcloud.candidates_from_info(info, wanted.number, wanted.absolute, wanted.tvdb, wanted.is_movie))
    return OK, out


def discover(wanted, settings, rd_client=None, cancelled=lambda: False):
    """({provider: outcome}, [Candidate]). Waits at most TOTAL_TIMEOUT seconds."""
    jobs = {"rdcloud": lambda: from_rdcloud(wanted, rd_client)}
    if settings.torrentio_enabled:
        jobs["torrentio"] = lambda: from_torrentio(wanted, settings)
    if settings.nyaa_enabled:
        jobs["nyaa"] = lambda: from_nyaa(wanted, settings)

    results = {}

    def run(name, job):
        try:
            results[name] = job()
        except errors.AuthError:
            results[name] = (SKIPPED, [])  # not connected / login expired: other providers still useful
        except Exception as exc:
            log.warning(f"source provider {name} failed: {type(exc).__name__}: {exc}")
            results[name] = (FAILED, [])

    threads = [threading.Thread(target=run, args=item, daemon=True) for item in jobs.items()]
    for t in threads:
        t.start()
    deadline = time.monotonic() + TOTAL_TIMEOUT
    for t in threads:
        while t.is_alive() and time.monotonic() < deadline and not cancelled():
            t.join(0.2)

    outcomes, candidates = {}, []
    for name in jobs:
        outcome, found = results.get(name, (FAILED, []))
        if outcome == OK and not found:
            outcome = EMPTY
        outcomes[name] = outcome
        candidates.extend(found)
    return outcomes, candidates
