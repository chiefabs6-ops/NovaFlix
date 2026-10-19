"""Thin Real-Debrid REST client (https://api.real-debrid.com/rest/1.0).

Every call refreshes the token first if it is close to expiry, and once more
on 401 / error_code 8. RD error codes become typed errors (DEC-035).
"""

import time

from resources.lib import errors
from resources.lib.debrid import auth
from resources.lib.net import http

API = "https://api.real-debrid.com/rest/1.0"

# error_code -> account problems the owner must act on (api.real-debrid.com error table)
ACCOUNT_CODES = {
    9: "permission denied",
    14: "account locked",
    15: "account not activated",
    20: "hoster not available for free users",
    21: "too many active downloads",
    22: "IP address not allowed",
    23: "traffic exhausted",
    36: "fair usage limit reached",
}
AUTH_CODES = {8}           # invalid token
RATE_LIMIT_CODES = {5, 34}  # slow down / too many requests

_clock = time.time


class RealDebrid:
    name = "Real-Debrid"

    def __init__(self, store):
        self.store = store

    def _call(self, method, path, retried=False, **kwargs):
        auth.ensure_fresh(self.store)
        headers = {"Authorization": f"Bearer {self.store.data['access_token']}"}
        try:
            return http.request(method, f"{API}{path}", headers=headers, **kwargs)
        except errors.RateLimited:
            raise
        except errors.HttpError as exc:
            code = (exc.payload or {}).get("error_code") if isinstance(exc.payload, dict) else None
            if (exc.status == 401 or code in AUTH_CODES) and not retried:
                auth.refresh(self.store)
                return self._call(method, path, retried=True, **kwargs)
            if exc.status == 401 or code in AUTH_CODES:
                raise errors.AuthError(f"Real-Debrid authorization rejected (HTTP {exc.status})") from None
            if code in RATE_LIMIT_CODES:
                raise errors.RateLimited("Real-Debrid asked to slow down", status=exc.status) from None
            if code in ACCOUNT_CODES:
                raise errors.AccountError(f"Real-Debrid: {ACCOUNT_CODES[code]}", code) from None
            if exc.status == 403:
                raise errors.AccountError("Real-Debrid: account locked or not premium", code) from None
            raise

    def user(self):
        """Account status; stores a summary for the settings screen and warnings (DEC-018)."""
        data = self._call("GET", "/user").json() or {}
        premium_s = int(data.get("premium") or 0)
        summary = {
            "username": data.get("username"),
            "type": data.get("type"),
            "premium_until": _clock() + premium_s if premium_s else None,
            "expiration": data.get("expiration"),
            "checked_at": _clock(),
        }
        self.store.save(account=summary)
        return summary

    def disable_access_token(self):
        """Revoke this device's access on Real-Debrid (best effort)."""
        http.request("GET", f"{API}/disable_access_token",
                     headers={"Authorization": f"Bearer {self.store.data.get('access_token', '')}"})

    # -- torrents (M6: read + owner-initiated add) --------------------------------

    def torrents(self, limit=100):
        return self._call("GET", "/torrents", params={"limit": limit}).json() or []

    def torrent_info(self, torrent_id):
        return self._call("GET", f"/torrents/info/{torrent_id}").json() or {}

    def add_magnet(self, magnet):
        """Returns the new torrent id."""
        return (self._call("POST", "/torrents/addMagnet", data={"magnet": magnet}).json() or {}).get("id")

    def select_files(self, torrent_id, file_ids="all"):
        files = file_ids if isinstance(file_ids, str) else ",".join(str(i) for i in file_ids)
        self._call("POST", f"/torrents/selectFiles/{torrent_id}", data={"files": files})

    def delete_torrent(self, torrent_id):
        self._call("DELETE", f"/torrents/delete/{torrent_id}")

    def unrestrict(self, link):
        """{download, filename, filesize, mimeType, ...} for a Real-Debrid hoster link."""
        return self._call("POST", "/unrestrict/link", data={"link": link}).json() or {}
