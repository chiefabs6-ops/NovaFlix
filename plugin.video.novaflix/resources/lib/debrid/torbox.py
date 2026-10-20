"""TorBox client (DEC-054), with the debrid interface the
existing resolver, source list and cleanup work unchanged.

API (TorBox official SDK docs, TorrentsService.md, checked 2026-10-11):
  POST /v1/api/torrents/createtorrent     form: magnet, seed, allow_zip
  GET  /v1/api/torrents/mylist?id=&bypass_cache=true
  GET  /v1/api/torrents/requestdl?token=&torrent_id=&file_id=
  POST /v1/api/torrents/controltorrent    {"torrent_id", "operation": "delete"}
  GET  /v1/api/torrents/checkcached?hash=a,b&format=object&list_files=true
Auth: the owner's API key as a Bearer header (requestdl also takes it as
`token`; query strings never reach logs, and the key is a registered secret).
TorBox downloads whole torrents: there is no file-selection step.
"""

from resources.lib import errors, redact
from resources.lib.kodi import log
from resources.lib.net import http

API = "https://api.torbox.app/v1/api"
NAME = "TorBox"

AUTH_ERRORS = {"BAD_TOKEN", "AUTH_ERROR", "NO_AUTH"}
ACCOUNT_ERRORS = {
    "MONTHLY_LIMIT": "monthly download limit reached",
    "ACTIVE_LIMIT": "no free download slot (the free plan has 1)",
    "DOWNLOAD_TOO_LARGE": "torrent is larger than your plan allows",
    "COOLDOWN_LIMIT": "account is in a cooldown period",
    "PLAN_RESTRICTED_FEATURE": "not available on your plan",
}
_DOWNLOADING = {"downloading", "metadl", "checkingresumedata", "queued", "paused", "stalled", "stalled (no seeds)",
                "checking", "uploading"}


class TorBox:
    name = NAME

    def __init__(self, api_key):
        self.key = api_key.strip()
        redact.register_secret(self.key)

    # -- transport ----------------------------------------------------------------

    def _call(self, method, path, **kwargs):
        headers = {"Authorization": f"Bearer {self.key}"}
        try:
            resp = http.request(method, f"{API}{path}", headers=headers, **kwargs)
        except errors.RateLimited:
            raise
        except errors.HttpError as exc:
            self._raise_for(exc.payload, exc.status)
            raise
        data = resp.json() or {}
        if data.get("success") is False:
            self._raise_for(data, resp.status)
            raise errors.HttpError(f"TorBox error: {data.get('error') or 'unknown'}", resp.status, data)
        return data.get("data")

    @staticmethod
    def _raise_for(payload, status):
        code = (payload or {}).get("error") if isinstance(payload, dict) else None
        if code in AUTH_ERRORS or (status in (401, 403) and code is None):
            raise errors.AuthError("TorBox rejected the API key")
        if code in ACCOUNT_ERRORS:
            raise errors.AccountError(f"TorBox: {ACCOUNT_ERRORS[code]}", code)

    # -- debrid interface used by the resolver -----------------------------------------------

    @staticmethod
    def _status(t):
        if t.get("download_finished") or t.get("download_present"):
            return "downloaded"
        state = (t.get("download_state") or "").lower()
        if state in ("error", "failed") or state.startswith("failed"):
            return "error"
        if not t.get("files"):
            # No file list yet: TorBox is still reading the torrent. Live states seen without
            # files (2026-10-20): "meta", "checking", "uploading" as well as "metadl".
            return "magnet_conversion"
        return "downloading" if state in _DOWNLOADING or state.startswith("stalled") else "queued"

    def torrents(self, limit=100):
        items = self._call("GET", "/torrents/mylist", params={"limit": limit, "bypass_cache": "true"}) or []
        return [{"id": str(t.get("id")), "hash": (t.get("hash") or "").lower(), "status": self._status(t),
                 "filename": t.get("name"), "bytes": t.get("size")} for t in items]

    def torrent_info(self, torrent_id):
        t = self._call("GET", "/torrents/mylist", params={"id": torrent_id, "bypass_cache": "true"}) or {}
        # Field names below follow TorBox integrations in the wild (UNVERIFIED until the first
        # live torrent); this debug line records the real ones without any values.
        log.debug(f"TorBox torrent fields: {sorted(t)}; state={t.get('download_state')}")
        files = t.get("files") or []
        status = self._status(t)
        return {
            "id": str(t.get("id", torrent_id)),
            "hash": (t.get("hash") or "").lower(),
            "filename": t.get("name"),
            "status": status,
            # Whole torrent is downloaded, so every file counts as selected.
            "files": [{"id": f.get("id"), "path": f.get("name") or f.get("short_name") or "", "bytes": f.get("size"),
                       "selected": 1} for f in files],
            "links": [f"torbox:{t.get('id', torrent_id)}:{f.get('id')}" for f in sorted(files, key=lambda f: f.get("id"))]
            if status == "downloaded" else [],
            "progress": round((t.get("progress") or 0) * 100),
            "speed": t.get("download_speed"),
            "seeders": t.get("seeds"),
        }

    def add_magnet(self, magnet):
        data = self._call("POST", "/torrents/createtorrent",
                          multipart={"magnet": magnet, "seed": "3", "allow_zip": "false"}) or {}
        return str(data.get("torrent_id")) if data.get("torrent_id") is not None else None

    def select_files(self, torrent_id, file_ids="all"):
        """TorBox always downloads the whole torrent; nothing to select."""

    def unrestrict(self, link):
        _, torrent_id, file_id = link.split(":", 2)
        url = self._call("GET", "/torrents/requestdl",
                         params={"token": self.key, "torrent_id": torrent_id, "file_id": file_id, "zip_link": "false"})
        if not url:
            return {}
        return {"download": url, "filename": None}

    def delete_torrent(self, torrent_id):
        self._call("POST", "/torrents/controltorrent",
                   json_body={"torrent_id": int(torrent_id), "operation": "delete"})

    # -- free cache check (no torrent added, no quota used) ------------------------------------

    def cached(self, hashes):
        """{hash: [file names]} for the hashes TorBox has cached."""
        out = {}
        hashes = [h for h in hashes if h]
        for i in range(0, len(hashes), 50):
            data = self._call("GET", "/torrents/checkcached",
                              params={"hash": ",".join(hashes[i:i + 50]), "format": "object", "list_files": "true"}) or {}
            for h, info in data.items():
                files = (info or {}).get("files") or []
                out[h.lower()] = [f.get("name") or f.get("short_name") or "" for f in files]
        return out
