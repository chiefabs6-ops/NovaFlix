"""DEC-054: TorBox as the playback service.

checkcached shape is from a live read (2026-10-11): data[hash] = {name, size,
hash, files:[{id, name, short_name, size, mimetype, opensubtitles_hash}]}.
mylist torrent fields (download_finished, download_state, progress, files...)
follow TorBox integrations and are UNVERIFIED until the first live torrent.
"""

import copy
import json

import pytest
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from helpers import fixture
from resources.lib import errors, router
from resources.lib.debrid import service
from resources.lib.debrid.torbox import TorBox
from resources.lib.kodi import paths
from resources.lib.models import Candidate
from resources.lib.net import http
from resources.lib.sources import precheck
from resources.lib.storage.added import AddedTorrents
from resources.lib.storage.cache import Cache

BASE = "plugin://plugin.video.aniverse/"
KEY = "TORBOXKEY-0000-1111-2222-333344445555"
HASH = "a" * 40
FILE_NAME = "Show - S01E03.mkv"
STREAM = "https://store-001.weur.tb-cdn.st/zip/ABC?token=XYZ"
FRIEREN = fixture("anilist_media_154587.json")
ANIZIP = fixture("anizip_154587.json")


class FakeTorBox:
    def __init__(self, cached=(HASH,), finished=True, create_error=None, failed=False, empty_link=False):
        self.failed = failed
        self.empty_link = empty_link
        self.cached_hashes = set(cached)
        self.finished = finished
        self.create_error = create_error
        self.torrents = {}
        self.calls = []
        http.set_transport(self)

    def __call__(self, method, url, headers, body, timeout, context):
        assert headers.get("Authorization") == f"Bearer {KEY}"
        path = url.split("/v1/api")[-1].split("?")[0]
        query = url.split("?", 1)[1] if "?" in url else ""
        self.calls.append((method, path, query, body))

        def ok(data):
            return 200, {}, json.dumps({"success": True, "detail": "ok", "data": data}).encode()

        if path == "/torrents/checkcached":
            hashes = query.split("hash=")[1].split("&")[0].split("%2C")
            return ok({h: {"name": "x", "size": 1, "hash": h, "files": [{"id": 0, "name": f"x/{FILE_NAME}"}]}
                       for h in hashes if h in self.cached_hashes})
        if path == "/torrents/createtorrent":
            if self.create_error:
                return 200, {}, json.dumps({"success": False, "error": self.create_error, "detail": "no"}).encode()
            tid = 100 + len(self.torrents)
            self.torrents[tid] = {
                "id": tid, "hash": HASH, "name": "pack",
                "download_finished": self.finished, "download_present": self.finished,
                "download_state": "failed (no seeds)" if self.failed else "cached" if self.finished else "downloading",
                "progress": 1 if self.finished else 0.25, "download_speed": 3_000_000, "seeds": 9,
                "files": [{"id": 0, "name": "pack/Show - S01E02.mkv", "size": 1},
                          {"id": 1, "name": f"pack/{FILE_NAME}", "size": 1}],
            }
            return ok({"torrent_id": tid, "hash": HASH, "auth_id": "x"})
        if path == "/torrents/mylist":
            if "id=" in query:
                return ok(self.torrents[int(query.split("id=")[1].split("&")[0])])
            return ok(list(self.torrents.values()))
        if path == "/torrents/requestdl":
            assert f"token={KEY}" in query and "file_id=1" in query
            return ok(None if self.empty_link else STREAM)
        if path == "/torrents/controltorrent":
            data = json.loads(body)
            assert data["operation"] == "delete"
            self.torrents.pop(data["torrent_id"], None)
            return ok(None)
        raise AssertionError(f"unexpected {method} {url}")

    def count(self, path):
        return sum(1 for _, p, _, _ in self.calls if p == path)


@pytest.fixture(autouse=True)
def torbox_active():
    xbmcaddon.settings.update(playback_service=0, torbox_api_key=KEY,
                              torrentio_enabled=True, nyaa_enabled=True, dub_only=True)


def test_service_factory_picks_torbox_with_key():
    assert service.active() == service.TORBOX and service.label() == "TorBox"
    assert isinstance(service.client(), TorBox)
    xbmcaddon.settings["torbox_api_key"] = ""
    assert service.client() is None


def test_cache_lookup_marks_cached_and_uncached_without_adding():
    fake = FakeTorBox(cached=(HASH,))
    cands = [Candidate(origin="torrentio", release_name="a", info_hash=HASH),
             Candidate(origin="torrentio", release_name="b", info_hash="b" * 40)]
    results = precheck.run(TorBox(KEY), cands, None, Cache(paths.profile_dir()))
    assert results == {HASH: precheck.READY, "b" * 40: precheck.DOWNLOAD}
    assert fake.count("/torrents/createtorrent") == 0


