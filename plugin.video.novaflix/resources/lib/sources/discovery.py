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
from resources.lib.sources import rdcloud, torrentio

PROVIDER_TIMEOUT = 12
TOTAL_TIMEOUT = 15

OK, EMPTY, FAILED, SKIPPED = "ok", "empty", "failed", "skipped"


@dataclass
class Wanted:
    show: object
    number: int
    absolute: Optional[int] = None
    tvdb: Optional[tuple] = None      # (season, episode) for an episode
    imdb_id: Optional[str] = None
    season: Optional[int] = None
    titles: Optional[list] = None     # title (and episode name): their words are never extras or languages

    @property
    def is_movie(self):
        return self.show.is_movie


def for_title(title, season=None, episode=None, episode_name=None):
    """What to look for: a TMDB movie, or one episode of a TMDB show (TMDB season/episode numbers)."""
    if title.is_movie:
        return Wanted(show=title, number=1, imdb_id=title.imdb_id, titles=[title.title])
    return Wanted(show=title, number=int(episode), tvdb=(int(season), int(episode)), imdb_id=title.imdb_id,
                  season=int(season), titles=[title.title] + ([episode_name] if episode_name else []))


@dataclass
class Settings:
    torrentio_enabled: bool = True
    torrentio_url: str = torrentio.DEFAULT_BASE


def from_torrentio(wanted, settings):
    if not wanted.imdb_id:
        return SKIPPED, []
    url = torrentio.imdb_url(settings.torrentio_url, wanted.imdb_id, wanted.season, wanted.number, wanted.is_movie)
    resp = http.get(url, timeout=PROVIDER_TIMEOUT)
    return OK, torrentio.parse_streams(resp.json(), wanted.number, wanted.absolute, wanted.tvdb, wanted.is_movie,
                                       wanted.titles)


def from_rdcloud(wanted, client):
    if client is None:
        return SKIPPED, []
    torrents = client.torrents()
    out = []
    for t in rdcloud.matching_torrents(torrents, wanted.show):
        info = client.torrent_info(t["id"])
        out.extend(rdcloud.candidates_from_info(info, wanted.number, wanted.absolute, wanted.tvdb, wanted.is_movie,
                                                wanted.titles))
    return OK, out


def discover(wanted, settings, rd_client=None, cancelled=lambda: False):
    """({provider: outcome}, [Candidate]). Waits at most TOTAL_TIMEOUT seconds."""
    jobs = {"rdcloud": lambda: from_rdcloud(wanted, rd_client)}
    if settings.torrentio_enabled:
        jobs["torrentio"] = lambda: from_torrentio(wanted, settings)

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
