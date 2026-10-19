"""M7: resolving a chosen source and handing it to Kodi.

A scripted fake Real-Debrid keeps torrent state so the add/select/info/
unrestrict sequence behaves like the API docs describe.
"""

import copy
import json

import pytest
import xbmcgui
import xbmcplugin

from helpers import fixture
from resources.lib import router
from resources.lib.debrid import auth, resolver
from resources.lib.debrid.realdebrid import RealDebrid
from resources.lib.debrid.resolver import AmbiguousFile, BadSource, NotReady, Resolver
from resources.lib.kodi import paths
from resources.lib.metadata.anilist import to_show
from resources.lib.models import Candidate
from resources.lib.net import http
from resources.lib.sources.discovery import Wanted
from resources.lib.storage import db
from resources.lib.storage.added import AddedTorrents
from resources.lib.views import play

BASE = "plugin://plugin.video.novaflix/"


@pytest.fixture(autouse=True)
def use_real_debrid(monkeypatch):
    """These tests drive the resolver through the Real-Debrid-shaped fake client (replaced
    with a TorBox fake when Plan 3 rewrites them); NovaFlix itself only offers TorBox."""
    from resources.lib.debrid import service
    from resources.lib.debrid.realdebrid import RealDebrid

    def client(directory=None):
        store = auth.TokenStore(directory or paths.profile_dir())
        return RealDebrid(store) if store.connected else None

    monkeypatch.setattr(service, "client", client)
FRIEREN = fixture("anilist_media_154587.json")
ANIZIP = fixture("anizip_154587.json")
TORRENTIO = fixture("torrentio_46474_3.json")
HASH = "a" * 40
STREAM = "https://xyz.download.real-debrid.com/d/ABCDEF/ep03.mkv"
FILES = [
    {"id": 1, "path": "/Show - S01E02.mkv", "bytes": 500, "selected": 0},
    {"id": 2, "path": "/Show - S01E03.mkv", "bytes": 500, "selected": 0},
    {"id": 3, "path": "/NCOP.mkv", "bytes": 50, "selected": 0},
]


class FakeRD:
    """Stateful Real-Debrid: statuses advance as the scenario says."""

    def __init__(self, after_select="downloaded", existing=None, conversion=0, unrestrict_error=None, add_status=None):
        self.torrents = {}
        self.calls = []
        self.after_select = after_select
        self.conversion = conversion
        self.unrestrict_error = unrestrict_error
        self.progress_steps = []
        self.add_status = add_status
        for t in existing or []:
            self.torrents[t["id"]] = t
        http.set_transport(self)

    def __call__(self, method, url, headers, body, timeout, context):
        body = body.decode() if body else ""
        path = url.split("/rest/1.0")[-1].split("?")[0]
        self.calls.append((method, path, body))

        def ok(data, status=200):
            return status, {}, json.dumps(data).encode() if data is not None else b""

        if method == "GET" and path == "/torrents":
            return ok([{"id": k, "hash": t["hash"], "status": t["status"]} for k, t in self.torrents.items()])
        if method == "POST" and path == "/torrents/addMagnet" and self.add_status:
            if self.add_status == 429:
                return ok({"error": "too_many_requests", "error_code": 34}, 429)
            return ok({"error": "infringing_file", "error_code": 35}, self.add_status)
        if method == "POST" and path == "/torrents/addMagnet":
            tid = f"T{len(self.torrents) + 1}"
            self.torrents[tid] = {"id": tid, "hash": HASH, "status": "magnet_conversion" if self.conversion else "waiting_files_selection",
                                  "files": copy.deepcopy(FILES), "links": [], "progress": 0}
            return ok({"id": tid, "uri": "x"}, 201)
        if method == "GET" and path.startswith("/torrents/info/"):
            t = self.torrents[path.rsplit("/", 1)[1]]
            if t["status"] == "magnet_conversion":
                self.conversion -= 1
                if self.conversion <= 0:
                    t["status"] = "waiting_files_selection"
            elif t["status"] in ("downloading", "queued") and self.progress_steps:
                t["progress"], t["status"] = self.progress_steps.pop(0)
                if t["status"] == "downloaded":
                    t["links"] = ["https://real-debrid.com/d/LINK"]
            return ok(dict(t, seeders=7, speed=2_000_000))
        if method == "POST" and path.startswith("/torrents/selectFiles/"):
            t = self.torrents[path.rsplit("/", 1)[1]]
            ids = body.split("=", 1)[1].split("%2C")
            for f in t["files"]:
                f["selected"] = 1 if str(f["id"]) in ids else 0
            t["status"] = self.after_select
            if self.after_select == "downloaded":
                t["links"] = ["https://real-debrid.com/d/LINK"]
            return ok(None, 204)
        if method == "DELETE" and path.startswith("/torrents/delete/"):
            self.torrents.pop(path.rsplit("/", 1)[1], None)
            return ok(None, 204)
        if method == "POST" and path == "/unrestrict/link":
            if self.unrestrict_error:
                return ok({"error": "x", "error_code": self.unrestrict_error}, 503)
            return ok({"download": STREAM, "filename": "Show - S01E03.mkv"})
        raise AssertionError(f"unexpected {method} {url}")

    def count(self, method, prefix):
        return sum(1 for m, p, _ in self.calls if m == method and p.startswith(prefix))


