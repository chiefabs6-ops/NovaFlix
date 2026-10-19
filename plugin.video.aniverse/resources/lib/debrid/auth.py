"""Real-Debrid authorization: device-code login, token refresh, disconnect (DEC-017).

Flow (OAuth2 device flow for open-source apps, api.real-debrid.com docs):
  GET  /oauth/v2/device/code?client_id=<public id>&new_credentials=yes
  GET  /oauth/v2/device/credentials?client_id=..&code=<device_code>  (nulls until approved)
  POST /oauth/v2/token  grant_type=http://oauth.net/grant_type/device/1.0
Refresh is the same token call with code=<refresh_token>.

Tokens live in realdebrid.json in the add-on's data folder, not in Kodi
settings: an open settings dialog would overwrite values written while it is
open. The file is plain text — Kodi has no secure store (SEC-11).
"""

import json
import os
import time

from resources.lib import errors, redact
from resources.lib.kodi import log
from resources.lib.net import http

OAUTH = "https://api.real-debrid.com/oauth/v2"
# Real-Debrid's documented client ID for open-source apps. Public, not a secret.
OPEN_SOURCE_CLIENT_ID = "X245A4XAIBGVM"
DEVICE_GRANT = "http://oauth.net/grant_type/device/1.0"
REFRESH_MARGIN_S = 600
FILENAME = "realdebrid.json"

_clock = time.time


class TokenStore:
    """Per-device credentials. Every secret read is registered for redaction."""

    def __init__(self, directory, filename=FILENAME):
        self._path = os.path.join(directory, filename)
        self.reload()

    def reload(self):
        """Read the file again (the other AniVerse process may have written it)."""
        try:
            with open(self._path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}
        self._register()

    def _register(self):
        for key in ("client_id", "client_secret", "access_token", "refresh_token"):
            redact.register_secret(self.data.get(key))

    @property
    def connected(self):
        return bool(self.data.get("access_token") and self.data.get("refresh_token"))

    def save(self, **values):
        self.data.update(values)
        self._register()
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        try:
            os.chmod(tmp, 0o600)  # best effort; ignored where unsupported
        except OSError:
            pass
        os.replace(tmp, self._path)

    def clear(self):
        self.data = {}
        if os.path.exists(self._path):
            os.remove(self._path)


# -- device login -------------------------------------------------------------

def start_device_login():
    """{device_code, user_code, verification_url, direct_verification_url, interval, expires_in}"""
    data = http.get(f"{OAUTH}/device/code",
                    params={"client_id": OPEN_SOURCE_CLIENT_ID, "new_credentials": "yes"}).json()
    redact.register_secret(data.get("device_code"))
    return data


def poll_credentials(device_code):
    """(client_id, client_secret) once the owner approved, else None."""
    try:
        data = http.get(f"{OAUTH}/device/credentials",
                        params={"client_id": OPEN_SOURCE_CLIENT_ID, "code": device_code}).json() or {}
    except errors.HttpError as exc:
        # A real pending code answers 403 {"error": null, "error_code": null}
        # (live probe 2026-10-11); keep waiting until the code expires.
        if exc.status == 403:
            return None
        raise
    if data.get("client_id") and data.get("client_secret"):
        redact.register_secret(data["client_id"])
        redact.register_secret(data["client_secret"])
        return data["client_id"], data["client_secret"]
    return None


def _token_request(client_id, client_secret, code):
    try:
        data = http.post(f"{OAUTH}/token", data={
            "client_id": client_id, "client_secret": client_secret,
            "code": code, "grant_type": DEVICE_GRANT,
        }).json() or {}
    except errors.HttpError as exc:
        if exc.status in (400, 401, 403):
            raise errors.AuthError(f"Real-Debrid refused the token request (HTTP {exc.status})") from None
        raise
    if not data.get("access_token") or not data.get("refresh_token"):
        raise errors.AuthError("Real-Debrid token response incomplete")
    return data


def _tokens(data):
    redact.register_secret(data["access_token"])
    redact.register_secret(data["refresh_token"])
    expires_in = int(data.get("expires_in") or 0)
    log.info(f"Real-Debrid token received; valid for {expires_in} s")
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": _clock() + expires_in,
    }


def run_device_login(store, presenter, wait):
    """Drive the whole device login. Returns True when tokens are stored.

    presenter.show(info), presenter.update(seconds_left) and presenter.close()
    draw the TV dialog; wait(seconds) sleeps and returns True if the owner
    cancelled or Kodi is closing.
    """
    info = start_device_login()
    deadline = _clock() + int(info.get("expires_in") or 900)
    interval = max(int(info.get("interval") or 5), 1)
    presenter.show(info)
    try:
        while True:
            remaining = int(deadline - _clock())
            if remaining <= 0:
                log.info("Real-Debrid device code expired before approval")
                return False
            presenter.update(remaining)
            if wait(interval):
                log.info("Real-Debrid login cancelled")
                return False
            creds = poll_credentials(info["device_code"])
            if creds:
                break
        client_id, client_secret = creds
        tokens = _tokens(_token_request(client_id, client_secret, info["device_code"]))
        store.save(client_id=client_id, client_secret=client_secret, **tokens)
        return True
    finally:
        presenter.close()


# -- refresh ----------------------------------------------------------------------

def refresh(store):
    """Exchange the refresh token. AuthError means the owner must reconnect."""
    if not store.connected:
        raise errors.AuthError("Real-Debrid is not connected")
    data = _token_request(store.data["client_id"], store.data["client_secret"], store.data["refresh_token"])
    store.save(**_tokens(data))


def ensure_fresh(store):
    """Refresh before expiry; called before every API call (fixes Otaku's startup-only refresh)."""
    if not store.connected:
        raise errors.AuthError("Real-Debrid is not connected")
    if store.data.get("expires_at", 0) - _clock() < REFRESH_MARGIN_S:
        refresh(store)
