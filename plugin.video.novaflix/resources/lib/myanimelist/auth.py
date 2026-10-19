"""MyAnimeList login (M13, amends DEC-015): OAuth2 with plain PKCE, token refresh, logout.

MAL docs (read 2026-10-11): authorize at myanimelist.net/v1/oauth2/authorize with
code_challenge_method=plain (the only method MAL supports); token and refresh at
/v1/oauth2/token. Each refresh returns a new refresh token. NovaFlix needs a MAL app
without a client secret ("web" apps have one), so no secret is ever sent.

Tokens live in mal_auth.json next to realdebrid.json, in the same kind of store (SEC-11).
"""

import secrets
import string
import time
from urllib.parse import urlencode

from resources.lib import errors, redact
from resources.lib.debrid.auth import TokenStore
from resources.lib.kodi import log
from resources.lib.net import http

AUTHORIZE_URL = "https://myanimelist.net/v1/oauth2/authorize"
TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
ME_URL = "https://api.myanimelist.net/v2/users/@me"
REDIRECT_URI = "https://chiefabs6-ops.github.io/novaflix-repo/mal-login.html"
FILENAME = "mal_auth.json"
REFRESH_MARGIN_S = 600
URLSAFE = string.ascii_letters + string.digits + "-_"

_clock = time.time


class MalLoginRefused(errors.NovaFlixError):
    """MyAnimeList refused the token request (wrong redirect URL, app with a secret, bad code)."""


class MalLoggedOut(errors.NovaFlixError):
    """No usable MyAnimeList login: never logged in, logged out, or the login expired."""


class MalStore(TokenStore):
    def __init__(self, directory):
        super().__init__(directory, FILENAME)

    @property
    def logged_in(self):
        return self.connected

    @property
    def linked(self):
        """A login exists, possibly expired: changes are kept for the next login."""
        return bool(self.data.get("username"))


def _random(length):
    value = "".join(secrets.choice(URLSAFE) for _ in range(length))
    redact.register_secret(value)
    return value


def new_verifier():
    return _random(64)


def new_nonce():
    return _random(16)


def make_state(nonce, host, port):
    return f"{nonce}~{host}~{port}"


def authorize_url(client_id, verifier, state):
    redact.register_secret(client_id)
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id, "code_challenge": verifier,
        "code_challenge_method": "plain", "state": state, "redirect_uri": REDIRECT_URI,
    })


def _token_request(fields):
    redact.register_secret(fields.get("client_id"))
    try:
        data = http.post(TOKEN_URL, data=fields).json() or {}
    except errors.HttpError as exc:
        if exc.status in (400, 401, 403):
            raise MalLoginRefused(f"MyAnimeList refused the token request (HTTP {exc.status})") from None
        raise
    if not data.get("access_token") or not data.get("refresh_token"):
        raise MalLoginRefused("MyAnimeList token response incomplete")
    redact.register_secret(data["access_token"])
    redact.register_secret(data["refresh_token"])
    expires_in = int(data.get("expires_in") or 0)
    log.info(f"MyAnimeList token received; valid for {expires_in} s")
    return {"access_token": data["access_token"], "refresh_token": data["refresh_token"],
            "expires_at": _clock() + expires_in}


def complete_login(store, client_id, code, verifier):
    """Exchange the code, confirm it with /users/@me, then store (SEC-13). Returns the MAL name."""
    redact.register_secret(code)
    tokens = _token_request({"client_id": client_id, "grant_type": "authorization_code", "code": code,
                             "code_verifier": verifier, "redirect_uri": REDIRECT_URI})
    me = http.get(ME_URL, params={"fields": "name"},
                  headers={"Authorization": f"Bearer {tokens['access_token']}"}).json() or {}
    name = me.get("name") or "?"
    store.save(client_id=client_id, username=name, **tokens)
    log.info("MyAnimeList login stored")
    return name


def expire(store):
    """Refresh refused: keep the username (queued changes wait for the next login), drop the tokens."""
    store.save(access_token=None, refresh_token=None, expires_at=0)
    log.warning("MyAnimeList login expired; log in again in Settings")


def refresh(store):
    used = store.data.get("refresh_token")
    if not used:
        raise MalLoggedOut("MyAnimeList is not logged in")
    try:
        tokens = _token_request({"client_id": store.data.get("client_id"), "grant_type": "refresh_token",
                                 "refresh_token": used})
    except MalLoginRefused:
        store.reload()
        if store.connected and store.data.get("refresh_token") != used:
            log.info("MyAnimeList token was refreshed by the other NovaFlix process")
            return
        expire(store)
        raise MalLoggedOut("MyAnimeList login expired") from None
    store.save(**tokens)


def ensure_fresh(store):
    if not store.logged_in:
        raise MalLoggedOut("MyAnimeList is not logged in")
    if store.data.get("expires_at", 0) - _clock() < REFRESH_MARGIN_S:
        refresh(store)