@pytest.fixture(autouse=True)
def connected(monkeypatch):
    monkeypatch.setattr(resolver, "_sleep", lambda s: None)
    auth.TokenStore(paths.profile_dir()).save(client_id="CID000001", client_secret="SECRET000001",
                                              access_token="ACCESS0000000001", refresh_token="REFRESH000001", expires_at=4e9)


def rd():
    return RealDebrid(auth.TokenStore(paths.profile_dir()))


def wanted():
    return Wanted(show=to_show(FRIEREN["data"]["Media"]), number=3, absolute=3, tvdb=(1, 3), kitsu_id=46474)


def cand(**kw):
    base = dict(origin="torrentio", release_name="[G] Show S01 batch", info_hash=HASH, file_name="Show - S01E03.mkv")
    base.update(kw)
    return Candidate(**base)


def added():
    return AddedTorrents(paths.profile_dir())


# -- resolver ------------------------------------------------------------------

def test_cached_source_selects_only_episode_file_and_unrestricts():
    fake = FakeRD()
    url, name = Resolver(rd(), added()).resolve(cand(), wanted())
    assert url == STREAM
    select_body = [b for m, p, b in fake.calls if p.startswith("/torrents/selectFiles")][0]
    assert select_body == "files=2"
    assert added().is_ours("T1")


def test_existing_account_torrent_is_reused_not_readded():
    existing = {"id": "OWN", "hash": HASH, "status": "downloaded", "links": ["https://real-debrid.com/d/L1", "https://real-debrid.com/d/L2"],
                "files": [{"id": 1, "path": "/Show - S01E02.mkv", "selected": 1}, {"id": 2, "path": "/Show - S01E03.mkv", "selected": 1}]}
    fake = FakeRD(existing=[existing])
    url, _ = Resolver(rd(), added()).resolve(cand(), wanted())
    assert url == STREAM
    assert fake.count("POST", "/torrents/addMagnet") == 0
    assert [b for m, p, b in fake.calls if p == "/unrestrict/link"][0].endswith("L2")
    assert not added().is_ours("OWN")


def test_not_ready_raises_with_torrent_id():
    FakeRD(after_select="downloading")
    with pytest.raises(NotReady) as info:
        Resolver(rd(), added()).resolve(cand(), wanted())
    assert info.value.torrent_id == "T1"


def test_broken_torrent_is_removed_and_reported():
    fake = FakeRD(after_select="dead")
    with pytest.raises(BadSource):
        Resolver(rd(), added()).resolve(cand(), wanted())
    assert fake.count("DELETE", "/torrents/delete/T1") == 1
    assert not added().is_ours("T1")


def test_magnet_conversion_waits_then_continues():
    FakeRD(conversion=2)
    url, _ = Resolver(rd(), added()).resolve(cand(), wanted())
    assert url == STREAM


def test_magnet_conversion_timeout_is_bad_source(monkeypatch):
    clock = iter(range(0, 1000, 20))
    monkeypatch.setattr(resolver, "_clock", lambda: next(clock))
    fake = FakeRD(conversion=999)
    with pytest.raises(BadSource):
        Resolver(rd(), added()).resolve(cand(), wanted())
    assert fake.count("DELETE", "/torrents/delete/") == 1


