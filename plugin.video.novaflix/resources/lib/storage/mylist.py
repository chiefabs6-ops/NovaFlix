"""My List: titles the owner saved (user.db v6, Plan 4). Never touched by "Clear cache"."""

import time

from resources.lib import media
from resources.lib.storage import db

_clock = time.time


class MyList:
    def __init__(self, directory):
        self._directory = directory

    def _run(self, sql, args=()):
        conn = db.open_user_db(self._directory)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def add(self, title):
        self._run("INSERT OR REPLACE INTO my_list (media_type, tmdb_id, title, poster, year, added_at) "
                  "VALUES (?, ?, ?, ?, ?, ?)",
                  (title.media_type, int(title.tmdb_id), title.title, title.poster, title.year, _clock()))

    def remove(self, media_type, tmdb_id):
        self._run("DELETE FROM my_list WHERE media_type = ? AND tmdb_id = ?", (media_type, int(tmdb_id)))

    def contains(self, media_type, tmdb_id):
        return bool(self._run("SELECT 1 FROM my_list WHERE media_type = ? AND tmdb_id = ?",
                              (media_type, int(tmdb_id))))

    def all(self):
        """Saved titles, newest first (only the fields shown on a card)."""
        rows = self._run("SELECT media_type, tmdb_id, title, poster, year FROM my_list ORDER BY added_at DESC")
        return [media.Title(media_type=m, tmdb_id=i, title=t, poster=p, year=y) for m, i, t, p, y in rows]
