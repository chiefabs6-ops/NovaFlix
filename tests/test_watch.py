"""The `watch` route (Plan 3, Task 6): source list and TorBox playback for TMDB movies and episodes."""

import json

import pytest
import xbmcaddon
import xbmcgui
import xbmcplugin

import test_torbox
from helpers import fixture
from resources.lib import router
from resources.lib.kodi import paths
from resources.lib.net import http
from resources.lib.storage.watching import WatchHistory
from test_torbox import HASH, KEY, STREAM, FakeTorBox

BASE = "plugin://plugin.video.novaflix/"
TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"
EPISODE_FILE = "Breaking.Bad.S02E03.1080p.BluRay.x264-GRP.mkv"
MOVIE_FILE = "Dune.2021.2160p.WEB-DL.x265-GRP.mkv"
OTHER_HASH = "b" * 40


@pytest.fixture(autouse=True)
def settings():
    xbmcaddon.settings.update(torbox_api_key=KEY, tmdb_token=TOKEN, torrentio_enabled=True, nyaa_enabled=True,
                              dub_only=True)


def stream(info_hash, release, file_name, flags=""):
    return {"name": "Torrentio\n1080p", "infoHash": info_hash, "fileIdx": 1,
            "title": f"{release}\n{file_name}\n👤 9 💾 1 GB ⚙️ 1337x" + (f"\n{flags}" if flags else ""),
            "behaviorHints": {"filename": file_name}}


class Net:
    """TMDB + Torrentio answers; TorBox calls go to the FakeTorBox."""

    def __init__(self, torbox, streams, tv=None):
        self.torbox, self.streams, self.calls = torbox, streams, []
        self.tv = tv or fixture("tmdb/tv_1396.json")
        http.set_transport(self)

    def __call__(self, method, url, headers, body, timeout, context):
        self.calls.append(url)
        if "api.torbox.app" in url:
            return self.torbox(method, url, headers, body, timeout, context)
        if "/3/tv/1396/season/2" in url:
            return 200, {}, json.dumps(fixture("tmdb/tv_1396_season_2.json")).encode()
        if "/3/tv/1396" in url:
            return 200, {}, json.dumps(self.tv).encode()
        if "/3/movie/438631" in url:
            return 200, {}, json.dumps(fixture("tmdb/movie_438631.json")).encode()
        if "torrentio.strem.fun" in url:
            return 200, {}, json.dumps({"streams": self.streams}).encode()
        raise AssertionError(f"unexpected {method} {url}")

    def count(self, part):
        return sum(1 for url in self.calls if part in url)


def test_watch_episode_plays_and_hands_off_ids_only(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", EPISODE_FILE)
    Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    xbmcgui.select_answers.append(0)
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    handle, ok, item = xbmcplugin.resolved[-1]
    assert ok and item.path == STREAM
    payload = json.loads(xbmcgui.window_properties["novaflix.playing"])
    assert {k: payload[k] for k in ("type", "id", "season", "episode")} == {"type": "tv", "id": 1396, "season": 2,
                                                                           "episode": 3}
    assert set(payload) <= {"type", "id", "season", "episode", "resume_s", "cleanup_torrent"}
    tag = item.getVideoInfoTag().values
    assert (tag["MediaType"], tag["TvShowTitle"], tag["Season"], tag["Episode"]) == ("episode", "Breaking Bad", 2, 3)
    history = WatchHistory(paths.profile_dir())
    assert history.last_choice("tv", 1396) == ("GRP", "1080p")


def test_watch_movie_plays(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", MOVIE_FILE)
    Net(FakeTorBox(), [stream(HASH, "Dune.2021.2160p.WEB-DL.x265-GRP", MOVIE_FILE)])
    xbmcgui.select_answers.append(0)
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    handle, ok, item = xbmcplugin.resolved[-1]
    assert ok and item.getVideoInfoTag().values["MediaType"] == "movie"
    payload = json.loads(xbmcgui.window_properties["novaflix.playing"])
    assert (payload["type"], payload["id"], payload["season"], payload["episode"]) == ("movie", 438631, 0, 0)


def test_title_without_imdb_id_explains():
    tv = fixture("tmdb/tv_1396.json")
    tv = dict(tv, external_ids={})
    net = Net(FakeTorBox(), [], tv=tv)
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    assert "no IMDb id" in xbmcgui.ok_calls[-1][1]
    assert xbmcplugin.resolved[-1][1] is False and net.count("torrentio") == 0


def test_other_language_releases_hidden_with_count(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", EPISODE_FILE)
    Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE),
                       stream(OTHER_HASH, "Breaking Bad Full 1080p PT-BR", "Breaking.Bad.S02E03.1080p.mkv", "🇵🇹")])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    heading, rows = xbmcgui.select_calls[-1]
    assert "1 releases in other languages hidden" in heading
    assert not any("PT-BR" in label for label, _ in rows)


def test_non_english_title_lists_original_language_releases():
    tv = dict(fixture("tmdb/tv_1396.json"), original_language="ko")
    Net(FakeTorBox(), [stream(OTHER_HASH, "Show.S02E03.1080p.WEB-DL.KOREAN", "Show.S02E03.1080p.mkv", "🇰🇷")], tv=tv)
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    heading, rows = xbmcgui.select_calls[-1]
    assert "No English audio track — Korean releases" in heading
    assert rows and "No English audio" in rows[0][1].split(" · ")[-2]  # the status stays last (gui/cards.source_row)
    assert not xbmcgui.ok_calls


def test_english_releases_still_hide_others(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", EPISODE_FILE)
    Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE),
                       stream(OTHER_HASH, "Breaking Bad Full 1080p PT-BR", "Breaking.Bad.S02E03.1080p.mkv", "🇵🇹")])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    heading, rows = xbmcgui.select_calls[-1]
    assert "No English audio" not in heading and len([r for r in rows if r[1]]) == 1


def test_cached_sources_open_without_network():
    net = Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    assert net.count("torrentio") == 1


def test_presearch_fills_cache_silently():
    from resources.lib import media
    from resources.lib.views import watch
    net = Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    title = media.title_from(fixture("tmdb/tv_1396.json"), media.TV)
    watch.presearch(title, 2, 3)
    assert net.count("torrentio") == 1 and not xbmcgui.select_calls and not xbmcgui.ok_calls
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    assert net.count("torrentio") == 1


def test_watch_url():
    from resources.lib.views import watch
    assert watch.watch_url("tv", 1396, 2, 3) == BASE + "watch?type=tv&id=1396&s=2&e=3"
    assert watch.watch_url("movie", 438631, resume=120) == BASE + "watch?type=movie&id=438631&resume=120"


def test_episode_name_is_passed_to_the_language_filter(monkeypatch):
    # "Bit by a Dead Bee": no language words, so check the hook with a spy on language.split.
    from resources.lib.sources import language
    seen = {}
    real = language.split

    def spy(candidates, wanted=language.RELEASE_LANGUAGES, title=None):
        seen["title"] = title
        return real(candidates, wanted, title)

    monkeypatch.setattr(language, "split", spy)
    Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    episode = fixture("tmdb/tv_1396_season_2.json")["episodes"][2]["name"]
    assert seen["title"] == ["Breaking Bad", episode]
