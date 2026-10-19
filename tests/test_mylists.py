"""M4: read-only MyAnimeList lists and local Favourites.

MAL responses are hand-built from the documented shape in the MAL API v2
reference (data[].node / data[].list_status / paging.next) because the
suite never uses a real client ID.
"""

import copy
import sqlite3

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from helpers import MAL_ACCESS, FakeNet, fixture, mal_login
from resources.lib import router
from resources.lib.kodi import paths
from resources.lib.metadata import dubs, mal
from resources.lib.storage import db, migrations
from resources.lib.storage.cache import Cache

BASE = "plugin://plugin.video.aniverse/"
FRIEREN = fixture("anilist_media_154587.json")
TRENDING = fixture("anilist_trending.json")
DUBS = fixture("mal_dubs.json")
CLIENT_ID = "TESTCLIENTID0123456789abcdef"


def mal_page(*entries, next_page=False):
    data = [{
        "node": {"id": mal_id, "title": title,
                 "main_picture": {"medium": f"https://cdn.example/{mal_id}m.jpg",
                                  "large": f"https://cdn.example/{mal_id}l.jpg"}},
        "list_status": {"status": "watching", "num_episodes_watched": watched, "score": 0,
                        "is_rewatching": False, "updated_at": "2026-10-01T00:00:00+00:00"},
    } for mal_id, title, watched in entries]
    paging = {"next": "https://api.myanimelist.net/v2/users/u/animelist?offset=100"} if next_page else {}
    return {"data": data, "paging": paging}


def anilist_by_mal(*mal_ids):
    media = []
    base = TRENDING["data"]["Page"]["media"][0]
    for i, mal_id in enumerate(mal_ids):
        m = copy.deepcopy(base)
        m["id"], m["idMal"], m["episodes"] = 1000 + i, mal_id, 12
        m["title"] = {"english": f"Show {mal_id}", "romaji": f"Romaji {mal_id}", "native": None}
        media.append(m)
    return {"data": {"Page": {"pageInfo": {"hasNextPage": False}, "media": media}}}


def configure(client_id=CLIENT_ID, username="tester"):
    xbmcaddon.settings["mal_client_id"] = client_id
    xbmcaddon.settings["mal_username"] = username


def labels():
    return [item.getLabel() for _, _, item, _ in xbmcplugin.directory_items]


def urls():
    return [url for _, url, _, _ in xbmcplugin.directory_items]


def dispatch(path, query=""):
    router.dispatch([BASE + path, "1", query])


class HttpStatus:
    """Transport returning one fixed status."""

    def __init__(self, status):
        self.status = status
        self.calls = []

    def __call__(self, method, url, headers, body, timeout, context):
        self.calls.append((url, headers))
        return self.status, {}, b'{"error":"x"}'


# -- MAL client ---------------------------------------------------------------

def test_fetch_list_sends_client_id_header_and_parses():
    from resources.lib.net import http
    calls = []

    def transport(method, url, headers, body, timeout, context):
        calls.append((url, headers))
        import json
        return 200, {}, json.dumps(mal_page((52991, "Sousou no Frieren", 5), next_page=True)).encode()

    http.set_transport(transport)
    entries, more = mal.fetch_list(CLIENT_ID, "tester", "watching")
    assert entries[0].mal_id == 52991 and entries[0].watched == 5
    assert entries[0].picture.endswith("l.jpg")
    assert more is True
    url, headers = calls[0]
    assert "/users/tester/animelist" in url and "status=watching" in url
    assert headers["X-MAL-CLIENT-ID"] == CLIENT_ID


def test_client_id_never_logged_on_errors():
    from resources.lib.net import http
    http.set_transport(HttpStatus(500))
    configure()
    dispatch("mal/list", "?status=watching")
    logged = "\n".join(m for _, m in xbmc.log_records)
    assert CLIENT_ID not in logged


def test_unknown_or_private_user_gets_clear_dialog():
    from resources.lib.net import http
    for status in (403, 404):
        xbmcgui.reset()
        http.set_transport(HttpStatus(status))
        configure()
        dispatch("mal/list", "?status=watching")
        assert "public list" in xbmcgui.yesno_calls[-1][1]


def test_rejected_client_id_offers_settings():
    from resources.lib.net import http
    http.set_transport(HttpStatus(401))
    configure()
    xbmcgui.yesno_answers.append(True)
    dispatch("mal/list", "?status=watching")
    assert "Client ID" in xbmcgui.yesno_calls[-1][1]
    assert xbmcaddon.opened_settings == [True]


def test_missing_settings_prompts_for_setup():
    xbmcgui.yesno_answers.append(False)
    dispatch("mal")
    assert "Client ID and username" in xbmcgui.yesno_calls[-1][1]
    assert xbmcplugin.end_calls[-1][1] is False
    assert xbmcaddon.opened_settings == []


def test_mal_menu_lists_five_statuses():
    configure()
    dispatch("mal")
    assert labels() == ["Watching", "Plan to Watch", "Completed", "On Hold", "Dropped"]
    assert "mal/list?status=plan_to_watch" in urls()[1]


def test_mal_list_joins_to_anilist_with_progress_and_badge():
    configure()
    FakeNet().route("MAL-Dubs", DUBS)
    dubs.refresh(paths.profile_dir())
    (FakeNet()
     .route("api.myanimelist.net", mal_page((52991, "Sousou no Frieren", 5), (777, "Obscure", 1), next_page=True))
     .route("graphql.anilist.co", anilist_by_mal(52991)))
    dispatch("mal/list", "?status=watching")
    assert labels()[0].startswith("Show 52991 ") and "(5/12)" in labels()[0] and "DUB" in labels()[0]
    assert "show?id=1000" in urls()[0]
    assert "not found on AniList" in labels()[1]
    assert labels()[-1] == "Next page" and "page=2" in urls()[-1]


