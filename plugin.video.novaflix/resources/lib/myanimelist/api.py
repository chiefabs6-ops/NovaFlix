"""Logged-in MyAnimeList API calls (M13). The token goes only to api.myanimelist.net (SEC-12).

Before every call the token is refreshed if it expires within 10 minutes; on HTTP 401
it is refreshed once and the call retried once (spec §4.2)."""

from resources.lib import errors
from resources.lib.metadata import mal
from resources.lib.myanimelist import auth
from resources.lib.net import http

API = "https://api.myanimelist.net/v2"
ENTRY_FIELDS = "my_list_status,num_episodes,status"


class MalApi:
    def __init__(self, store):
        self.store = store

    def _send(self, method, path, **kwargs):
        headers = {"Authorization": f"Bearer {self.store.data['access_token']}"}
        return http.request(method, API + path, headers=headers, **kwargs)

    def _call(self, method, path, **kwargs):
        auth.ensure_fresh(self.store)
        try:
            return self._send(method, path, **kwargs)
        except errors.HttpError as exc:
            if exc.status != 401:
                raise
        auth.refresh(self.store)
        try:
            return self._send(method, path, **kwargs)
        except errors.HttpError as exc:
            if exc.status != 401:
                raise
        auth.expire(self.store)
        raise auth.MalLoggedOut("MyAnimeList refused the login after a refresh")

    def me(self):
        return (self._call("GET", "/users/@me", params={"fields": "name"}).json() or {}).get("name") or "?"

    def entry(self, mal_id):
        data = self._call("GET", f"/anime/{int(mal_id)}", params={"fields": ENTRY_FIELDS}).json() or {}
        mine = data.get("my_list_status") or {}
        return {"title": data.get("title") or "?", "num_episodes": int(data.get("num_episodes") or 0),
                "airing": data.get("status") or "", "list_status": mine.get("status"),
                "watched": int(mine.get("num_episodes_watched") or 0), "score": int(mine.get("score") or 0)}

    def update(self, mal_id, status, watched):
        """Sends only status and episode count; score and other fields stay as they are."""
        self._call("PUT", f"/anime/{int(mal_id)}/my_list_status",
                   data={"status": status, "num_watched_episodes": int(watched)})

    def remove(self, mal_id):
        """Deletes the show from the owner's list (HTTP 404 when it is not on it)."""
        self._call("DELETE", f"/anime/{int(mal_id)}/my_list_status")

    def list_page(self, status, page=1):
        resp = self._call("GET", "/users/@me/animelist", params={
            "status": status, "sort": "list_updated_at", "limit": mal.PAGE_SIZE,
            "offset": (page - 1) * mal.PAGE_SIZE, "fields": "list_status"})
        return mal.parse_list(resp.json() or {}, status)

    def watching(self):
        return self.list_page("watching")[0]
