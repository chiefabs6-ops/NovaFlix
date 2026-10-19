"""What AniVerse sends to MyAnimeList for one change (M13 spec §5). Pure: no network, no storage.

entry: MalApi.entry() dict — title, num_episodes (0 = unknown), airing, list_status (None = not on
the list), watched, score. Returns (status, num_watched_episodes), or None when MAL already matches.
"""

KINDS = ("watched", "unwatched", "show_watched", "show_unwatched")


def plan(kind, episode, entry):
    current_status, current = entry.get("list_status"), int(entry.get("watched") or 0)
    total = int(entry.get("num_episodes") or 0)
    finished = entry.get("airing") == "finished_airing"
    episode = int(episode or 0)
    if kind == "watched":
        count = max(current, episode)
        if current_status == "completed" or (finished and total and count >= total):
            status = "completed"
        else:
            status = "watching"
    elif kind == "unwatched":
        if current_status is None or episode > current:
            return None
        status, count = "watching", episode - 1
    elif kind == "show_watched":
        status, count = ("completed", total) if total else ("watching", max(current, episode))
    elif kind == "show_unwatched":
        if current_status is None:
            return None
        status, count = "watching", 0
    else:
        raise ValueError(kind)
    if (status, count) == (current_status, current):
        return None
    return status, count