def test_mal_list_is_cached_for_30_minutes():
    configure()
    net = (FakeNet()
           .route("api.myanimelist.net", mal_page((52991, "Sousou no Frieren", 5)))
           .route("graphql.anilist.co", anilist_by_mal(52991)))
    dispatch("mal/list", "?status=watching")
    dispatch("mal/list", "?status=watching")
    assert net.count("myanimelist") == 1
    assert net.count("anilist") == 1  # MAL→AniList lookups cached too


# -- favourites ---------------------------------------------------------------

def test_favourites_empty_state():
    dispatch("favourites")
    assert labels() == ["No favourites yet. Press Menu on any show to add it."]


def test_add_and_remove_favourite_via_context_actions():
    FakeNet().route("graphql.anilist.co", FRIEREN)
    dispatch("favourites/add", "?id=154587")
    assert xbmcgui.notifications[-1][1] == "Added to Favourites"
    assert "Container.Refresh" in xbmc.builtins_executed
    xbmcplugin.reset()
    dispatch("favourites")
    assert labels()[0].startswith("Frieren")
    item = xbmcplugin.directory_items[0][2]
    assert item.context_menu[0][0] == "Remove from Favourites"
    assert "favourites/remove?id=154587" in item.context_menu[0][1]
    dispatch("favourites/remove", "?id=154587")
    xbmcplugin.reset()
    dispatch("favourites")
    assert labels() == ["No favourites yet. Press Menu on any show to add it."]


def test_show_lists_offer_add_or_remove_depending_on_state():
    FakeNet().route("graphql.anilist.co", TRENDING)
    first_id = TRENDING["data"]["Page"]["media"][0]["id"]
    dispatch("trending")
    assert xbmcplugin.directory_items[0][2].context_menu[0][0] == "Add to Favourites"
    from resources.lib.storage.favourites import Favourites
    from resources.lib.metadata.anilist import to_show
    favs = Favourites(paths.profile_dir())
    favs.add(to_show(TRENDING["data"]["Page"]["media"][0]))
    favs.close()
    xbmcplugin.reset()
    Cache(paths.profile_dir()).clear()
    FakeNet().route("graphql.anilist.co", TRENDING)
    dispatch("trending")
    assert xbmcplugin.directory_items[0][2].context_menu[0][0] == "Remove from Favourites"
    assert f"id={first_id}" in xbmcplugin.directory_items[0][2].context_menu[0][1]


def test_favourites_survive_clear_cache():
    FakeNet().route("graphql.anilist.co", FRIEREN)
    dispatch("favourites/add", "?id=154587")
    xbmcgui.yesno_answers.append(True)
    dispatch("clear_cache")
    xbmcplugin.reset()
    dispatch("favourites")
    assert labels()[0].startswith("Frieren")


def test_favourite_shows_dub_badge_from_stored_mal_id():
    FakeNet().route("MAL-Dubs", DUBS)
    dubs.refresh(paths.profile_dir())
    FakeNet().route("graphql.anilist.co", FRIEREN)
    dispatch("favourites/add", "?id=154587")
    xbmcplugin.reset()
    dispatch("favourites")
    assert "DUB" in labels()[0]


def test_migration_v2_upgrades_existing_v1_database(tmp_path):
    path = str(tmp_path / "user.db")
    conn = sqlite3.connect(path)
    for statement in migrations.USER_MIGRATIONS[0].split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.execute("INSERT INTO favourites (anilist_id, title, poster, added_at) VALUES (1, 'Old', '', 0)")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    conn = db.open_user_db(str(tmp_path))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(migrations.USER_MIGRATIONS)
    assert conn.execute("SELECT title, mal_id FROM favourites").fetchone() == ("Old", None)


MY_LIST = {"data": [{"node": {"id": 52991, "title": "Sousou no Frieren"},
                     "list_status": {"status": "watching", "num_episodes_watched": 7}}], "paging": {}}


def test_logged_in_lists_use_the_login_and_need_no_username():
    mal_login()
    configure(username="")
    net = FakeNet().route("users/@me/animelist", MY_LIST).route("graphql.anilist.co", anilist_by_mal(52991))
    dispatch("mal")
    assert len(labels()) == 5   # status menu without a username
    xbmcplugin.directory_items.clear()
    dispatch("mal/list", "?status=watching")
    assert net.headers[0]["Authorization"] == f"Bearer {MAL_ACCESS}" and "X-MAL-CLIENT-ID" not in net.headers[0]
    assert labels()[0].startswith("Show 52991")


def test_expired_login_falls_back_to_the_public_list():
    mal_login()
    configure()
    net = (FakeNet().route("users/@me/animelist", {"error": "invalid_token"}, status=401)
           .route("oauth2/token", {"error": "invalid_grant"}, status=400)
           .route("users/tester/animelist", MY_LIST).route("graphql.anilist.co", anilist_by_mal(52991)))
    dispatch("mal/list", "?status=watching")
    public = next(h for (_, url, _), h in zip(net.calls, net.headers) if "users/tester/animelist" in url)
    assert public["X-MAL-CLIENT-ID"] == CLIENT_ID
    assert labels()[0].startswith("Show 52991")
