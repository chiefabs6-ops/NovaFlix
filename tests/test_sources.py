"""M6: providers, ranking, discovery and the source-list screen."""

import copy
import json
import os
import re

import pytest
import xbmcaddon
import xbmcgui
import xbmcplugin

from helpers import FIXTURES, FakeNet, fixture
from resources.lib import router
from resources.lib.debrid import auth
from resources.lib.kodi import paths
from resources.lib.metadata.anilist import to_show
from resources.lib.models import Candidate
from resources.lib.sources import discovery, matcher, nyaa, ranking, rdcloud, torrentio

BASE = "plugin://plugin.video.aniverse/"


@pytest.fixture(autouse=True)
def use_real_debrid():
    """These tests exercise the Real-Debrid client; TorBox has its own tests."""
    import xbmcaddon
    xbmcaddon.settings["playback_service"] = 1
TORRENTIO = fixture("torrentio_46474_3.json")
FRIEREN = fixture("anilist_media_154587.json")
ANIZIP = fixture("anizip_154587.json")
with open(os.path.join(FIXTURES, "nyaa_frieren_03.xml"), encoding="utf-8") as _f:
    NYAA_XML = _f.read()
RD_TOKEN = "RDACCESSTOKEN00000000000000000001"


def frieren():
    return to_show(FRIEREN["data"]["Media"])


# -- Torrentio ------------------------------------------------------------------

def test_torrentio_urls():
    assert torrentio.url(None, 46474, 3, False) == "https://torrentio.strem.fun/stream/series/kitsu:46474:3.json"
    assert torrentio.url("https://my.host/", 5, 1, True) == "https://my.host/stream/movie/kitsu:5.json"


def test_torrentio_parses_real_streams():
    found = torrentio.parse_streams(TORRENTIO, 3, 3, (1, 3))
    assert found and all(c.origin == "torrentio" and len(c.info_hash) == 40 for c in found)
    first = found[0]
    assert first.release_group == "Feibanyama"
    assert first.file_name.endswith("- 03 [IQIYI WebRip 2160p HEVC OPUS Multi-Subs].mkv")
    assert first.file_idx == 2 and first.seeders == 86 and first.site == "NyaaSi"
    assert first.resolution == "2160p" and first.codec == "HEVC"
    assert abs(first.size_bytes - 1.43e9) < 1e7
    assert first.audio is None  # "Multi Subs" is not an English dub


def test_torrentio_dub_evidence():
    found = torrentio.parse_streams(TORRENTIO, 3, 3, (1, 3))
    by_hash = {s["infoHash"]: s["title"] for s in TORRENTIO["streams"]}
    for c in found:
        languages = by_hash[c.info_hash].split("\n")[-1]
        if matcher.other_language_only(c.release_name):
            assert c.audio is None  # e.g. [DUAL JAP PT-BR]: the flag is from English subtitles
        elif "🇬🇧" in languages and "Dubbed" in languages:
            assert c.audio == "dub"
        elif "Dubbed" not in languages and not re.search(r"dual|dub", c.release_name, re.I):
            assert c.audio is None
        elif "Dual Audio" in languages and "Dub" not in c.release_name:
            assert c.audio == "dual"
    assert any(c.release_group == "Salieri" and c.audio == "dual" for c in found)  # "Dubbed / Dual Audio", no flag
    assert any(c.release_group == "Rapta" and c.audio == "dub" for c in found)     # 🇬🇧 flag


def test_torrentio_drops_other_episodes_and_bad_hashes():
    data = {"streams": [
        {"name": "Torrentio\n1080p", "infoHash": "a" * 40, "fileIdx": 1,
         "title": "[G] Show - 04 (1080p)\n👤 5 💾 1 GB ⚙️ NyaaSi", "behaviorHints": {"filename": "[G] Show - 04 (1080p).mkv"}},
        {"name": "Torrentio\n1080p", "infoHash": "not-a-hash", "title": "[G] Show - 03"},
        {"name": "Torrentio\n1080p", "infoHash": "b" * 40, "title": "[G] Show Batch\n👤 5 💾 1 GB ⚙️ NyaaSi"},
    ]}
    found = torrentio.parse_streams(data, 3)
    assert [c.info_hash for c in found] == ["b" * 40]
    assert found[0].match == "best_guess"


