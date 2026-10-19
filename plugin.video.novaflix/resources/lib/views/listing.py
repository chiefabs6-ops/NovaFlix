"""Turns Show/Episode models into Kodi list items. Shared by all list views."""

from resources.lib import router
from resources.lib.kodi import paths, ui
from resources.lib.storage.favourites import Favourites

DUB_COLOUR = "FFFFC857"
_STATUS = {"FINISHED": "Ended", "RELEASING": "Continuing", "NOT_YET_RELEASED": "Upcoming",
           "CANCELLED": "Cancelled", "HIATUS": "Hiatus"}


def dub_badge(status):
    if status == "dubbed":
        return f" [COLOR {DUB_COLOUR}]{ui.string(30037)}[/COLOR]"
    if status == "partial":
        return f" [COLOR {DUB_COLOUR}]{ui.string(30038)}[/COLOR]"
    return ""


def show_info(show):
    return {
        "Title": show.title,
        "OriginalTitle": show.title_romaji,
        "Plot": show.description,
        "Year": show.year,
        "Genres": show.genres,
        "Rating": show.score / 10 if show.score else None,
        "Premiered": show.start_date if show.start_date and len(show.start_date) == 10 else None,
        "MediaType": "movie" if show.is_movie else "tvshow",
        "TvShowStatus": None if show.is_movie else _STATUS.get(show.status),
    }


def show_art(show, fanart=None):
    return {"poster": show.poster, "thumb": show.poster, "icon": show.poster, "fanart": fanart or show.banner}


def favourite_context(anilist_id, is_favourite):
    if is_favourite:
        return [(ui.string(30061), router.build_url("favourites/remove", id=anilist_id))]
    return [(ui.string(30060), router.build_url("favourites/add", id=anilist_id))]


def history_context(anilist_id):
    from resources.lib.views import history
    return history.show_context(anilist_id)


def add_show(handle, show, dub_status=None, label=None, favourite_ids=None):
    ui.add_video_item(
        handle,
        router.build_url("show", id=show.anilist_id),
        (label or show.title) + dub_badge(dub_status),
        show_info(show),
        show_art(show),
        is_folder=True,
        context=favourite_context(show.anilist_id, show.anilist_id in (favourite_ids or ()))
        + history_context(show.anilist_id),
    )


def add_next_page(handle, path, page, **params):
    ui.add_item(handle, ui.string(30030), router.build_url(path, page=page + 1, **params))


def list_shows(request, shows, more, catalog, path, **params):
    page = int(request.params.get("page", 1))
    fav_ids = favourite_ids()
    for show in shows:
        add_show(request.handle, show, catalog.dub_status(show), favourite_ids=fav_ids)
    if more:
        add_next_page(request.handle, path, page, **params)
    ui.set_content(request.handle, "tvshows")
    ui.end_directory(request.handle)


def favourite_ids():
    favs = Favourites(paths.profile_dir())
    try:
        return favs.ids()
    finally:
        favs.close()
