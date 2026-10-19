"""M13: MyAnimeList login tokens — PKCE, state, authorize URL, token exchange, refresh, logout."""

import json
import os
from urllib.parse import parse_qs, urlsplit

import pytest
from helpers import MAL_ACCESS, MAL_CLIENT, MAL_REFRESH, MAL_TOKEN, FakeNet, mal_login

from resources.lib import errors, redact
from resources.lib.kodi import paths
from resources.lib.myanimelist import auth

NOW = 1_800_000_000.0
TOKEN2 = dict(MAL_TOKEN, access_token="ACCESSTOKENMAL0000000000000000002",
              refresh_token="REFRESHTOKENMAL000000000000000002")


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    now = [NOW]
    monkeypatch.setattr(auth, "_clock", lambda: now[0])
    return now


def store():
    return auth.MalStore(paths.profile_dir())


def form(body):
    return {k: v[0] for k, v in parse_qs(body).items()}


def test_verifier_and_nonce_are_random_urlsafe_and_redacted():
    v1, v2 = auth.new_verifier(), auth.new_verifier()
    assert len(v1) == 64 and v1 != v2 and set(v1) <= set(auth.URLSAFE)
    nonce = auth.new_nonce()
    assert len(nonce) == 16 and set(nonce) <= set(auth.URLSAFE)
    assert v1 not in redact.text(f"verifier {v1}") and nonce not in redact.text(f"state {nonce}")


def test_authorize_url_uses_plain_pkce_state_and_relay_page():
    url = auth.authorize_url(MAL_CLIENT, "V" * 64, auth.make_state("N" * 16, "192.168.1.86", 41234))
    parts = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://myanimelist.net/v1/oauth2/authorize"
    assert query == {"response_type": "code", "client_id": MAL_CLIENT, "code_challenge": "V" * 64,
                     "code_challenge_method": "plain", "state": "NNNNNNNNNNNNNNNN~192.168.1.86~41234",
                     "redirect_uri": "https://chiefabs6-ops.github.io/aniverse-repo/mal-login.html"}


def test_complete_login_stores_tokens_and_name_only_after_users_me():
    net = FakeNet().route("oauth2/token", MAL_TOKEN).route("users/@me", {"id": 1, "name": "owner"})
    assert auth.complete_login(store(), MAL_CLIENT, "AUTHCODE123456", "V" * 64) == "owner"
    assert form(net.calls[0][2]) == {"client_id": MAL_CLIENT, "grant_type": "authorization_code",
                                     "code": "AUTHCODE123456", "code_verifier": "V" * 64,
                                     "redirect_uri": auth.REDIRECT_URI}
    assert net.calls[1][1].startswith("https://api.myanimelist.net/v2/users/@me")
    saved = store()
    assert saved.logged_in and saved.linked and saved.data["username"] == "owner"
    assert saved.data["expires_at"] == NOW + 2678400 and saved.data["client_id"] == MAL_CLIENT
    assert MAL_ACCESS not in redact.text(json.dumps(saved.data))


def test_refused_token_call_stores_nothing():
    FakeNet().route("oauth2/token", {"error": "invalid_client"}, status=401)
    with pytest.raises(auth.MalLoginRefused):
        auth.complete_login(store(), MAL_CLIENT, "AUTHCODE123456", "V" * 64)
    assert not os.path.exists(os.path.join(paths.profile_dir(), auth.FILENAME))


def test_failed_users_me_stores_nothing():
    FakeNet().route("oauth2/token", MAL_TOKEN).route("users/@me", errors.NetworkError("down"))
    with pytest.raises(errors.NetworkError):
        auth.complete_login(store(), MAL_CLIENT, "AUTHCODE123456", "V" * 64)
    assert not store().linked


def test_refresh_ahead_of_expiry_replaces_both_tokens():
    mal_login(expires_at=NOW + 300)  # inside the 10-minute margin
    net = FakeNet().route("oauth2/token", TOKEN2)
    auth.ensure_fresh(store())
    assert form(net.calls[0][2]) == {"client_id": MAL_CLIENT, "grant_type": "refresh_token",
                                     "refresh_token": MAL_REFRESH}
    assert store().data["refresh_token"] == TOKEN2["refresh_token"]


def test_no_refresh_while_token_is_fresh():
    mal_login(expires_at=NOW + 3600)
    net = FakeNet()
    auth.ensure_fresh(store())
    assert net.calls == []


def test_not_logged_in_raises_without_network():
    FakeNet()
    with pytest.raises(auth.MalLoggedOut):
        auth.ensure_fresh(store())


def test_refused_refresh_logs_out_but_keeps_the_link():
    mal_login(expires_at=NOW)
    FakeNet().route("oauth2/token", {"error": "invalid_grant"}, status=400)
    with pytest.raises(auth.MalLoggedOut):
        auth.ensure_fresh(store())
    after = store()
    assert not after.logged_in and after.linked


def test_refresh_done_by_the_other_process_is_used_not_logged_out():
    # Plugin and service refresh at once: MAL refuses the old refresh token for the slower one.
    mal_login(expires_at=NOW)
    mine = store()  # this process still holds the old tokens
    store().save(access_token=TOKEN2["access_token"], refresh_token=TOKEN2["refresh_token"], expires_at=NOW + 3600)
    FakeNet().route("oauth2/token", {"error": "invalid_grant"}, status=400)
    auth.ensure_fresh(mine)
    assert mine.logged_in and mine.data["access_token"] == TOKEN2["access_token"]


def test_logout_deletes_the_file():
    mal_login()
    store().clear()
    assert not store().linked and not store().logged_in
