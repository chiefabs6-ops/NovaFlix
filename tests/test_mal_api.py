"""M13: logged-in MyAnimeList calls — Bearer token, refresh on 401, entry/update/list shapes."""

import datetime
from urllib.parse import parse_qs

import pytest
from helpers import MAL_ACCESS, MAL_TOKEN, FakeNet, Replies, mal_login

from resources.lib import errors
from resources.lib.kodi import paths
from resources.lib.myanimelist import auth
from resources.lib.myanimelist.api import MalApi

ACCESS2 = "ACCESSTOKENMAL0000000000000000002"
TOKEN2 = dict(MAL_TOKEN, access_token=ACCESS2, refresh_token="REFRESHTOKENMAL000000000000000002")
ENTRY = {"id": 52991, "title": "Sousou no Frieren", "num_episodes": 28, "status": "finished_airing",
         "my_list_status": {"status": "watching", "num_episodes_watched": 7, "score": 8,
                            "updated_at": "2026-10-10T20:00:00+00:00"}}
LIST = {"data": [{"node": {"id": 52991, "title": "Sousou no Frieren", "main_picture": {"large": "f.jpg"}},
                  "list_status": {"status": "watching", "num_episodes_watched": 7,
                                  "updated_at": "2026-10-10T20:00:00+00:00"}}], "paging": {}}


@pytest.fixture
def api():
    return MalApi(mal_login())


def test_entry_sends_bearer_and_parses(api):
    net = FakeNet().route("anime/52991?", ENTRY)
    assert api.entry(52991) == {"title": "Sousou no Frieren", "num_episodes": 28, "airing": "finished_airing",
                                "list_status": "watching", "watched": 7, "score": 8}
    assert net.headers[0]["Authorization"] == f"Bearer {MAL_ACCESS}"
    assert "fields=my_list_status%2Cnum_episodes%2Cstatus" in net.calls[0][1]


def test_entry_not_on_the_list(api):
    FakeNet().route("anime/52991?", {"id": 52991, "title": "Frieren", "num_episodes": 0, "status": "currently_airing"})
    assert api.entry(52991) == {"title": "Frieren", "num_episodes": 0, "airing": "currently_airing",
                                "list_status": None, "watched": 0, "score": 0}


def test_update_puts_only_status_and_count(api):
    net = FakeNet().route("52991/my_list_status", {"status": "watching"})
    api.update(52991, "watching", 8)
    method, url, body = net.calls[0]
    assert method == "PUT" and url == "https://api.myanimelist.net/v2/anime/52991/my_list_status"
    assert {k: v[0] for k, v in parse_qs(body).items()} == {"status": "watching", "num_watched_episodes": "8"}


def test_401_refreshes_once_and_retries(api):
    net = FakeNet().route("oauth2/token", TOKEN2).route(
        "anime/52991?", Replies((401, {"error": "invalid_token"}), (200, ENTRY)))
    assert api.entry(52991)["watched"] == 7
    assert net.count("oauth2/token") == 1 and net.headers[-1]["Authorization"] == f"Bearer {ACCESS2}"


def test_401_after_refresh_logs_out(api):
    FakeNet().route("oauth2/token", TOKEN2).route("anime/52991?", {"error": "invalid_token"}, status=401)
    with pytest.raises(auth.MalLoggedOut):
        api.entry(52991)
    store = auth.MalStore(paths.profile_dir())
    assert not store.logged_in and store.linked


def test_not_logged_in_raises_without_network():
    FakeNet()
    with pytest.raises(auth.MalLoggedOut):
        MalApi(auth.MalStore(paths.profile_dir())).entry(52991)


def test_list_page_uses_me_and_reads_updated_at(api):
    net = FakeNet().route("users/@me/animelist", LIST)
    entries, more = api.list_page("watching")
    assert (entries[0].mal_id, entries[0].watched, more) == (52991, 7, False)
    assert entries[0].updated_at == datetime.datetime(2026, 10, 10, 20, tzinfo=datetime.timezone.utc).timestamp()
    assert "status=watching" in net.calls[0][1] and net.headers[0]["Authorization"] == f"Bearer {MAL_ACCESS}"
    assert "X-MAL-CLIENT-ID" not in net.headers[0]


def test_token_never_in_error_text(api):
    FakeNet().route("anime/52991?", {"error": "boom"}, status=500)
    with pytest.raises(errors.ServiceUnavailable) as exc:
        api.entry(52991)
    assert MAL_ACCESS not in str(exc.value)


def test_remove_deletes_the_list_entry(api):
    net = FakeNet().route("52991/my_list_status", [])
    api.remove(52991)
    method, url, _ = net.calls[0]
    assert method == "DELETE" and url == "https://api.myanimelist.net/v2/anime/52991/my_list_status"


def test_listedit_remove_treats_not_on_list_as_done(monkeypatch):
    from resources.lib import errors
    from resources.lib.kodi import paths
    from resources.lib.myanimelist import listedit
    from resources.lib.myanimelist.api import MalApi
    def gone(self, mal_id):
        raise errors.HttpError("not found", 404)
    monkeypatch.setattr(MalApi, "remove", gone)
    listedit.remove(paths.profile_dir(), 52991)  # no exception
    def broken(self, mal_id):
        raise errors.HttpError("server error", 500)
    monkeypatch.setattr(MalApi, "remove", broken)
    import pytest
    with pytest.raises(errors.HttpError):
        listedit.remove(paths.profile_dir(), 52991)