# -- Nyaa ---------------------------------------------------------------------------

def test_nyaa_query():
    assert nyaa.query_for("Sousou no Frieren", 3, False) == "Sousou no Frieren 03"
    assert nyaa.query_for("Movie", 1, True) == "Movie"


def test_nyaa_parses_real_rss_and_drops_wrong_episodes():
    found = nyaa.parse_rss(NYAA_XML, 3, 3, (1, 3))
    assert all(c.origin == "nyaa" and len(c.info_hash) == 40 for c in found)
    assert not any("S2 - 08" in c.release_name for c in found)
    assert not any("S02E05" in c.release_name for c in found)
    for c in found:
        assert c.match in ("exact", "best_guess")


# -- RD account ------------------------------------------------------------------------

TORRENTS = [
    {"id": "T1", "filename": "[EMBER] Frieren - Beyond Journey's End (Season 1) [1080p Dual Audio]", "status": "downloaded", "bytes": 9e9},
    {"id": "T2", "filename": "Some Other Show S01", "status": "downloaded", "bytes": 5e9},
    {"id": "T3", "filename": "Sousou no Frieren 1080p", "status": "downloading", "bytes": 1e9},
]
INFO_T1 = {"id": "T1", "hash": "c" * 40, "filename": TORRENTS[0]["filename"], "files": [
    {"id": 1, "path": "/S01E02-Journey.mkv", "bytes": 600e6, "selected": 1},
    {"id": 2, "path": "/S01E03-Killing Magic.mkv", "bytes": 650e6, "selected": 1},
    {"id": 3, "path": "/S01E04-Other.mkv", "bytes": 640e6, "selected": 0},
    {"id": 4, "path": "/NCOP.mkv", "bytes": 90e6, "selected": 1},
    {"id": 5, "path": "/readme.txt", "bytes": 1e3, "selected": 1},
]}


def test_rdcloud_matches_downloaded_torrents_by_title():
    hits = rdcloud.matching_torrents(TORRENTS, frieren())
    assert [t["id"] for t in hits] == ["T1"]


def test_rdcloud_finds_episode_file():
    found = rdcloud.candidates_from_info(INFO_T1, 3, 3, (1, 3))
    assert len(found) == 1
    c = found[0]
    assert c.rd_torrent_id == "T1" and c.rd_file_id == 2 and c.status == "ready"
    assert c.audio == "dual" and c.resolution == "1080p"


def test_rdcloud_ignores_unselected_files():
    assert rdcloud.candidates_from_info(INFO_T1, 4, 4, (1, 4)) == []


def test_rdcloud_movie_takes_largest_video():
    info = {"id": "M", "filename": "Movie (2023)", "files": [
        {"id": 1, "path": "/Movie.mkv", "bytes": 4e9, "selected": 1},
        {"id": 2, "path": "/Movie Trailer.mkv", "bytes": 1e8, "selected": 1}]}
    found = rdcloud.candidates_from_info(info, 1, is_movie=True)
    assert [c.rd_file_id for c in found] == [1]


# -- ranking ---------------------------------------------------------------------------

def cand(origin="torrentio", h=None, res=None, size=None, codec=None, audio=None, group=None, **kw):
    return Candidate(origin=origin, release_name=f"{group or 'x'} {res}", info_hash=h, resolution=res,
                     size_bytes=size, codec=codec, audio=audio, release_group=group, **kw)


def test_dedupe_prefers_ready_account_copy():
    rd = cand("rdcloud", h="d" * 40, rd_torrent_id="T", rd_file_id=1, status="ready")
    tio = cand("torrentio", h="d" * 40)
    ny = cand("nyaa", h="d" * 40)
    assert ranking.dedupe([ny, tio, rd]) == [rd]


