# plugin.video.aniverse/resources/lib/gui/lists.py
"""Data for every AniVerse screen (M12), from the existing catalog, history, favourites,
MyAnimeList and playback-service code. Returns cards only; no Kodi windows here."""

import re
from dataclasses import dataclass, field

from resources.lib import router
from resources.lib.gui import cards
from resources.lib.kodi import paths, ui
from resources.lib.metadata import franchise, mal
from resources.lib.metadata.catalog import Catalog
from resources.lib.models import Show
from resources.lib.myanimelist import progress
from resources.lib.storage import db
from resources.lib.storage.favourites import Favourites
from resources.lib.views import browse, mylists
from resources.lib.views.show import ROW_STRINGS, entry_details

ROW_LIMIT = 20
VIDEO = re.compile(r"\.(mkv|mp4|avi|m4v|webm|ts|mov)$", re.I)
TITLES = {"trending": 30007, "popular": 30008, "airing": 30005, "upcoming": 30009, "recent": 30006,
          "continue": 30001, "favourites": 30004, "genres": 30010, "search": 30002, "mal": 30003}
PAGED = {"trending": "trending", "popular": "popular", "airing": "airing_this_season", "upcoming": "upcoming"}


class ServiceMissing(Exception):
    """No TorBox API key / Real-Debrid login yet."""


@dataclass
class Page:
    title: str
    cards: list = field(default_factory=list)
    more: bool = False
    empty: str = ""
    shows: list = field(default_factory=list)   # raw Show objects of show lists (hero uses Trending's)


@dataclass
class RelatedPage:
    title: str
    rows: list = field(default_factory=list)   # [(row title, [Card])], non-empty rows in franchise.ROWS order
    notice: str = ""                            # AniList failed mid-walk
    empty: str = ""                             # no rows at all


def _shows(catalog, shows):
    return [cards.show_card(s, catalog.dub_status(s)) for s in shows]


def load(key, page=1):
    catalog = Catalog()
    text = ui.string
    name, _, arg = key.partition(":")
    if name in PAGED:
        shows, more = getattr(catalog, PAGED[name])(page)
        return Page(text(TITLES[name]), _shows(catalog, shows), more, text(30039), shows)
    if name == "recent":
        rows = [cards.recent_card(s, ep, at, catalog.dub_status(s), text) for s, ep, at in catalog.recently_aired()]
        return Page(text(30006), rows, False, text(30039))
    if name == "continue":
        return Page(text(30001), _continue_cards(catalog, arg != "local", text), False, text(30226))
    if name == "favourites":
        favs = Favourites(paths.profile_dir())
        try:
            entries = favs.all()
        finally:
            favs.close()
        rows = [cards.show_card(Show(anilist_id=i, title=t, poster=p, mal_id=m),
                                catalog.dub_status(Show(anilist_id=i, title=t, mal_id=m)))
                for i, t, p, m in entries]
        return Page(text(30004), rows, False, text(30062))
    if name == "genres":
        return Page(text(30010), [cards.tile(g, ("grid", f"genre:{g}"), icon="grid_view") for g in catalog.genres()])
    if name == "genre":
        shows, more = catalog.by_genre(arg, page)
        return Page(arg, _shows(catalog, shows), more, text(30039))
    if name == "search" and not arg:
        from resources.lib.net import phone_keyboard
        phone = [cards.tile(text(30318), ("search_phone",), icon="smartphone")]
        if phone_keyboard.load_pairing(paths.profile_dir()):
            phone.append(cards.tile(text(30324), ("phone_unpair",), icon="cancel"))
        return Page(text(30002), [cards.tile(text(30031), ("search_new",), icon="search")] + phone
                    + [cards.tile(q, ("grid", f"search:{q}"), icon="history") for q in _recent_searches()])
    if name == "search":
        _remember_search(arg)
        shows, more = catalog.search(arg, page)
        return Page(text(30245) % arg, _shows(catalog, shows), more, text(30039))
    if name == "mal" and not arg:
        client_id, username = mylists._mal_settings()
        if not mylists._mal_ready(client_id, username):
            raise mal.MalSetupMissing("MyAnimeList client ID or username missing")
        return Page(text(30003), [cards.tile(text(mylists.STATUS_STRINGS[s]), ("grid", f"mal:{s}"),
                                             icon="format_list_bulleted") for s in mal.STATUSES])
    if name == "mal":
        return _mal_status(catalog, arg, page, text)
    if name == "torbox" and not arg:
        return _service_torrents(text)
    if name == "torbox":
        return _service_files(arg)
    raise KeyError(key)


