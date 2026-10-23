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
    # "Bit by a Dead Bee": no language words, so check the hook with a spy on language.tabs.
    from resources.lib.sources import language
    seen = {}
    real = language.tabs

    def spy(candidates, title=None):
        seen["title"] = title
        return real(candidates, title)

    monkeypatch.setattr(language, "tabs", spy)
    Net(FakeTorBox(), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    episode = fixture("tmdb/tv_1396_season_2.json")["episodes"][2]["name"]
    assert seen["title"] == ["Breaking Bad", episode]


# -- TorBox outcomes through the watch route --------------------------------------------------------

def test_torbox_not_finished_offers_download(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", EPISODE_FILE)
    fake = FakeTorBox(cached=(), finished=False)
    Net(fake, [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    xbmcgui.select_answers.extend([0, -1])
    xbmcgui.yesno_answers.append(False)  # decline -> removed, back to list
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    assert "isn't ready on TorBox yet" in xbmcgui.yesno_calls[-1][1]
    assert fake.torrents == {}


def test_torbox_failed_torrent_is_removed_and_back_to_list(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", EPISODE_FILE)
    fake = FakeTorBox(cached=(), finished=False, failed=True)
    Net(fake, [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    xbmcgui.select_answers.extend([0, -1])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    assert "TorBox could not download this torrent" in xbmcgui.ok_calls[-1][1]
    assert fake.torrents == {} and xbmcplugin.resolved[-1][1] is False


def test_torbox_without_stream_link_is_a_bad_source(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", EPISODE_FILE)
    Net(FakeTorBox(empty_link=True), [stream(HASH, "Breaking.Bad.S02.1080p.BluRay.x264-GRP", EPISODE_FILE)])
    xbmcgui.select_answers.extend([0, -1])
    router.dispatch([BASE + "watch", "5", "?type=tv&id=1396&s=2&e=3"])
    assert "TorBox returned no stream URL" in xbmcgui.ok_calls[-1][1]
    assert xbmcplugin.resolved[-1][1] is False


def test_unknown_release_language_has_no_name():
    # Safety net: with no original language and no stated release language the heading is the generic one.
    from resources.lib import media
    from resources.lib.views import watch
    title = media.Title(media_type="tv", tmdb_id=1, title="X")
    assert watch._release_language(title, [], ["X"]) == ""


def test_quality_tabs_and_cinema_recordings(monkeypatch):
    uhd, fhd, cam = "c" * 40, "d" * 40, "e" * 40
    xbmcaddon.settings["hide_cam"] = True
    Net(FakeTorBox(cached=(uhd, fhd, cam)), [
        stream(fhd, "Dune.2021.1080p.BluRay.x264-GRP", "Dune.2021.1080p.BluRay.x264-GRP.mkv"),
        stream(uhd, "Dune.2021.2160p.WEB-DL.DV.x265-GRP", "Dune.2021.2160p.WEB-DL.DV.x265-GRP.mkv"),
        stream(cam, "Dune.2021.HDCAM.2160p-GRP", "Dune.2021.HDCAM.2160p-GRP.mkv")])
    # Quality row -> menu: All / 4K / 1080p -> 1080p tab -> back (All again) -> back (leave).
    xbmcgui.select_answers.extend([0, 2, -1, -1])
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    (all_heading, all_rows), (_, menu), (tab_heading, tab_rows), (again_heading, _) = xbmcgui.select_calls
    assert "1 cinema recordings hidden" in all_heading
    assert all_rows[0][0] == "Quality: All (2) — 4K / UHD 1 · 1080p 1"
    assert [label for label, _ in all_rows[1:3]] == ["Dune.2021.2160p.WEB-DL.DV.x265-GRP.mkv",
                                                    "Dune.2021.1080p.BluRay.x264-GRP.mkv"]
    assert "WEB-DL · DV" in all_rows[1][1] and all_rows[-1][0] == "Order: Best quality"
    assert not any("HDCAM" in label for label, _ in all_rows)
    assert menu == ["All (2)", "4K / UHD (1)", "1080p (1)"]
    assert tab_heading.endswith("· 1080p") and [r[0] for r in tab_rows][1] == "Dune.2021.1080p.BluRay.x264-GRP.mkv"
    assert len([r for r in tab_rows if r[1]]) == 1
    assert again_heading == all_heading
    assert xbmcplugin.resolved[-1][1] is False


def test_only_cinema_recordings_explains_the_setting():
    cam = "e" * 40
    xbmcaddon.settings["hide_cam"] = True
    Net(FakeTorBox(cached=(cam,)), [stream(cam, "Dune.2021.TELESYNC-GRP", "Dune.2021.TELESYNC-GRP.mkv")])
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    assert "Only cinema recordings found (1 hidden)" in xbmcgui.ok_calls[-1][1]
    assert not xbmcgui.select_calls


def test_english_and_polish_tabs_never_mix(monkeypatch):
    english, polish, multi = "c" * 40, "d" * 40, "e" * 40
    Net(FakeTorBox(cached=(english, polish, multi)), [
        stream(english, "Dune.2021.1080p.BluRay.x264-GRP", "Dune.2021.1080p.BluRay.x264-GRP.mkv"),
        stream(polish, "Dune (2021) [PL] [1080p] [Lektor PL]", "Dune.2021.PL.1080p.mkv", "🇵🇱"),
        stream(multi, "Dune.2021.Eng.Pol.2160p.BluRay.Remux-SGF", "Dune.2021.Eng.Pol.2160p.Remux.mkv", "🇬🇧 / 🇵🇱")])
    # Language row -> Polish tab -> back (English again) -> back (leave).
    xbmcgui.select_answers.extend([0, -1, -1])
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    (en_heading, en_rows), (pl_heading, pl_rows), (again_heading, _) = xbmcgui.select_calls
    assert en_rows[0][0] == "Language: English (2) — Polish 2"
    assert en_heading.endswith("· English") and "other languages hidden" not in en_heading
    en_files = [label for label, details in en_rows if details]
    assert sorted(en_files) == ["Dune.2021.1080p.BluRay.x264-GRP.mkv", "Dune.2021.Eng.Pol.2160p.Remux.mkv"]
    assert pl_rows[0][0] == "Language: Polish (2) — English 2" and pl_heading.endswith("· Polish")
    pl_files = [label for label, details in pl_rows if details]
    assert sorted(pl_files) == ["Dune.2021.Eng.Pol.2160p.Remux.mkv", "Dune.2021.PL.1080p.mkv"]
    assert again_heading == en_heading
    assert xbmcplugin.resolved[-1][1] is False


def test_only_polish_releases_open_the_polish_tab(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", "Dune.2021.PL.1080p.mkv")
    Net(FakeTorBox(), [stream(HASH, "Dune (2021) [PL] [1080p] [Lektor PL]", "Dune.2021.PL.1080p.mkv", "🇵🇱")])
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    heading, rows = xbmcgui.select_calls[-1]
    assert not any(label.startswith("Language:") for label, _ in rows)  # no other language: no row
    assert "No English audio" not in heading and rows[0][0] == "Dune.2021.PL.1080p.mkv"


def test_watch_names_the_title_for_the_source_drawer(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", MOVIE_FILE)
    Net(FakeTorBox(), [stream(HASH, "Dune.2021.2160p.WEB-DL.x265-GRP", MOVIE_FILE)])
    seen = []
    from resources.lib.views import sources
    real = sources.pick_source

    def spy(*args, **kwargs):
        seen.append((xbmcgui.window_properties.get("novaflix.source_title"),
                     xbmcgui.window_properties.get("novaflix.source_art")))
        return real(*args, **kwargs)
    monkeypatch.setattr(sources, "pick_source", spy)
    xbmcgui.select_answers.append(0)
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    title = fixture("tmdb/movie_438631.json")["title"]
    assert seen and seen[0][0] == title and seen[0][1].endswith(fixture("tmdb/movie_438631.json")["backdrop_path"])
    assert not xbmcgui.window_properties.get("novaflix.source_title")  # cleared afterwards


def test_source_drawer_counts_and_title_details(monkeypatch):
    monkeypatch.setattr(test_torbox, "FILE_NAME", MOVIE_FILE)
    Net(FakeTorBox(), [stream(HASH, "Dune.2021.2160p.WEB-DL.x265-GRP", MOVIE_FILE)])
    seen = {}

    def script(window):
        seen.update(window.properties)
        window.getControl(600).selectItem(len(window.entries) - 1)  # the source is the last row
        window.onClick(600)
    xbmcaddon.settings["novaflix_look"] = True
    xbmcgui.modal_scripts.append(script)
    router.dispatch([BASE + "watch", "5", "?type=movie&id=438631"])
    assert seen.get("count") == "1 source"
    assert seen.get("sub", "").startswith("Best quality")
    assert seen.get("meta") and "Movie" in seen["meta"]
