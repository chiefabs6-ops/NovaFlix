"""Watch history for TMDB movies and episodes (user.db v5, Plan 3).

Watched at 90 %, no resume point under
60 s, a rewatch never un-marks. Movies are stored as season 0, episode 0. Lives in user.db, so
"Clear cache" never touches it.
"""

import time

from resources.lib.storage import db

WATCHED_AT = 0.90       # share of the duration that counts as watched (DEC-028)
MIN_RESUME_S = 60       # shorter than this: start from the beginning next time
_clock = time.time


class WatchHistory:
    def __init__(self, directory):
        self._directory = directory

    def _run(self, sql, args=()):
        conn = db.open_user_db(self._directory)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def save_position(self, media_type, tmdb_id, season, episode, position_s, duration_s):
        """Store progress; returns True when the episode or movie is now watched."""
        watched = bool(duration_s) and position_s >= WATCHED_AT * duration_s
        resume = 0 if watched or position_s < MIN_RESUME_S else position_s
        self._run(
            "INSERT INTO watch_history (media_type, tmdb_id, season, episode, position_s, duration_s, watched, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(media_type, tmdb_id, season, episode) DO UPDATE "
            "SET position_s = excluded.position_s, duration_s = excluded.duration_s, "
            "watched = MAX(watched, excluded.watched), updated_at = excluded.updated_at",
            (media_type, int(tmdb_id), int(season), int(episode), float(resume), float(duration_s or 0),
             int(watched), _clock()))
        return watched

    def mark(self, media_type, tmdb_id, season, episode, watched):
        """Manual mark: either way the resume point is cleared."""
        self._run(
            "INSERT INTO watch_history (media_type, tmdb_id, season, episode, position_s, duration_s, watched, "
            "updated_at) VALUES (?, ?, ?, ?, 0, 0, ?, ?) ON CONFLICT(media_type, tmdb_id, season, episode) DO UPDATE "
            "SET position_s = 0, watched = excluded.watched, updated_at = excluded.updated_at",
            (media_type, int(tmdb_id), int(season), int(episode), int(bool(watched)), _clock()))

    def forget(self, media_type, tmdb_id):
        """Mark unwatched: every watched mark and resume point of the title goes."""
        self._run("DELETE FROM watch_history WHERE media_type = ? AND tmdb_id = ?", (media_type, int(tmdb_id)))

    def last_watched(self, media_type, tmdb_id):
        """(season, episode) of the title's most recent history row, or None."""
        rows = self._run("SELECT season, episode FROM watch_history WHERE media_type = ? AND tmdb_id = ? "
                         "ORDER BY updated_at DESC LIMIT 1", (media_type, int(tmdb_id)))
        return tuple(rows[0]) if rows else None

    def states(self, media_type, tmdb_id):
        """{(season, episode): (position_s, duration_s, watched)} for one title."""
        rows = self._run("SELECT season, episode, position_s, duration_s, watched FROM watch_history "
                         "WHERE media_type = ? AND tmdb_id = ?", (media_type, int(tmdb_id)))
        return {(s, e): (pos, dur, bool(w)) for s, e, pos, dur, w in rows}

    def remember_title(self, title):
        """Title and art for Continue Watching, so that row needs no network. Keeps the last choice."""
        self._run(
            "INSERT INTO title_prefs (media_type, tmdb_id, title, poster, backdrop, year, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(media_type, tmdb_id) DO UPDATE SET title = excluded.title, "
            "poster = excluded.poster, backdrop = excluded.backdrop, year = excluded.year",
            (title.media_type, int(title.tmdb_id), title.title, title.poster, title.backdrop, title.year, _clock()))

    def remember_choice(self, media_type, tmdb_id, candidate):
        """DEC-024: the next episode pins the same release group + resolution."""
        self._run(
            "INSERT INTO title_prefs (media_type, tmdb_id, last_release_group, last_resolution, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(media_type, tmdb_id) DO UPDATE SET "
            "last_release_group = excluded.last_release_group, last_resolution = excluded.last_resolution, "
            "updated_at = excluded.updated_at",
            (media_type, int(tmdb_id), candidate.release_group, candidate.resolution, _clock()))

    def last_choice(self, media_type, tmdb_id):
        rows = self._run("SELECT last_release_group, last_resolution FROM title_prefs "
                         "WHERE media_type = ? AND tmdb_id = ?", (media_type, int(tmdb_id)))
        return rows[0] if rows else (None, None)

    def continue_watching(self, limit=50):
        """Started titles, most recent first: the latest history row of each title plus its saved title."""
        rows = self._run(
            "SELECT h.media_type, h.tmdb_id, p.title, p.poster, p.backdrop, p.year, h.season, h.episode, "
            "h.position_s, h.duration_s, h.watched, h.updated_at FROM watch_history h JOIN title_prefs p "
            "ON p.media_type = h.media_type AND p.tmdb_id = h.tmdb_id WHERE p.title IS NOT NULL AND h.updated_at = "
            "(SELECT MAX(updated_at) FROM watch_history WHERE media_type = h.media_type AND tmdb_id = h.tmdb_id) "
            "ORDER BY h.updated_at DESC LIMIT ?", (int(limit),))
        keys = ("media_type", "tmdb_id", "title", "poster", "backdrop", "year", "season", "episode", "position_s",
                "duration_s", "watched", "updated_at")
        out, seen = [], set()
        for row in rows:
            item = dict(zip(keys, row))
            ident = (item["media_type"], item["tmdb_id"])
            if ident in seen:
                continue  # two rows with the same timestamp
            seen.add(ident)
            item["watched"] = bool(item["watched"])
            out.append(item)
        return out
