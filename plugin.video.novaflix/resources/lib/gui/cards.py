# plugin.video.novaflix/resources/lib/gui/cards.py
"""Card models for the NovaFlix screens (M12). Pure: no Kodi imports.

`text` arguments are callables string_id -> str (callers pass ui.string).
Missing data stays missing (DEC-004): no invented titles or art.
"""

from dataclasses import dataclass
from typing import Optional

PLOT_MAX = 300


@dataclass
class Card:
    label: str
    label2: str = ""
    poster: Optional[str] = None
    wide: Optional[str] = None
    position: float = 0.0
    duration: float = 0.0
    watched: bool = False
    note: str = ""
    status: str = ""
    kind: str = "show"
    action: tuple = ()
    avail: str = ""        # availability state shown by the layouts (not filled yet: deferred)


def clock(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def tile(label, action, icon=None):
    return Card(label=label, kind="tile", wide=f"icon:{icon}" if icon else None, action=action)


def more_card(key, text):
    return Card(label=text(30237), kind="more", action=("grid", key))


def source_row(line1, line2, text):
    if not line2:
        return Card(label=line1, kind="source", status="action")
    last = line2.rsplit(" · ", 1)[-1]
    ready_in = text(30144).split("%s")[0]
    if last == text(30193) or last.startswith(ready_in):
        status = "ready"
    elif last == text(30194):
        status = "download"
    elif last == text(30192):
        status = "blocked"
    else:
        status = "unchecked"
    return Card(label=line1, label2=line2, kind="source", status=status, note=last)


def next_episode(numbers, states):
    """(episode, resume_s): the lowest started-unwatched episode, else the first unwatched,
    else episode 1 (everything watched: start again)."""
    started = [n for n in numbers if n in states and states[n][0] > 0 and not states[n][2]]
    if started:
        n = min(started)
        return n, int(states[n][0])
    for n in numbers:
        if not (n in states and states[n][2]):
            return n, 0
    return (numbers[0] if numbers else 1), 0


# -- TV shows and movies (TMDB, Plan 4) ------------------------------------------------------------

def title_card(title):
    return Card(label=title.title, label2=str(title.year) if title.year else "", poster=title.poster,
                wide=title.backdrop, action=("title", title.media_type, title.tmdb_id))


def title_continue_card(row, next_ref, text):
    """Continue Watching from a WatchHistory row. next_ref: (season, episode) after a watched one,
    or None when not known yet (the card opens the title page). Callers leave out caught-up titles."""
    movie = row["media_type"] == "movie"
    card = Card(label=row["title"], poster=row["poster"], wide=row["backdrop"])
    ident = (row["media_type"], row["tmdb_id"])
    if row["watched"]:
        if next_ref is None:
            card.action = ("title",) + ident
            return card
        card.label2 = text(30421) % tuple(next_ref)
        card.action = ("watch",) + ident + (next_ref[0], next_ref[1], 0)
        return card
    season, episode = (None, None) if movie else (row["season"], row["episode"])
    position, duration = row["position_s"] or 0.0, row["duration_s"] or 0.0
    if position and duration:
        left = clock(duration - position)
        card.label2 = text(30422) % left if movie else text(30420) % (season, episode, left)
        card.position, card.duration = position, duration
    elif not movie:
        card.label2 = text(30404) % (season, episode)
    card.action = ("watch",) + ident + (season, episode, int(position))
    return card


def title_episode_card(title, episode, state, text):
    label = f"{episode.number}. {episode.title}" if episode.title else text(30036) % episode.number
    details = [episode.air_date, text(30258) % episode.runtime_min if episode.runtime_min else None]
    position, duration, watched = state or (0.0, 0.0, False)
    return Card(label=label, label2=" · ".join(d for d in details if d), wide=episode.still or title.backdrop,
                position=0.0 if watched else position, duration=duration, watched=watched, kind="episode",
                action=("t_episode", title.tmdb_id, episode.season, episode.number))


def title_movie_card(title, state, text):
    """The film itself as the one card of a movie's page (season 0, episode 0)."""
    position, duration, watched = state or (0.0, 0.0, False)
    details = [str(title.year) if title.year else None,
               text(30258) % title.runtime_min if title.runtime_min else None]
    return Card(label=title.title, label2=" · ".join(d for d in details if d), wide=title.backdrop,
                position=0.0 if watched else position, duration=duration, watched=watched, kind="episode",
                action=("t_episode", title.tmdb_id, 0, 0))


def title_meta(title, text):
    from resources.lib import media
    seasons = len([s for s in title.seasons if s.number > 0])
    parts = [str(title.year) if title.year else None,
             text(30429) if title.is_movie else text(30430),
             text(30431) % seasons if seasons and not title.is_movie else None,
             text(30258) % title.runtime_min if title.is_movie and title.runtime_min else None,
             f"★ {title.rating:.1f}" if title.rating else None,
             media.language_name(title.original_language) if title.original_language not in (None, "en") else None]
    return " · ".join(p for p in parts if p)


def title_hero(title, text=None):
    plot = (title.overview or "").replace("\n", " ").strip()
    if len(plot) > PLOT_MAX:
        plot = plot[:PLOT_MAX - 1].rsplit(" ", 1)[0] + "…"
    alt = title.original_title if title.original_title and title.original_title != title.title else ""
    return {"title": title.title, "alt": alt, "plot": plot, "art": title.backdrop or title.poster or "",
            "dark": not title.backdrop, "meta": title_meta(title, text) if text else ""}
