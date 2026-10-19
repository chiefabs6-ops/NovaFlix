"""Watch history in user.db (DEC-005, DEC-028, DEC-029, DEC-032).

Written by the service's player monitor and by manual marks. Lives in
user.db, so "Clear cache" never touches it.
"""

import time

from resources.lib.storage import db

WATCHED_AT = 0.90       # DEC-028
MIN_RESUME_S = 60       # shorter than this: start from the beginning next time

_clock = time.time


class History:
    def __init__(self, directory):
        self._directory = directory

    def _run(self, sql, args=()):
        conn = db.open_user_db(self._directory)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def save_position(self, anilist_id, episode, mal_id, position_s, duration_s):
        """Store progress; at >= 90 % the episode becomes watched (resume point cleared).
        A rewatch never un-marks a watched episode. Returns True if now watched."""
        watched = bool(duration_s) and position_s >= WATCHED_AT * duration_s
        resume = 0 if watched or position_s < MIN_RESUME_S else position_s
        self._run(
            "INSERT INTO history (anilist_id, episode, mal_id, position_s, duration_s, watched, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(anilist_id, episode) DO UPDATE SET "
            "mal_id = COALESCE(excluded.mal_id, mal_id), position_s = excluded.position_s, "
            "duration_s = excluded.duration_s, watched = MAX(watched, excluded.watched), updated_at = excluded.updated_at",
            (int(anilist_id), int(episode), mal_id, float(resume), float(duration_s or 0), int(watched), _clock()))
        return watched

    def mark(self, anilist_id, episode, watched):
        """Manual mark (DEC-032): either way the resume point is cleared."""
        self._run(
            "INSERT INTO history (anilist_id, episode, position_s, duration_s, watched, updated_at) "
            "VALUES (?, ?, 0, 0, ?, ?) ON CONFLICT(anilist_id, episode) DO UPDATE SET "
            "position_s = 0, watched = excluded.watched, updated_at = excluded.updated_at",
            (int(anilist_id), int(episode), int(bool(watched)), _clock()))

    def mark_show(self, anilist_id, episodes, watched):
        if not watched:
            self._run("DELETE FROM history WHERE anilist_id = ?", (int(anilist_id),))
            return
        for episode in episodes:
            self.mark(anilist_id, episode, True)

    def states(self, anilist_id):
        """{episode: (position_s, duration_s, watched)} for one show."""
        rows = self._run("SELECT episode, position_s, duration_s, watched FROM history WHERE anilist_id = ?",
                         (int(anilist_id),))
        return {ep: (pos, dur, bool(w)) for ep, pos, dur, w in rows}

    def remember_show(self, show):
        """Title/poster for Continue Watching, so that menu needs no network."""
        self._run(
            "INSERT INTO show_prefs (anilist_id, title, poster, mal_id, episodes_total, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(anilist_id) DO UPDATE SET title = excluded.title, "
            "poster = excluded.poster, mal_id = excluded.mal_id, episodes_total = excluded.episodes_total",
            (int(show.anilist_id), show.title, show.poster, show.mal_id, show.episodes_total, _clock()))

    def mal_id(self, anilist_id):
        """The show's MAL ID from saved data (no network), or None."""
        rows = self._run(
            "SELECT mal_id FROM show_prefs WHERE anilist_id = ? AND mal_id IS NOT NULL "
            "UNION ALL SELECT mal_id FROM history WHERE anilist_id = ? AND mal_id IS NOT NULL LIMIT 1",
            (int(anilist_id), int(anilist_id)))
        return rows[0][0] if rows else None

    def continue_watching(self, limit=50):
        """Started shows, most recent first (DEC-029): the latest history row of each
        show plus the show's title. Rows: dict(anilist_id, title, poster, mal_id,
        episode, position_s, duration_s, watched, episodes_total)."""
        rows = self._run(
            "SELECT h.anilist_id, p.title, p.poster, p.mal_id, h.episode, h.position_s, h.duration_s, h.watched, "
            "p.episodes_total, h.updated_at FROM history h JOIN show_prefs p ON p.anilist_id = h.anilist_id "
            "WHERE p.title IS NOT NULL AND h.updated_at = "
            "(SELECT MAX(updated_at) FROM history WHERE anilist_id = h.anilist_id) "
            "ORDER BY h.updated_at DESC LIMIT ?", (int(limit),))
        keys = ("anilist_id", "title", "poster", "mal_id", "episode", "position_s", "duration_s", "watched",
                "episodes_total", "updated_at")
        out, seen = [], set()
        for row in rows:
            item = dict(zip(keys, row))
            if item["anilist_id"] in seen:
                continue  # two rows with the same timestamp
            seen.add(item["anilist_id"])
            item["watched"] = bool(item["watched"])
            out.append(item)
        return out
