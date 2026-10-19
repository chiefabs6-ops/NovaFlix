"""Catalog sections (DEC-033): season, recent, trending, popular, upcoming, genres, search."""

import time

from resources.lib import router
from resources.lib.kodi import paths, ui
from resources.lib.metadata.catalog import Catalog
from resources.lib.storage import db
from resources.lib.views import listing

MAX_RECENT_SEARCHES = 20


def _page(request):
    return int(request.params.get("page", 1))


def airing(request):
    catalog = Catalog()
    shows, more = catalog.airing_this_season(_page(request))
    listing.list_shows(request, shows, more, catalog, "airing")


def upcoming(request):
    catalog = Catalog()
    shows, more = catalog.upcoming(_page(request))
    listing.list_shows(request, shows, more, catalog, "upcoming")


def trending(request):
    catalog = Catalog()
    shows, more = catalog.trending(_page(request))
    listing.list_shows(request, shows, more, catalog, "trending")


def popular(request):
    catalog = Catalog()
    shows, more = catalog.popular(_page(request))
    listing.list_shows(request, shows, more, catalog, "popular")


def genres(request):
    for name in Catalog().genres():
        ui.add_item(request.handle, name, router.build_url("genre", name=name))
    ui.end_directory(request.handle)


def genre(request):
    catalog = Catalog()
    name = request.params["name"]
    shows, more = catalog.by_genre(name, _page(request))
    listing.list_shows(request, shows, more, catalog, "genre", name=name)


def recent(request):
    catalog = Catalog()
    fav_ids = listing.favourite_ids()
    for show, episode, _ in catalog.recently_aired():
        label = f"{show.title} — {ui.string(30036) % episode}"
        listing.add_show(request.handle, show, catalog.dub_status(show), label=label, favourite_ids=fav_ids)
    ui.set_content(request.handle, "tvshows")
    ui.end_directory(request.handle)


# -- search -------------------------------------------------------------------

def _recent_queries(conn):
    rows = conn.execute("SELECT query FROM search_history ORDER BY used_at DESC LIMIT ?", (MAX_RECENT_SEARCHES,))
    return [r[0] for r in rows]


def _remember(conn, text):
    conn.execute("INSERT OR REPLACE INTO search_history (query, used_at) VALUES (?, ?)", (text, time.time()))
    conn.execute(
        "DELETE FROM search_history WHERE query NOT IN "
        "(SELECT query FROM search_history ORDER BY used_at DESC LIMIT ?)", (MAX_RECENT_SEARCHES,))


def search_menu(request):
    # Not a folder: Kodi runs it as an action, so the keyboard never reopens on Back
    # and the container is free to switch to the results list.
    ui.add_item(request.handle, ui.string(30031), router.build_url("search/new"), is_folder=False)
    conn = db.open_user_db(paths.profile_dir())
    try:
        queries = _recent_queries(conn)
    finally:
        conn.close()
    for text in queries:
        ui.add_item(request.handle, text, router.build_url("search/results", q=text))
    if queries:
        ui.add_item(request.handle, ui.string(30033), router.build_url("search/clear"), is_folder=False)
    ui.end_directory(request.handle, cache=False)


def search_new(request):
    text = ui.keyboard(ui.string(30032))
    if text:
        ui.container_update(router.build_url("search/results", q=text))


def search_results(request):
    text = request.params.get("q", "").strip()
    if not text:
        ui.end_directory(request.handle, succeeded=False)
        return
    conn = db.open_user_db(paths.profile_dir())
    try:
        _remember(conn, text)
    finally:
        conn.close()
    catalog = Catalog()
    shows, more = catalog.search(text, _page(request))
    if not shows:
        ui.notify(ui.string(30002), ui.string(30039))
    listing.list_shows(request, shows, more, catalog, "search/results", q=text)


def search_clear(request):
    conn = db.open_user_db(paths.profile_dir())
    try:
        conn.execute("DELETE FROM search_history")
    finally:
        conn.close()
    ui.container_update(router.build_url("search"))
