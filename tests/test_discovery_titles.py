"""Discovery for TMDB titles (Plan 3, Task 4): Torrentio by IMDb id, no Nyaa, account search by title."""

from helpers import FakeNet, fixture
from resources.lib import media
from resources.lib.sources import discovery, rdcloud


def breaking_bad():
    return media.title_from(fixture("tmdb/tv_1396.json"), media.TV)


def dune():
    return media.title_from(fixture("tmdb/movie_438631.json"), media.MOVIE)


def test_for_title_episode_and_movie():
    w = discovery.for_title(breaking_bad(), 2, 3)
    assert (w.number, w.tvdb, w.absolute, w.imdb_id, w.season, w.is_movie) == (3, (2, 3), None, "tt0903747", 2, False)
    m = discovery.for_title(dune())
    assert (m.number, m.tvdb, m.imdb_id, m.is_movie) == (1, None, dune().imdb_id, True)


def test_discover_uses_imdb_and_skips_nyaa():
    net = FakeNet().route("torrentio.strem.fun/stream/series/tt0903747:2:3",
                          fixture("torrentio/series_tt0903747_2_3.json"))
    outcomes, found = discovery.discover(discovery.for_title(breaking_bad(), 2, 3), discovery.Settings())
    assert outcomes["torrentio"] == "ok" and outcomes["nyaa"] == "skipped" and found
    assert all("nyaa" not in url and "kitsu" not in url for _, url, _ in net.calls)


def test_title_without_imdb_id_skips_torrentio():
    title = breaking_bad()
    title.imdb_id = None
    net = FakeNet()
    outcomes, found = discovery.discover(discovery.for_title(title, 2, 3), discovery.Settings())
    assert outcomes["torrentio"] == "skipped" and found == [] and net.calls == []


def test_account_torrents_found_by_title():
    torrents = [{"id": "1", "status": "downloaded", "filename": "Breaking.Bad.S02.1080p.BluRay.x265-RARBG"},
                {"id": "2", "status": "downloaded", "filename": "Better.Call.Saul.S01.1080p"}]
    assert [t["id"] for t in rdcloud.matching_torrents(torrents, breaking_bad())] == ["1"]