def test_ambiguous_file_asks_owner_then_uses_choice():
    FakeRD()
    c = cand(file_name=None, file_idx=None)
    w = wanted()
    w.number, w.absolute, w.tvdb = 9, None, None  # nothing matches -> ambiguous
    res = Resolver(rd(), added())
    with pytest.raises(AmbiguousFile) as info:
        res.resolve(c, w)
    assert [path for _, path in info.value.files] == ["Show - S01E02.mkv", "Show - S01E03.mkv"]
    url, _ = res.resolve(c, w, chosen_file_id=2, torrent_id=info.value.torrent_id)
    assert url == STREAM


def test_infringing_file_is_bad_source():
    FakeRD(unrestrict_error=35)
    with pytest.raises(BadSource):
        Resolver(rd(), added()).resolve(cand(), wanted())


def test_account_file_resolves_without_adding():
    existing = {"id": "OWN", "hash": "b" * 40, "status": "downloaded", "links": ["https://real-debrid.com/d/L1"],
                "files": [{"id": 4, "path": "/Movie.mkv", "selected": 1}]}
    fake = FakeRD(existing=[existing])
    url, _ = Resolver(rd(), added()).resolve(Candidate(origin="rdcloud", release_name="", rd_torrent_id="OWN", rd_file_id=4), None)
    assert url == STREAM and fake.count("POST", "/torrents/addMagnet") == 0


# -- download flow (DEC-020) -------------------------------------------------------------

def test_download_then_play_updates_progress():
    fake = FakeRD(after_select="downloading")
    fake.progress_steps = [(10, "downloading"), (40, "downloading"), (100, "downloaded")]
    res = Resolver(rd(), added())
    with pytest.raises(NotReady):
        res.resolve(cand(), wanted())
    result = play.download_and_wait(res, "T1", cand(), wanted(), "Frieren", wait=lambda s: False)
    assert result[0] == STREAM
    assert "40% downloaded" in xbmcgui.progress_dialogs[-1].last_update[1]


def test_cancel_download_keep():
    fake = FakeRD(after_select="downloading")
    fake.progress_steps = [(10, "downloading")] * 3
    res = Resolver(rd(), added())
    with pytest.raises(NotReady):
        res.resolve(cand(), wanted())
    xbmcgui.yesno_answers.append(True)  # keep
    assert play.download_and_wait(res, "T1", cand(), wanted(), "F", wait=lambda s: True) == play.STOP
    assert added().is_kept("T1") and "T1" in fake.torrents


def test_cancel_download_remove():
    fake = FakeRD(after_select="downloading")
    fake.progress_steps = [(10, "downloading")] * 3
    res = Resolver(rd(), added())
    with pytest.raises(NotReady):
        res.resolve(cand(), wanted())
    xbmcgui.yesno_answers.append(False)  # remove
    play.download_and_wait(res, "T1", cand(), wanted(), "F", wait=lambda s: True)
    assert "T1" not in fake.torrents and not added().is_ours("T1")


def test_stall_prompt_after_ten_minutes(monkeypatch):
    fake = FakeRD(after_select="downloading")
    fake.progress_steps = [(5, "downloading")] * 10
    res = Resolver(rd(), added())
    with pytest.raises(NotReady):
        res.resolve(cand(), wanted())
    clock = iter([0, 0, 700, 700, 700, 700])
    monkeypatch.setattr(play, "_clock", lambda: next(clock))
    xbmcgui.select_answers.append(1)  # keep for later
    assert play.download_and_wait(res, "T1", cand(), wanted(), "F", wait=lambda s: False) == play.STOP
    assert "No progress for 10 minutes" in xbmcgui.select_calls[-1][0]
    assert added().is_kept("T1")


# -- full route ---------------------------------------------------------------------------

def precheck_says(monkeypatch, status):
    """Pretend the pre-check already ran with this result (tests the play step alone)."""
    from resources.lib.sources import precheck
    from resources.lib.views import sources

    def fake(rd, shown, wanted, cache, needed, heading):
        for c in shown:
            if c.info_hash and cache.get(precheck.cache_key(c.info_hash)) is None:
                cache.set(precheck.cache_key(c.info_hash), status, 3600)
    monkeypatch.setattr(sources, "_precheck", fake)