def test_sort_groups_then_resolution_then_size():
    items = [cand("nyaa", "1" * 40, "2160p", 9), cand("torrentio", "2" * 40, "720p", 5),
             cand("torrentio", "3" * 40, "1080p", 1), cand("torrentio", "4" * 40, "1080p", 3),
             cand("rdcloud", "5" * 40, "480p", 1, rd_torrent_id="T", rd_file_id=1)]
    shown = ranking.build(items, ranking.Filters(), dub_only=False).shown
    assert [c.info_hash[0] for c in shown] == ["5", "4", "3", "2", "1"]


def test_filters_only_act_on_known_values():
    items = [cand(h="1" * 40, res="480p"), cand(h="2" * 40, res=None), cand(h="3" * 40, res="1080p", size=30e9),
             cand(h="4" * 40, res="1080p", codec="HEVC"), cand(h="5" * 40, res="1080p")]
    result = ranking.build(items, ranking.Filters("720p", 20, ["HEVC"]), dub_only=False)
    assert sorted(c.info_hash[0] for c in result.shown) == ["2", "5"]
    assert result.hidden_by_filters == 3


def test_dub_only_view_counts_hidden():
    items = [cand(h="1" * 40, audio="dub"), cand(h="2" * 40, audio="dual"), cand(h="3" * 40, audio=None)]
    result = ranking.build(items, ranking.Filters(), dub_only=True)
    assert len(result.shown) == 2 and result.hidden_non_dub == 1


def test_same_as_last_episode_is_pinned_within_its_group():
    items = [cand(h="1" * 40, res="2160p", group="Other"), cand(h="2" * 40, res="1080p", group="Salieri")]
    shown = ranking.build(items, ranking.Filters(), False, last_group="salieri", last_resolution="1080p").shown
    assert shown[0].release_group == "Salieri" and shown[0].pinned


# -- discovery ------------------------------------------------------------------------

def wanted(kitsu=46474):
    return discovery.Wanted(show=frieren(), number=3, absolute=3, tvdb=(1, 3), kitsu_id=kitsu)


def test_discovery_isolates_provider_failures():
    FakeNet().route("torrentio.strem.fun", TORRENTIO).route("nyaa.si", OSError("down"))
    outcomes, found = discovery.discover(wanted(), discovery.Settings())
    assert outcomes["torrentio"] == "ok" and outcomes["nyaa"] == "failed" and outcomes["rdcloud"] == "skipped"
    assert found and all(c.origin == "torrentio" for c in found)


def test_discovery_skips_torrentio_without_kitsu_id():
    net = FakeNet().route("nyaa.si", {"x": 1})
    from resources.lib.net import http

    class Rss:
        def __call__(self, method, url, headers, body, timeout, context):
            return 200, {}, NYAA_XML.encode()
    http.set_transport(Rss())
    outcomes, _ = discovery.discover(wanted(kitsu=None), discovery.Settings())
    assert outcomes["torrentio"] == "skipped"


def test_real_debrid_token_never_sent_to_search_providers():
    calls = []
    from resources.lib.net import http

    def transport(method, url, headers, body, timeout, context):
        calls.append((url, json.dumps(headers)))
        if "torrentio" in url:
            return 200, {}, json.dumps(TORRENTIO).encode()
        if "nyaa.si" in url:
            return 200, {}, NYAA_XML.encode()
        if "/torrents/info/" in url:
            return 200, {}, json.dumps(INFO_T1).encode()
        if "/torrents" in url:
            return 200, {}, json.dumps(TORRENTS).encode()
        raise AssertionError(url)

    http.set_transport(transport)
    store = auth.TokenStore(paths.profile_dir())
    store.save(client_id="CID000001", client_secret="SECRET000001", access_token=RD_TOKEN,
               refresh_token="REFRESH000001", expires_at=4e9)
    from resources.lib.debrid.realdebrid import RealDebrid
    outcomes, found = discovery.discover(wanted(), discovery.Settings(), RealDebrid(store))
    assert outcomes["rdcloud"] == "ok"
    for url, headers in calls:
        if "real-debrid.com" not in url:
            assert RD_TOKEN not in url and RD_TOKEN not in headers
    assert any(c.origin == "rdcloud" for c in found)