def test_key_never_logged():
    FakeTorBox(create_error="MONTHLY_LIMIT")
    with pytest.raises(errors.AccountError):
        TorBox(KEY).add_magnet("magnet:?xt=urn:btih:" + HASH)
    from resources.lib.kodi import log
    log.info(f"debug https://api.torbox.app/v1/api/torrents/requestdl?token={KEY}&torrent_id=1 key {KEY}")
    assert KEY not in "\n".join(m for _, m in xbmc.log_records)


@pytest.mark.parametrize("code,kind", [("BAD_TOKEN", errors.AuthError), ("MONTHLY_LIMIT", errors.AccountError),
                                       ("ACTIVE_LIMIT", errors.AccountError), ("DOWNLOAD_TOO_LARGE", errors.AccountError)])
def test_torbox_errors_are_typed(code, kind):
    FakeTorBox(create_error=code)
    with pytest.raises(kind):
        TorBox(KEY).add_magnet("magnet:?xt=urn:btih:" + HASH)


def test_multipart_body_for_createtorrent():
    fake = FakeTorBox()
    TorBox(KEY).add_magnet("magnet:?xt=urn:btih:" + HASH)
    body = [b for m, p, q, b in fake.calls if p == "/torrents/createtorrent"][0].decode()
    assert 'name="magnet"' in body and HASH in body and 'name="seed"' in body


def show_net(fake):
    data = copy.deepcopy(FRIEREN)
    data["data"]["Media"].update(status="FINISHED", nextAiringEpisode=None, episodes=28)
    stream = {"name": "Torrentio\n1080p", "infoHash": HASH, "fileIdx": 1,
              "title": f"[Salieri] Show S1 [Dual Audio]\n{FILE_NAME}\n👤 9 💾 1 GB ⚙️ NyaaSi\nDubbed / Dual Audio",
              "behaviorHints": {"filename": FILE_NAME}}

    def transport(method, url, headers, body, timeout, context):
        if "graphql.anilist.co" in url:
            return 200, {}, json.dumps(data).encode()
        if "api.ani.zip" in url:
            return 200, {}, json.dumps(ANIZIP).encode()
        if "torrentio" in url:
            return 200, {}, json.dumps({"streams": [stream]}).encode()
        if "nyaa.si" in url:
            raise OSError("off")
        return fake(method, url, headers, body, timeout, context)

    http.set_transport(transport)


def test_play_through_torbox_cached_source():
    fake = FakeTorBox()
    show_net(fake)
    xbmcgui.select_answers.append(0)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert "Ready to play" in xbmcgui.select_calls[-1][1][0][1]
    handle, ok, item = xbmcplugin.resolved[-1]
    assert ok and item.path == STREAM
    payload = json.loads(xbmcgui.window_properties["aniverse.playing"])
    assert payload["cleanup_torrent"] == "100"


def test_torbox_not_finished_offers_download():
    fake = FakeTorBox(cached=(), finished=False)
    show_net(fake)
    xbmcgui.select_answers.extend([0, -1])
    xbmcgui.yesno_answers.append(False)  # decline -> removed, back to list
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert "isn't ready on TorBox yet" in xbmcgui.yesno_calls[-1][1]
    assert fake.torrents == {}


def test_torbox_failed_torrent_is_removed_and_back_to_list():
    fake = FakeTorBox(cached=(), finished=False, failed=True)
    show_net(fake)
    xbmcgui.select_answers.extend([0, -1])  # pick it, then leave the list
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert "TorBox could not download this torrent" in xbmcgui.ok_calls[-1][1]
    assert fake.torrents == {}                   # our torrent removed
    assert xbmcplugin.resolved[-1][1] is False   # nothing played


def test_torbox_without_stream_link_is_a_bad_source():
    fake = FakeTorBox(empty_link=True)
    show_net(fake)
    xbmcgui.select_answers.extend([0, -1])
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert "TorBox returned no stream URL" in xbmcgui.ok_calls[-1][1]
    assert xbmcplugin.resolved[-1][1] is False


def test_torbox_cleanup_after_start():
    from resources.lib import service_main
    fake = FakeTorBox()
    tid = TorBox(KEY).add_magnet("magnet:?xt=urn:btih:" + HASH)
    AddedTorrents(paths.profile_dir()).remember(tid, HASH)
    service_main.cleanup_after_start(paths.profile_dir(), json.dumps({"cleanup_torrent": tid}))
    assert fake.torrents == {}


def test_missing_key_prompts_settings():
    xbmcaddon.settings["torbox_api_key"] = ""
    xbmcgui.yesno_answers.append(True)
    router.dispatch([BASE + "rd/cloud", "1", ""])
    assert "TorBox API key" in xbmcgui.yesno_calls[-1][1]
    assert xbmcaddon.opened_settings == [True]