def show_net(fake):
    data = copy.deepcopy(FRIEREN)
    data["data"]["Media"].update(status="FINISHED", nextAiringEpisode=None, episodes=28)
    inner = fake

    def transport(method, url, headers, body, timeout, context):
        if "graphql.anilist.co" in url:
            return 200, {}, json.dumps(data).encode()
        if "api.ani.zip" in url:
            return 200, {}, json.dumps(ANIZIP).encode()
        if "torrentio" in url:
            return 200, {}, json.dumps({"streams": [{"name": "Torrentio\n1080p", "infoHash": HASH, "fileIdx": 1,
                                                     "title": "[Salieri] Show S1 [Dual Audio]\nShow - S01E03.mkv\n👤 9 💾 1 GB ⚙️ NyaaSi\nDubbed / Dual Audio",
                                                     "behaviorHints": {"filename": "Show - S01E03.mkv"}}]}).encode()
        if "nyaa.si" in url:
            raise OSError("off")
        return inner(method, url, headers, body, timeout, context)

    http.set_transport(transport)


def test_play_route_resolves_into_kodi_and_hands_off_ids_only():
    fake = FakeRD()
    fake.precheck_ok = True
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    xbmcgui.select_answers.append(0)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    handle, ok, item = xbmcplugin.resolved[-1]
    assert handle == 5 and ok and item.path == STREAM
    payload = json.loads(xbmcgui.window_properties[play.HANDOFF_PROPERTY])
    assert payload == {"anilist_id": 154587, "episode": 3, "mal_id": 52991, "cleanup_torrent": "T1"}
    # SEC-15: IDs only — every value a plain integer or ID string, no URL or token.
    assert all(isinstance(v, int) or str(v).isalnum() for v in payload.values())
    assert "http" not in json.dumps(payload) and "real-debrid" not in json.dumps(payload)
    conn = db.open_user_db(paths.profile_dir())
    assert conn.execute("SELECT last_release_group, last_episode_played FROM show_prefs").fetchone() == ("Salieri", 3)


def test_bad_source_returns_to_list_then_cancel_resolves_false(monkeypatch):
    precheck_says(monkeypatch, "ready")  # checked fine earlier, refused at play time
    fake = FakeRD(after_select="dead")
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    xbmcgui.select_answers.extend([0, -1])
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert len(xbmcgui.select_calls) == 2  # the list came back after the failure
    assert "can't be played" in xbmcgui.ok_calls[-1][1]
    assert xbmcplugin.resolved[-1][1] is False


def test_declined_download_removes_torrent_and_returns_to_list(monkeypatch):
    precheck_says(monkeypatch, "download")
    fake = FakeRD(after_select="downloading")
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    xbmcgui.select_answers.extend([0, -1])
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert "isn't ready on TorBox yet" in xbmcgui.yesno_calls[-1][1]
    assert fake.torrents == {}
    assert xbmcplugin.resolved[-1][1] is False


def test_play_route_crash_still_answers_kodi(monkeypatch):
    from resources.lib.views import sources
    monkeypatch.setattr(sources, "_choose", lambda req: (_ for _ in ()).throw(RuntimeError("boom")))
    router.dispatch([BASE + "play", "5", "?id=1&ep=1"])
    assert xbmcplugin.resolved[-1][1] is False
    assert xbmcplugin.end_calls == []


# -- service cleanup (DEC-019) ---------------------------------------------------------------

def test_service_removes_our_torrent_after_start():
    from resources.lib import service_main
    fake = FakeRD()
    fake.torrents["T9"] = {"id": "T9", "hash": HASH, "status": "downloaded"}
    added().remember("T9", HASH)
    service_main.cleanup_after_start(paths.profile_dir(), json.dumps({"cleanup_torrent": "T9"}))
    assert "T9" not in fake.torrents and not added().is_ours("T9")


