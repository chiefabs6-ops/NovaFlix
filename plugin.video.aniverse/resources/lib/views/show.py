"""Show page: episode list plus related entries (DEC-013, DEC-014)."""

import datetime

from resources.lib import router
from resources.lib.kodi import paths, ui
from resources.lib.metadata import franchise
from resources.lib.metadata.catalog import Catalog
from resources.lib.myanimelist import progress
from resources.lib.storage.history import History
from resources.lib.views import history, listing

FORMAT_LABELS = {"TV": "TV", "TV_SHORT": "TV Short", "MOVIE": "Movie", "SPECIAL": "Special",
                 "OVA": "OVA", "ONA": "ONA", "MUSIC": "Music"}
ROW_STRINGS = {"sequels": 30282, "prequels": 30283, "side_stories": 30284, "ovas": 30285,
               "movies": 30286, "other": 30287}


def entry_details(node):
    """'2019 · TV' for a franchise entry; parts that are unknown are left out."""
    parts = [str(node.start[0]) if node.start else None, FORMAT_LABELS.get(node.format, node.format)]
    return " · ".join(p for p in parts if p)

def show(request):
    catalog = Catalog()
    item = catalog.show(request.params["id"])
    fanart = catalog.fanart(item)

    if item.relations:
        ui.add_item(request.handle, ui.string(30034), router.build_url("related", id=item.anilist_id),
                    art={"icon": item.poster, "thumb": item.poster, "fanart": fanart})

    episodes = catalog.episodes(item)
    dub_dates = catalog.dub_estimates(item, [ep.number for ep in episodes])
    states = progress.merge_states(History(paths.profile_dir()).states(item.anilist_id),
                                   progress.show_entry(item.mal_id))
    for ep in episodes:
        label = f"{ep.number}. {ep.title}" if ep.title and not item.is_movie else (ep.title or ui.string(30036) % ep.number)
        plot = ep.overview
        if ep.number in dub_dates:
            note = dub_note(dub_dates[ep.number])
            label += f" [COLOR grey]({note})[/COLOR]"
            plot = f"{note} ({ui.string(30052)})" + (f"\n\n{plot}" if plot else "")
        info = {
            "Title": ep.title or ui.string(30036) % ep.number,
            "TvShowTitle": item.title,
            "Episode": None if item.is_movie else ep.number,
            "Plot": plot,
            "FirstAired": ep.air_date,
            "Duration": ep.runtime_min * 60 if ep.runtime_min else None,
            "MediaType": "movie" if item.is_movie else "episode",
        }
        info.update(history.resume_info(states.get(ep.number)))
        art = {"thumb": ep.thumbnail or item.poster, "icon": ep.thumbnail or item.poster,
               "poster": item.poster, "fanart": fanart}
        url = router.build_url("play", id=item.anilist_id, ep=ep.number)
        ui.add_video_item(request.handle, url, label, info, art, is_folder=False, playable=True,
                          context=history.episode_context(item.anilist_id, ep.number, states.get(ep.number)))

    if not episodes:
        ui.add_item(request.handle, ui.string(30035), router.build_url("noop"), is_folder=False)

    ui.set_content(request.handle, "movies" if item.is_movie else "episodes")
    ui.end_directory(request.handle, cache=False)  # watched marks change after playback


def dub_note(timestamp):
    """'Dub expected Fri 20 Feb' in the device's local time (DEC-056)."""
    day = datetime.datetime.fromtimestamp(timestamp)
    return ui.string(30051) % f"{day:%a} {day.day} {day:%b}"


def related(request):
    catalog = Catalog()
    item = catalog.show(request.params["id"])
    if not item.relations:
        # Reachable from the context menu of any show, also ones without relations.
        ui.notify(item.title, ui.string(30231))
        ui.end_directory(request.handle, succeeded=False)
        return
    result = catalog.franchise(item.anilist_id)
    if result.partial:
        ui.notify(item.title, ui.string(30288))
    for name in franchise.ROWS:
        row = ui.string(ROW_STRINGS[name])
        for node in result.rows.get(name) or []:
            details = entry_details(node)
            label = f"[{row}] {node.title}" + (f" ({details})" if details else "") + listing.dub_badge(catalog.dub_status(node))
            ui.add_item(request.handle, label, router.build_url("show", id=node.anilist_id),
                        art={"poster": node.poster, "thumb": node.poster, "icon": node.poster})
    ui.end_directory(request.handle)


def noop(request):
    pass
