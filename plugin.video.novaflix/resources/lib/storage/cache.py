"""Disposable key/value cache in cache.db (DEC-034).

Kept in its own file so "Clear cache" can never touch user.db. If the file
is damaged it is deleted and rebuilt — losing a cache is harmless.
"""

import json
import os
import sqlite3
import time

from resources.lib.kodi import log

CACHE_DB = "cache.db"
_clock = time.time

_SCHEMA = "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL NOT NULL)"


class Cache:
    def __init__(self, directory):
        self._path = os.path.join(directory, CACHE_DB)
        self._conn = self._open()

    def _open(self):
        try:
            return self._connect()
        except sqlite3.DatabaseError:
            log.warning("cache.db unreadable; recreating it")
            for suffix in ("", "-wal", "-shm"):
                if os.path.exists(self._path + suffix):
                    os.remove(self._path + suffix)
            return self._connect()

    def _connect(self):
        conn = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(_SCHEMA)
        except sqlite3.DatabaseError:
            conn.close()  # Windows cannot delete a file that is still open
            raise
        return conn

    def get(self, key, default=None):
        row = self._conn.execute("SELECT value, expires_at FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None or row[1] <= _clock():
            return default
        return json.loads(row[0])

    def set(self, key, value, ttl):
        self._conn.execute(
            "INSERT OR REPLACE INTO kv (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), _clock() + ttl),
        )

    def delete(self, key):
        self._conn.execute("DELETE FROM kv WHERE key = ?", (key,))

    def purge_expired(self):
        return self._conn.execute("DELETE FROM kv WHERE expires_at <= ?", (_clock(),)).rowcount

    def clear(self):
        self._conn.execute("DELETE FROM kv")
        self._conn.execute("VACUUM")

    def close(self):
        self._conn.close()