# -- source list screen ---------------------------------------------------------------

def setup_show_net(torrentio_data=TORRENTIO):
    data = copy.deepcopy(FRIEREN)
    data["data"]["Media"].update(status="FINISHED", nextAiringEpisode=None, episodes=28)
    return (FakeNet().route("graphql.anilist.co", data).route("api.ani.zip", ANIZIP)
            .route("torrentio.strem.fun", torrentio_data).route("nyaa.si", OSError("down")))


def defaults(dub_only=True):
    xbmcaddon.settings.update(torrentio_enabled=True, nyaa_enabled=True, dub_only=dub_only)


def test_choose_shows_dub_sources_with_details_and_show_all_row():
    setup_show_net()
    defaults()
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    heading, rows = xbmcgui.select_calls[-1]
    assert heading.endswith("Episode 3")
    assert all(("English dub" in r[1] or "Dual audio" in r[1]) for r in rows[:-1])
    assert rows[-1][0].startswith("Show all sources (")
    assert "Torrentio (" in rows[0][1] and "seeders" in rows[0][1] and "Not checked yet" in rows[0][1]
    assert any("Could not reach: Nyaa" in n[1] for n in xbmcgui.notifications)


def test_choose_show_all_row_switches_view():
    setup_show_net()
    defaults()
    xbmcgui.select_answers.extend(["last", -1])  # pick "Show all", then cancel
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    first, second = xbmcgui.select_calls[-2][1], xbmcgui.select_calls[-1][1]
    assert len(second) > len(first) - 1


def test_choose_no_dub_asks_to_show_all():
    data = copy.deepcopy(TORRENTIO)
    data["streams"] = [s for s in data["streams"] if "Dub" not in s["title"] and "🇬🇧" not in s["title"] and "Dual" not in s["title"]]
    setup_show_net(data)
    defaults()
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    assert "No English dub" in xbmcgui.yesno_calls[-1][1]
    assert xbmcgui.select_calls == []


def test_choose_heading_reports_filtered_count():
    setup_show_net()
    defaults(dub_only=False)
    xbmcaddon.settings["min_resolution"] = 4  # 2160p only
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    heading, rows = xbmcgui.select_calls[-1]
    assert "hidden by your filters" in heading
    assert all("2160p" in r[1] or "2160p" not in r[1] for r in rows)


def test_candidates_cached_for_reopen():
    net = setup_show_net()
    defaults()
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    assert net.count("torrentio") == 1


def test_nothing_found_message():
    setup_show_net({"streams": []})
    defaults(dub_only=False)
    router.dispatch([BASE + "play", "-1", "?id=154587&ep=3"])
    assert xbmcgui.ok_calls[-1][1] == "No sources found for this episode."


# -- My Real-Debrid --------------------------------------------------------------------

def connect_store():
    auth.TokenStore(paths.profile_dir()).save(client_id="CID000001", client_secret="SECRET000001",
                                              access_token=RD_TOKEN, refresh_token="REFRESH000001", expires_at=4e9)


def test_my_real_debrid_requires_connection():
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "rd/cloud", "1", ""])
    assert "not connected" in xbmcgui.yesno_calls[-1][1]
    assert xbmcplugin.end_calls[-1][1] is False


def test_my_real_debrid_lists_downloaded_torrents_with_add_magnet_first():
    connect_store()
    FakeNet().route("/torrents", TORRENTS)
    router.dispatch([BASE + "rd/cloud", "1", ""])
    labels = [i.getLabel() for _, _, i, _ in xbmcplugin.directory_items]
    assert labels[0] == "Add magnet link..."
    assert len(labels) == 3  # add + two downloaded
    assert not any("downloading" in l for l in labels)