def _check_next(card, show, number, text):
    """MyAnimeList lists: the label shows whether the next episode can be watched (and with
    Dub only on, whether it is dubbed). The card still opens the show page."""
    from resources.lib.sources import availability
    if show.episodes_total and number > show.episodes_total:
        return  # caught up with a finished or fully announced series: keep "watched/total"
    card.label2 = text(30299) % number
    card.avail, card.check, card.check_play = "checking", (show.anilist_id, number), False
    known = availability.cached(show.anilist_id, number)
    if known is not None:
        cards.apply_availability(card, known, text)


def _continue_cards(catalog, network, text):
    """Started shows only (progress.started), not Completed / Dropped / On Hold on MAL, one card
    per show, never an episode past the end. Saved availability is applied at once; the rest is
    checked in the background by the window (card.check)."""
    from resources.lib.sources import availability
    out, seen = [], set()
    for row in progress.continue_rows(network=network):
        if row["anilist_id"] in seen or not progress.started(row) or progress.inactive(row):
            continue
        saved = catalog.cached_show(row["anilist_id"])
        total = row["episodes_total"] or (saved.episodes_total if saved else None)
        if row["watched"] and total and row["episode"] + 1 > total:
            continue  # finished the show
        card = cards.continue_card(row, saved, text)
        if card.check:
            known = availability.cached(*card.check)
            if known is not None and known.state == availability.FINISHED:
                continue
            if known is not None:
                cards.apply_availability(card, known, text)
        seen.add(row["anilist_id"])
        out.append(card)
    return out


def home_row(key):
    page = load(key)
    if len(page.cards) > ROW_LIMIT or page.more:
        grid_key = "continue" if key == "continue:local" else key
        page.cards = page.cards[:ROW_LIMIT] + [cards.more_card(grid_key, ui.string)]
    return page


def related(anilist_id):
    """Related & sequels as franchise rows (M14, DEC-062)."""
    catalog = Catalog()
    text = ui.string
    result = catalog.franchise(int(anilist_id))
    rows = []
    for name in franchise.ROWS:
        entries = result.rows.get(name) or []
        if entries:
            rows.append((text(ROW_STRINGS[name]), [
                cards.Card(label=n.title, label2=entry_details(n), poster=cards.small_cover(n.poster),
                           dub=catalog.dub_status(n) or "", action=("show", n.anilist_id)) for n in entries]))
    return RelatedPage(result.title, rows, text(30288) if result.partial else "", "" if rows else text(30231))


def _recent_searches():
    conn = db.open_user_db(paths.profile_dir())
    try:
        return browse._recent_queries(conn)
    finally:
        conn.close()


def _remember_search(text):
    conn = db.open_user_db(paths.profile_dir())
    try:
        browse._remember(conn, text)
    finally:
        conn.close()


def _mal_status(catalog, status, page, text):
    client_id, username = mylists._mal_settings()
    entries, more = mylists._mal_page(client_id, username, status, page)
    shows = catalog.by_mal_ids([e.mal_id for e in entries])
    rows = []
    for entry in entries:
        found = shows.get(entry.mal_id)
        if found:
            card = cards.show_card(found, catalog.dub_status(found))
            card.label2 = f"{entry.watched}/{found.episodes_total or '?'}"
            if status != "completed":
                _check_next(card, found, entry.watched + 1, text)
        else:
            card = cards.Card(label=entry.title, label2=text(30078), poster=entry.picture, action=("noop",))
        rows.append(card)
    return Page(text(mylists.STATUS_STRINGS[status]), rows, more, text(30256))


MAL_COUNT_PAGES = 10  # counts stop at 1000 entries per status ("1000+")


def mal_count(status):
    """(entries with this status on the user's MyAnimeList, True when there are more than counted).
    Uses the same cached pages as the status grid, so opening a status afterwards is instant."""
    client_id, username = mylists._mal_settings()
    total = 0
    for page in range(1, MAL_COUNT_PAGES + 1):
        entries, more = mylists._mal_page(client_id, username, status, page)
        total += len(entries)
        if not more:
            return total, False
    return total, True


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
