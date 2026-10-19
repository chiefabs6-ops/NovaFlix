"""My MyAnimeList (DEC-015; uses the MAL login when there is one, M13) and local Favourites (DEC-031)."""

from resources.lib import router
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata import mal
from resources.lib.metadata.catalog import Catalog
from resources.lib.models import Show
from resources.lib.myanimelist import auth
from resources.lib.storage.cache import Cache
from resources.lib.storage.favourites import Favourites
from resources.lib.views import listing

MAL_LIST_TTL = 30 * 60
STATUS_STRINGS = {"watching": 30070, "plan_to_watch": 30071, "completed": 30072,
                  "on_hold": 30073, "dropped": 30074}


def _mal_settings():
    return ui.setting("mal_client_id"), ui.setting("mal_username")


def _mal_ready(client_id, username):
    """A client ID plus either a username (public list) or a MyAnimeList login."""
    return bool(client_id) and (bool(username) or auth.MalStore(paths.profile_dir()).logged_in)


def _setup_prompt(request):
    ui.end_directory(request.handle, succeeded=False)
    if ui.confirm(ui.string(30003), ui.string(30075)):
        ui.open_settings()


def mal_menu(request):
    client_id, username = _mal_settings()
    if not _mal_ready(client_id, username):
        _setup_prompt(request)
        return
    for status in mal.STATUSES:
        ui.add_item(request.handle, ui.string(STATUS_STRINGS[status]), router.build_url("mal/list", status=status))
    ui.end_directory(request.handle)


def _mal_page(client_id, username, status, page):
    cache = Cache(paths.profile_dir())
    store = auth.MalStore(paths.profile_dir())
    if store.logged_in:
        key = f"mal:@me:{status}:{page}"
        cached = cache.get(key)
        if cached is not None:
            return [mal.MalEntry(**e) for e in cached["entries"]], cached["more"]
        from resources.lib.myanimelist.api import MalApi
        try:
            entries, more = MalApi(store).list_page(status, page)
        except auth.MalLoggedOut:
            log.warning("MyAnimeList login expired; using the public list")
        else:
            cache.set(key, {"entries": [e.__dict__ for e in entries], "more": more}, MAL_LIST_TTL)
            return entries, more
    key = f"mal:{username.lower()}:{status}:{page}"
    cached = cache.get(key)
    if cached is not None:
        return [mal.MalEntry(**e) for e in cached["entries"]], cached["more"]
    entries, more = mal.fetch_list(client_id, username, status, page)
    cache.set(key, {"entries": [e.__dict__ for e in entries], "more": more}, MAL_LIST_TTL)
    return entries, more


def mal_list(request):
    client_id, username = _mal_settings()
    status = request.params.get("status", "watching")
    page = int(request.params.get("page", 1))
    try:
        entries, more = _mal_page(client_id, username, status, page)
    except mal.MalSetupMissing:
        _setup_prompt(request)
        return
    except mal.MalUserUnavailable as exc:
        log.warning(str(exc))
        ui.end_directory(request.handle, succeeded=False)
        ui.confirm(ui.string(30003), ui.string(30076) % username)
        return
    except mal.MalClientRejected as exc:
        log.warning(str(exc))
        ui.end_directory(request.handle, succeeded=False)
        if ui.confirm(ui.string(30003), ui.string(30077)):
            ui.open_settings()
        return

    catalog = Catalog()
    shows = catalog.by_mal_ids([e.mal_id for e in entries])
    fav_ids = listing.favourite_ids()
    for entry in entries:
        show = shows.get(entry.mal_id)
        progress = f" [COLOR FF9E9E9E]({entry.watched}/{show.episodes_total or '?'})[/COLOR]" if show else ""
        if show:
            listing.add_show(request.handle, show, catalog.dub_status(show),
                             label=show.title + progress, favourite_ids=fav_ids)
        else:
            # AniList has no matching entry: show it, but say why it can't open.
            ui.add_item(request.handle, f"{entry.title} [COLOR FF9E9E9E]({ui.string(30078)})[/COLOR]",
                        router.build_url("noop"), is_folder=False, art={"poster": entry.picture, "thumb": entry.picture})
    if more:
        listing.add_next_page(request.handle, "mal/list", page, status=status)
    ui.set_content(request.handle, "tvshows")
    ui.end_directory(request.handle, cache=False)


def favourites(request):
    favs = Favourites(paths.profile_dir())
    try:
        rows = favs.all()
    finally:
        favs.close()
    catalog = Catalog()
    for anilist_id, title, poster, mal_id in rows:
        badge = listing.dub_badge(catalog.dub_status(Show(anilist_id=anilist_id, title=title, mal_id=mal_id)))
        ui.add_item(request.handle, title + badge, router.build_url("show", id=anilist_id),
                    art={"poster": poster, "thumb": poster, "icon": poster},
                    context=listing.favourite_context(anilist_id, True))
    if not rows:
        ui.add_item(request.handle, ui.string(30062), router.build_url("noop"), is_folder=False)
    ui.set_content(request.handle, "tvshows")
    ui.end_directory(request.handle, cache=False)


def favourite_add(request):
    show = Catalog().show(request.params["id"])
    favs = Favourites(paths.profile_dir())
    try:
        favs.add(show)
    finally:
        favs.close()
    ui.notify(show.title, ui.string(30063))
    ui.refresh()


def favourite_remove(request):
    favs = Favourites(paths.profile_dir())
    try:
        favs.remove(request.params["id"])
    finally:
        favs.close()
    ui.notify("NovaFlix", ui.string(30064))
    ui.refresh()
