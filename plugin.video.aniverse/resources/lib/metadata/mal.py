"""MyAnimeList lists by client ID (DEC-015); logged-in calls live in resources.lib.myanimelist (M13).

Uses GET /users/{name}/animelist with the owner's own client ID in the
X-MAL-CLIENT-ID header (client_auth in the MAL API v2 reference). No login.
"""

import datetime
from dataclasses import dataclass
from typing import Optional

from resources.lib import errors, redact
from resources.lib.net import http

URL = "https://api.myanimelist.net/v2/users/{user}/animelist"
PAGE_SIZE = 100
STATUSES = ("watching", "plan_to_watch", "completed", "on_hold", "dropped")


class MalSetupMissing(errors.AniVerseError):
    """Client ID or username not set in AniVerse settings."""


class MalUserUnavailable(errors.AniVerseError):
    """User not found, or the list is private."""


class MalClientRejected(errors.AniVerseError):
    """MyAnimeList did not accept the client ID."""


@dataclass
class MalEntry:
    mal_id: int
    title: str
    picture: Optional[str]
    watched: int
    status: str
    updated_at: float = 0.0


def fetch_list(client_id, username, status, page=1):
    """One page of the user's list: ([MalEntry], has_more)."""
    if not client_id or not username:
        raise MalSetupMissing("MyAnimeList client ID or username missing")
    redact.register_secret(client_id)
    params = {
        "status": status,
        "sort": "list_updated_at",
        "limit": PAGE_SIZE,
        "offset": (page - 1) * PAGE_SIZE,
        "fields": "list_status",
    }
    try:
        resp = http.get(URL.format(user=username.strip()), params=params,
                        headers={"X-MAL-CLIENT-ID": client_id})
    except errors.HttpError as exc:
        if exc.status in (403, 404):
            raise MalUserUnavailable(f"MyAnimeList user list unavailable (HTTP {exc.status})") from None
        if exc.status in (400, 401):
            raise MalClientRejected(f"MyAnimeList rejected the client ID (HTTP {exc.status})") from None
        raise
    return parse_list(resp.json() or {}, status)


def _timestamp(text):
    try:
        return datetime.datetime.fromisoformat(text).timestamp() if text else 0.0
    except ValueError:
        return 0.0


def parse_list(data, status):
    """([MalEntry], has_more) from an animelist response (public list or the logged-in @me list)."""
    entries = []
    for row in data.get("data") or []:
        node = row.get("node") or {}
        if not node.get("id"):
            continue
        picture = node.get("main_picture") or {}
        list_status = row.get("list_status") or {}
        entries.append(MalEntry(
            mal_id=int(node["id"]),
            title=node.get("title") or "?",
            picture=picture.get("large") or picture.get("medium"),
            watched=int(list_status.get("num_episodes_watched") or 0),
            status=list_status.get("status") or status,
            updated_at=_timestamp(list_status.get("updated_at")),
        ))
    return entries, bool((data.get("paging") or {}).get("next"))
