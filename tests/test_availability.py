"""Next-episode availability for TMDB titles (availability plan, Task 1)."""

import copy

import pytest
import xbmcaddon

from helpers import fixture
from resources.lib.kodi import paths
from resources.lib.metadata import library
from resources.lib.sources import availability as av
from resources.lib.storage.cache import Cache
from test_torbox import HASH, KEY, FakeTorBox
from test_watch import OTHER_HASH, TOKEN, Net, stream

EPISODE_FILE = "Breaking.Bad.S02E03.1080p.BluRay.x264-GRP.mkv"


@pytest.fixture(autouse=True)
def settings():
    xbmcaddon.settings.update(torbox_api_key=KEY, tmdb_token=TOKEN, torrentio_enabled=True)


def english():
    return [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)]


def test_english_release_is_available():
    Net(FakeTorBox(), english())
    assert av.check("tv", 1396, 2, 3).state == av.AVAILABLE
    from resources.lib.views import watch
    keys = [k for (k,) in Cache(paths.profile_dir())._conn.execute("SELECT key FROM kv")]
    assert any(k.startswith("sources:t1:tv:1396:2:3") for k in keys)


def test_only_other_language_releases_is_no_english():
    Net(FakeTorBox(), [stream(OTHER_HASH, "Breaking Bad Full 1080p PT-BR", "Breaking.Bad.S02E03.1080p.mkv", "🇵🇹")])
    assert av.check("tv", 1396, 2, 3).state == av.NO_ENGLISH


def test_nothing_found_is_unavailable():
    Net(FakeTorBox(), [])
    assert av.check("tv", 1396, 2, 3).state == av.UNAVAILABLE


def test_provider_failure_is_unknown_and_remembered():
    class Failing(Net):
        def __call__(self, method, url, headers, body, timeout, context):
            if "torrentio" in url:
                self.calls.append(url)
                return 500, {}, b"{}"
            return super().__call__(method, url, headers, body, timeout, context)
    net = Failing(FakeTorBox(), [])
    assert av.check("tv", 1396, 2, 3).state == av.UNKNOWN
    before = net.count("torrentio")
    assert av.check("tv", 1396, 2, 3).state == av.UNKNOWN and net.count("torrentio") == before


def test_future_episode_is_upcoming_with_its_date(monkeypatch):
    first_s2 = fixture("tmdb/tv_1396_season_2.json")["episodes"][0]["air_date"]
    monkeypatch.setattr(library, "_today", lambda: "2009-01-01")
    net = Net(FakeTorBox(), english())
    result = av.check("tv", 1396, 2, 1)
    assert (result.state, result.air_date) == (av.UPCOMING, first_s2) and net.count("torrentio") == 0


def test_saved_sources_need_no_network():
    from resources.lib import media
    from resources.lib.views import watch
    Net(FakeTorBox(), english())
    title = media.title_from(fixture("tmdb/tv_1396.json"), media.TV)
    library.Library().title("tv", 1396)                     # title page / continue row saved it
    library.Library().season_episodes(title, 2)
    watch.presearch(title, 2, 3)
    net = Net(FakeTorBox(), english())
    net.calls.clear()
    assert av.cached("tv", 1396, 2, 3).state == av.AVAILABLE and net.calls == []


def test_cached_without_saved_data_is_none():
    Net(FakeTorBox(), english())
    assert av.cached("tv", 1396, 2, 3) is None


def test_movie_released_is_checked_and_future_movie_upcoming(monkeypatch):
    Net(FakeTorBox(), [stream(HASH, "Dune.2021.2160p.WEB-DL.x265-GRP", "Dune.2021.2160p.WEB-DL.x265-GRP.mkv")])
    assert av.check("movie", 438631, 0, 0).state == av.AVAILABLE
    monkeypatch.setattr(library, "_today", lambda: "2020-01-01")
    Cache(paths.profile_dir()).clear()
    result = av.check("movie", 438631, 0, 0)
    assert result.state == av.UPCOMING and result.air_date == fixture("tmdb/movie_438631.json")["release_date"]


def test_check_never_raises():
    class Broken(Net):
        def __call__(self, method, url, headers, body, timeout, context):
            if "themoviedb" in url:
                return 500, {}, b"{}"
            return super().__call__(method, url, headers, body, timeout, context)
    Broken(FakeTorBox(), english())
    assert av.check("tv", 1396, 2, 3).state == av.UNKNOWN


# -- review fixes --------------------------------------------------------------------------------

def test_a_failing_saved_read_gives_no_results_not_an_error(monkeypatch):
    import sqlite3
    Net(FakeTorBox(), english())
    library.Library().title("tv", 1396)
    monkeypatch.setattr(Cache, "get", lambda self, key, default=None: (_ for _ in ()).throw(
        sqlite3.OperationalError("database is locked")))
    assert av.cached_episodes("tv", 1396, 2, [1, 2, 3]) == {}


def test_title_without_imdb_id_is_unavailable_without_searching():
    tv = dict(fixture("tmdb/tv_1396.json"), external_ids={})
    net = Net(FakeTorBox(), english(), tv=tv)
    assert av.check("tv", 1396, 2, 3).state == av.UNAVAILABLE and net.count("torrentio") == 0


def test_settings_are_read_once_for_a_whole_season(monkeypatch):
    from resources.lib import media
    from resources.lib.views import sources, watch
    Net(FakeTorBox(), english())
    title = library.Library().title("tv", 1396)
    library.Library().season_episodes(title, 2)
    for episode in (1, 2, 3):
        watch.presearch(title, 2, episode)
    reads = []
    real = sources._settings
    monkeypatch.setattr(sources, "_settings", lambda: reads.append(1) or real())
    assert len(av.cached_episodes("tv", 1396, 2, [1, 2, 3])) == 3 and len(reads) == 1
