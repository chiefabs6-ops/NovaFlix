# plugin.video.novaflix/resources/lib/gui/lists.py
"""Data for every NovaFlix screen: TMDB titles (metadata/library.py), watch history, My List,
searches and My TorBox. Returns cards only; no Kodi windows here."""

import re
from dataclasses import dataclass, field

from resources.lib import errors, media, router
from resources.lib.gui import cards
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata.library import Library
from resources.lib.storage import searches
from resources.lib.storage.mylist import MyList
from resources.lib.storage.watching import WatchHistory

ROW_LIMIT = 20
VIDEO = re.compile(r"\.(mkv|mp4|avi|m4v|webm|ts|mov)$", re.I)
TITLES = {"trending": 30007, "popular_movies": 30410, "popular_tv": 30411, "top_movies": 30412, "top_tv": 30413,
          "airing_today": 30414, "continue": 30001, "mylist": 30415, "genres": 30010, "search": 30002}
LISTS = ("trending", "popular_movies", "popular_tv", "top_movies", "top_tv", "airing_today")
GENRE_GROUPS = ((media.MOVIE, 30416), (media.TV, 30417))


class ServiceMissing(Exception):
    """No TorBox API key yet."""


class TmdbKeyMissing(Exception):
    """No TMDB key yet: nothing can be browsed."""


@dataclass
class Page:
    title: str
    cards: list = field(default_factory=list)
    more: bool = False
    empty: str = ""
    titles: list = field(default_factory=list)   # raw Titles of title lists (the Home hero uses Trending's)


@dataclass
class RelatedPage:
    title: str
    rows: list = field(default_factory=list)   # [(row title, [Card])], non-empty rows only
    notice: str = ""
    empty: str = ""


def _library():
    library = Library()
    if not library.has_token:
        raise TmdbKeyMissing()
    return library


def _titles_page(title, titles, more):
    return Page(title, [cards.title_card(t) for t in titles], more, ui.string(30039), titles)


def load(key, page=1):
    text = ui.string
    name, _, arg = key.partition(":")
    if name in LISTS:
        titles, more = _library().list(name, page)
        return _titles_page(text(TITLES[name]), titles, more)
    if name == "continue":
        return Page(text(30001), _continue_cards(network=arg != "local"), False, text(30226))
    if name == "mylist":
        return Page(text(30415), [cards.title_card(t) for t in MyList(paths.profile_dir()).all()], False,
                    text(30428))
    if name == "genres":
        library = _library()
        tiles = []
        for media_type, group in GENRE_GROUPS:
            for genre_id, genre in library.genres(media_type):
                tile = cards.tile(genre, ("grid", f"genre:{media_type}:{genre_id}"), icon="grid_view")
                tile.label2 = text(group)
                tiles.append(tile)
        return Page(text(30010), tiles)
    if name == "genre":
        media_type, _, genre_id = arg.partition(":")
        library = _library()
        names = dict(library.genres(media_type))
        titles, more = library.by_genre(media_type, int(genre_id), page)
        group = dict(GENRE_GROUPS)[media_type]
        return _titles_page(f"{names.get(int(genre_id), '?')} · {text(group)}", titles, more)
    if name == "search" and not arg:
        from resources.lib.net import phone_keyboard
        phone = [cards.tile(text(30318), ("search_phone",), icon="smartphone")]
        if phone_keyboard.load_pairing(paths.profile_dir()):
            phone.append(cards.tile(text(30324), ("phone_unpair",), icon="cancel"))
        recent = [cards.tile(q, ("grid", f"search:{q}"), icon="history") for q in searches.recent(paths.profile_dir())]
        return Page(text(30002), [cards.tile(text(30031), ("search_new",), icon="search")] + phone + recent)
    if name == "search":
        library = _library()
        searches.remember(paths.profile_dir(), arg)
        titles, more = library.search(arg, page)
        return _titles_page(text(30245) % arg, titles, more)
    if name == "torbox" and not arg:
        return _service_torrents(text)
    if name == "torbox":
        return _service_files(arg)
    raise KeyError(key)


def _continue_cards(network):
    """Started titles, newest first. A watched episode offers the next aired one (network) or opens
    the title page (saved data only); a caught-up show and a watched movie are left out."""
    from resources.lib.sources import availability
    library = Library() if network else None
    out = []
    for row in WatchHistory(paths.profile_dir()).continue_watching():
        next_ref, upcoming = None, None
        if row["watched"]:
            if row["media_type"] == media.MOVIE:
                continue
            if library is not None and library.has_token:
                try:
                    title = library.title(row["media_type"], row["tmdb_id"])
                    next_ref = library.next_episode(title, row["season"], row["episode"])
                except errors.NovaFlixError as exc:
                    log.warning(f"continue watching: next of {row['media_type']}:{row['tmdb_id']} unknown: {exc}")
                    next_ref = ()  # unknown: open the title page
                else:
                    if next_ref is None:
                        upcoming = _next_air(title, row)
                        if upcoming is None:
                            continue  # caught up
        card = cards.title_continue_card(row, next_ref or None, ui.string, upcoming)
        if card.check:
            known = availability.cached(*card.check)  # saved result: no search needed
            if known is not None:
                cards.apply_availability(card, known, ui.string)
        out.append(card)
    return out


def _next_air(title, row):
    """(season, episode, air date) of a running show's announced next episode after the watched one, or None."""
    nxt = title.next_air
    if nxt and (nxt[0], nxt[1]) > (row["season"], row["episode"]):
        return nxt
    return None


def home_row(key):
    page = load(key)
    if len(page.cards) > ROW_LIMIT or page.more:
        grid_key = "continue" if key == "continue:local" else key
        page.cards = page.cards[:ROW_LIMIT] + [cards.more_card(grid_key, ui.string)]
    return page


def more_like_this(media_type, tmdb_id):
    """Rows for a title's "More like this": its movie collection first, then TMDB's recommendations."""
    library = _library()
    title = library.title(media_type, tmdb_id)
    rows = []
    if title.collection:
        collection = library.collection(title.collection[0])
        if collection.parts:
            rows.append((collection.name, [cards.title_card(t) for t in collection.parts]))
    recommended = library.more_like_this(media_type, tmdb_id)
    if recommended:
        rows.append((ui.string(30418), [cards.title_card(t) for t in recommended]))
    return RelatedPage(title.title, rows, "", "" if rows else ui.string(30039))


def _client():
    from resources.lib.debrid import service
    client = service.client()
    if client is None:
        raise ServiceMissing()
    return client


def _service_torrents(text):
    from resources.lib.debrid import service
    client = _client()
    rows = [cards.tile(text(30154), ("magnet",), icon="add_link")]
    for t in client.torrents():
        if t.get("status") == "downloaded":
            rows.append(cards.tile(t.get("filename") or "?", ("grid", f"torbox:{t['id']}"), icon="folder"))
    return Page(text(30011) % service.label(), rows)


def _service_files(torrent_id):
    info = _client().torrent_info(torrent_id)
    rows = []
    for f in info.get("files") or []:
        path = (f.get("path") or "").lstrip("/")
        if f.get("selected") and VIDEO.search(path):
            url = router.build_url("rd/play", torrent=info.get("id"), file=f.get("id"))
            rows.append(cards.tile(path, ("plugin_play", url), icon="movie"))
    return Page(info.get("filename") or "", rows)
