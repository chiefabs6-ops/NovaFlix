"""Add a show to, or remove it from, the owner's MyAnimeList (long-press menu of a card).
Sent at once, not through the sync queue: the owner is waiting for the answer. Saved MAL data
for the show and the owner's lists is dropped so every screen shows the change."""

from resources.lib import errors
from resources.lib.metadata import mal
from resources.lib.myanimelist import auth, sync
from resources.lib.myanimelist.api import MalApi
from resources.lib.storage.cache import Cache
from resources.lib.storage.history import History

ADD_ORDER = ("plan_to_watch", "watching", "completed", "on_hold", "dropped")
LIST_PAGES = 10  # same reach as the My Anime List counts (gui/lists.MAL_COUNT_PAGES)


def add(directory, mal_id, anilist_id, status, episodes_total=0):
    """PUT status + episode count: Completed counts every episode, otherwise the episodes
    watched in NovaFlix (so adding a show in progress keeps its progress)."""
    if status == "completed" and episodes_total:
        watched = episodes_total
    else:
        watched = max((n for n, (_, _, done) in History(directory).states(anilist_id).items() if done), default=0)
    MalApi(auth.MalStore(directory)).update(mal_id, status, watched)
    forget(directory, mal_id)
    return watched


def remove(directory, mal_id):
    try:
        MalApi(auth.MalStore(directory)).remove(mal_id)
    except errors.HttpError as exc:
        if exc.status != 404:  # 404: not on the list (any more)
            raise
    # A queued watch change would put the show straight back on the list.
    sync._run(directory, "DELETE FROM mal_pending WHERE mal_id = ?", (int(mal_id),))
    forget(directory, mal_id)


def forget(directory, mal_id):
    cache = Cache(directory)
    try:
        cache.delete(sync.entry_key(mal_id))
        cache.delete(sync.WATCHING_KEY)
        for status in mal.STATUSES:
            for page in range(1, LIST_PAGES + 1):
                cache.delete(f"mal:@me:{status}:{page}")
    finally:
        cache.close()
