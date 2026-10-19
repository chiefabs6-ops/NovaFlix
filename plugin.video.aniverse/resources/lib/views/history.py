"""Continue Watching (DEC-029) and manual watched/unwatched marks (DEC-032)."""

from resources.lib import router
from resources.lib.kodi import paths, ui
from resources.lib.metadata.catalog import Catalog
from resources.lib.myanimelist import progress, sync
from resources.lib.storage.history import History


def clock(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def resume_info(state):
    """InfoTagVideo values for an episode's history state (position, duration, watched).
    Kodi offers "Resume from" itself when a resume point is set. Our history is
    the record (DEC-005): no row means unwatched, whatever Kodi remembers."""
    position, duration, watched = state or (0, 0, False)
    info = {"Playcount": 1 if watched else 0}
    if position and not watched:
        info["ResumePoint"] = (position, duration)
    return info


def episode_context(anilist_id, number, state):
    watched = bool(state and state[2])
    return [(ui.string(30222 if watched else 30221),
             router.build_url("history/mark", id=anilist_id, ep=number, watched=0 if watched else 1)),
            # DEC-036: search again, skipping the saved list, and choose another source.
            (ui.string(30230), router.build_url("play", id=anilist_id, ep=number, refresh=1), "PlayMedia")]


def show_context(anilist_id):
    return [(ui.string(30223), router.build_url("history/mark_show", id=anilist_id, watched=1)),
            (ui.string(30224), router.build_url("history/mark_show", id=anilist_id, watched=0)),
            (ui.string(30034), router.build_url("related", id=anilist_id), "Container.Update")]


def continue_watching(request):
    rows = progress.continue_rows()
    shown = 0
    for row in rows:
        art = {"poster": row["poster"], "thumb": row["poster"], "icon": row["poster"]}
        anilist_id, episode = row["anilist_id"], row["episode"]
        if not row["watched"]:
            # Started episode: play it directly; Kodi offers the resume point.
            detail = (ui.string(30225) % (episode, clock(row["position_s"])) if row["position_s"]
                      else ui.string(30036) % episode)
            info = {"Title": row["title"], "TvShowTitle": row["title"], "Episode": episode, "MediaType": "episode"}
            info.update(resume_info((row["position_s"], row["duration_s"], False)))
            ui.add_video_item(request.handle, router.build_url("play", id=anilist_id, ep=episode),
                              f"{row['title']} — {detail}", info, art, is_folder=False, playable=True,
                              context=show_context(anilist_id))
        else:
            following = episode + 1
            if row["episodes_total"] and following > row["episodes_total"]:
                continue  # finished the show
            # Next episode may not have aired yet: open the show page rather than play.
            ui.add_video_item(request.handle, router.build_url("show", id=anilist_id),
                              f"{row['title']} — {ui.string(30218) % following}",
                              {"Title": row["title"], "MediaType": "tvshow"}, art, is_folder=True,
                              context=show_context(anilist_id))
        shown += 1
    if not shown:
        ui.notify(ui.string(30001), ui.string(30226))
        ui.end_directory(request.handle, succeeded=False)
        return
    ui.set_content(request.handle, "episodes")
    ui.end_directory(request.handle, cache=False)


def mark(request):
    anilist_id, episode = request.params["id"], int(request.params["ep"])
    watched = request.params.get("watched") == "1"
    History(paths.profile_dir()).mark(anilist_id, episode, watched)
    sync.queue_show(paths.profile_dir(), anilist_id, "watched" if watched else "unwatched", episode)
    ui.refresh()


def mark_show(request):
    anilist_id = request.params["id"]
    watched = request.params.get("watched") == "1"
    history = History(paths.profile_dir())
    if watched:
        catalog = Catalog()
        show = catalog.show(anilist_id)
        numbers = [e.number for e in catalog.episodes(show)]
        history.mark_show(anilist_id, numbers, True)
        sync.queue_show(paths.profile_dir(), anilist_id, "show_watched", max(numbers, default=0), mal_id=show.mal_id)
    else:
        if not ui.confirm("AniVerse", ui.string(30227)):
            return
        history.mark_show(anilist_id, [], False)
        sync.queue_show(paths.profile_dir(), anilist_id, "show_unwatched")
    ui.refresh()