def test_torrent_view_lists_selected_videos_only():
    connect_store()
    FakeNet().route("/torrents/info/T1", INFO_T1)
    router.dispatch([BASE + "rd/torrent", "1", "?id=T1"])
    labels = [i.getLabel() for _, _, i, _ in xbmcplugin.directory_items]
    assert labels == ["S01E02-Journey.mkv", "S01E03-Killing Magic.mkv", "NCOP.mkv"]


def test_add_magnet_rejects_non_magnets():
    connect_store()
    xbmcgui.input_answers.append("https://example.com/file.torrent")
    router.dispatch([BASE + "rd/add_magnet", "-1", ""])
    assert "magnet:?xt=urn:btih:" in xbmcgui.ok_calls[-1][1]


def test_add_magnet_adds_and_selects_all():
    connect_store()
    net = FakeNet().route("/torrents/addMagnet", {"id": "NEW1", "uri": "x"}).route("/torrents/selectFiles/NEW1", {})
    xbmcgui.input_answers.append("magnet:?xt=urn:btih:" + "e" * 40 + "&dn=Show")
    router.dispatch([BASE + "rd/add_magnet", "-1", ""])
    assert net.count("/torrents/addMagnet") == 1
    select_body = [b for m, u, b in net.calls if "selectFiles" in u][0]
    assert "files=all" in select_body
    assert xbmcgui.notifications[-1][1] == "Added to your Real-Debrid"


def test_subtitle_flags_are_not_dub_evidence():
    # Live Torrentio lines for a show with no English dub (Ruri no Houseki, 2026-10-11).
    subs_only = "Multi Subs / 🇬🇧 / 🇷🇺 / 🇮🇹 / 🇵🇹 / 🇪🇸 / 🇲🇽 / 🇫🇷 / 🇩🇪 / 🇸🇦"
    data = {"streams": [
        {"name": "Torrentio\n1080p", "infoHash": "f" * 40, "fileIdx": 0,
         "title": f"[Erai-raws] Ruri no Houseki - 01 [1080p CR WEB-DL AVC EAC3][MultiSub][037FE43B].mkv\n👤 9 💾 1.4 GB ⚙️ NyaaSi\n{subs_only}"},
        {"name": "Torrentio\n1080p", "infoHash": "e" * 40, "fileIdx": 0,
         "title": "[G] Show - 01 (1080p)\n👤 9 💾 1.4 GB ⚙️ NyaaSi\nDubbed / 🇷🇺"},
        {"name": "Torrentio\n1080p", "infoHash": "d" * 40, "fileIdx": 0,
         "title": "[G] Show - 01 (1080p)\n👤 9 💾 1.4 GB ⚙️ NyaaSi\nDubbed / Multi Subs / Dual Audio / 🇬🇧 / 🇷🇺"},
    ]}
    audio = {c.info_hash[0]: c.audio for c in torrentio.parse_streams(data, 1)}
    assert audio == {"f": None, "e": None, "d": "dub"}


def test_flag_from_english_subtitles_is_not_english_audio():
    # Live Frieren list (2026-10-11): Portuguese dual audio, English only as subtitles.
    data = {"streams": [
        {"name": "Torrentio\n1080p", "infoHash": "a" * 40, "fileIdx": 0,
         "title": "[Anitsu] Sousou no Frieren S01 [BD 1080p x265 Opus] [DUAL JAP PT-BR] [SUB PT-BR ENG]\n"
                  "Sousou no Frieren - S01E01.mkv\n👤 9 💾 1.4 GB ⚙️ NyaaSi\nDubbed / Dual Audio / 🇬🇧 / 🇧🇷"},
    ]}
    assert [c.audio for c in torrentio.parse_streams(data, 1)] == [None]
