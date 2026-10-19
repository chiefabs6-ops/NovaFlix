"""Torrents this add-on added to TorBox (user.db added_torrents).

Only these may be removed automatically (DEC-019); anything the owner added
is never touched. keep=1 means the owner chose to keep it for later.
"""

import time

from resources.lib.storage import db


class AddedTorrents:
    def __init__(self, directory):
        self._directory = directory

    def _run(self, sql, args=()):
        conn = db.open_user_db(self._directory)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def remember(self, torrent_id, info_hash):
        self._run("INSERT OR REPLACE INTO added_torrents (rd_torrent_id, info_hash, added_at, keep) VALUES (?, ?, ?, 0)",
                  (str(torrent_id), info_hash, time.time()))

    def is_ours(self, torrent_id):
        return bool(self._run("SELECT 1 FROM added_torrents WHERE rd_torrent_id = ?", (str(torrent_id),)))

    def is_kept(self, torrent_id):
        rows = self._run("SELECT keep FROM added_torrents WHERE rd_torrent_id = ?", (str(torrent_id),))
        return bool(rows and rows[0][0])

    def keep(self, torrent_id):
        self._run("UPDATE added_torrents SET keep = 1 WHERE rd_torrent_id = ?", (str(torrent_id),))

    def forget(self, torrent_id):
        self._run("DELETE FROM added_torrents WHERE rd_torrent_id = ?", (str(torrent_id),))