def test_service_never_removes_owner_or_kept_torrents():
    from resources.lib import service_main
    fake = FakeRD()
    fake.torrents["OWN"] = {"id": "OWN", "hash": HASH, "status": "downloaded"}
    fake.torrents["KEEP"] = {"id": "KEEP", "hash": HASH, "status": "downloaded"}
    added().remember("KEEP", HASH)
    added().keep("KEEP")
    service_main.cleanup_after_start(paths.profile_dir(), json.dumps({"cleanup_torrent": "OWN"}))
    service_main.cleanup_after_start(paths.profile_dir(), json.dumps({"cleanup_torrent": "KEEP"}))
    assert set(fake.torrents) == {"OWN", "KEEP"}


def test_blocked_torrent_451_is_bad_source_not_network_error():
    FakeRD(add_status=451)
    with pytest.raises(BadSource) as info:
        Resolver(rd(), added()).resolve(cand(), wanted())
    assert "blocked" in str(info.value)


def test_blocked_torrent_returns_to_list_with_clear_message(monkeypatch):
    precheck_says(monkeypatch, "ready")  # pre-check passed, then RD refused at play time
    fake = FakeRD(add_status=451)
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    xbmcgui.select_answers.extend([0, -1])
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert "blocked" in xbmcgui.ok_calls[-1][1]
    assert not any("internet" in n[1] for n in xbmcgui.notifications)
    # Second list: the refused source is now hidden behind "Show blocked sources".
    assert xbmcgui.select_calls[-1][1][-1][0] == "Show blocked sources (1)"



# -- pre-check (DEC-053) ----------------------------------------------------------------

def test_precheck_hides_blocked_and_offers_show_blocked():
    fake = FakeRD(add_status=451)
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    heading, rows = xbmcgui.select_calls[-1]
    assert "No playable sources found yet" in heading
    assert rows == [("Show blocked sources (1)", "")]
    assert fake.torrents == {}


def test_precheck_marks_ready_and_cleans_up():
    fake = FakeRD()
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    rows = xbmcgui.select_calls[-1][1]
    assert "Ready to play" in rows[0][1]
    assert fake.torrents == {}  # the check removed what it added
    assert fake.count("DELETE", "/torrents/delete/") == 1


def test_precheck_results_are_cached():
    fake = FakeRD()
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    adds = fake.count("POST", "/torrents/addMagnet")
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3"])
    assert fake.count("POST", "/torrents/addMagnet") == adds


def test_precheck_stops_after_two_playable():
    from resources.lib.sources import precheck
    from resources.lib.storage.cache import Cache
    fake = FakeRD()
    many = [cand(info_hash=f"{i:040x}") for i in range(1, 9)]
    precheck.CONCURRENCY_BACKUP = precheck.CONCURRENCY
    precheck.CONCURRENCY = 1
    try:
        results = precheck.run(rd(), many, wanted(), Cache(paths.profile_dir()), needed=2)
    finally:
        precheck.CONCURRENCY = precheck.CONCURRENCY_BACKUP
    assert len(results) == 2 and fake.count("POST", "/torrents/addMagnet") == 2


def test_precheck_never_deletes_owner_torrents():
    from resources.lib.sources import precheck
    from resources.lib.storage.cache import Cache
    existing = {"id": "OWN", "hash": HASH, "status": "downloaded", "files": [], "links": []}
    fake = FakeRD(existing=[existing])
    results = precheck.run(rd(), [cand()], wanted(), Cache(paths.profile_dir()))
    assert results == {HASH: "ready"} and "OWN" in fake.torrents
    assert fake.count("DELETE", "/torrents/delete/") == 0


def test_precheck_stops_on_rate_limit():
    from resources.lib.sources import precheck
    from resources.lib.storage.cache import Cache
    fake = FakeRD(add_status=429)
    results = precheck.run(rd(), [cand(info_hash=f"{i:040x}") for i in range(1, 6)], wanted(), Cache(paths.profile_dir()))
    assert results == {}


def test_play_route_passes_resume_position_as_number():
    fake = FakeRD()
    fake.precheck_ok = True
    show_net(fake)
    import xbmcaddon
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=True)
    xbmcgui.select_answers.append(0)
    router.dispatch([BASE + "play", "5", "?id=154587&ep=3&resume=754"])
    payload = json.loads(xbmcgui.window_properties[play.HANDOFF_PROPERTY])
    assert payload["resume_s"] == 754 and all(isinstance(v, int) or str(v).isalnum() for v in payload.values())
