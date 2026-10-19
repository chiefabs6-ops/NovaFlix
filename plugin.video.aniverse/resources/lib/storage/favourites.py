"""Local favourites in user.db (DEC-031). One device, not synced."""

import time

from resources.lib.storage import db


class Favourites:
    def __init__(self, directory):
        self._conn = db.open_user_db(directory)

    def add(self, show):
        self._conn.execute(
            "INSERT OR REPLACE INTO favourites (anilist_id, title, poster, added_at, mal_id) VALUES (?, ?, ?, ?, ?)",
            (show.anilist_id, show.title, show.poster, time.time(), show.mal_id),
        )

    def remove(self, anilist_id):
        self._conn.execute("DELETE FROM favourites WHERE anilist_id = ?", (int(anilist_id),))

    def ids(self):
        return {r[0] for r in self._conn.execute("SELECT anilist_id FROM favourites")}

    def all(self):
        """[(anilist_id, title, poster, mal_id)] newest first."""
        return list(self._conn.execute(
            "SELECT anilist_id, title, poster, mal_id FROM favourites ORDER BY added_at DESC"))

    def close(self):
        self._conn.close()
