"""Recent searches (user.db search_history), newest first, without duplicates."""

import time

from resources.lib.storage import db

MAX_RECENT = 10
_clock = time.time


def recent(directory, limit=MAX_RECENT):
    conn = db.open_user_db(directory)
    try:
        rows = conn.execute("SELECT query FROM search_history ORDER BY used_at DESC LIMIT ?", (int(limit),))
        return [r[0] for r in rows]
    finally:
        conn.close()


def remember(directory, text):
    conn = db.open_user_db(directory)
    try:
        conn.execute("INSERT OR REPLACE INTO search_history (query, used_at) VALUES (?, ?)", (text, _clock()))
        conn.execute("DELETE FROM search_history WHERE query NOT IN "
                     "(SELECT query FROM search_history ORDER BY used_at DESC LIMIT ?)", (MAX_RECENT,))
    finally:
        conn.close()
