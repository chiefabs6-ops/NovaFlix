"""Source list for an episode (DEC-004, DEC-021..025) and "My Real-Debrid".

The owner always picks. Unknown details are left out, never guessed.
Playback of the chosen source arrives in M7.
"""

import re

from resources.lib import router
from resources.lib.debrid import service
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata.catalog import Catalog
from resources.lib.models import Candidate
from resources.lib.sources import discovery, precheck, ranking
from resources.lib.views import play
from resources.lib.storage import db
from resources.lib.storage.cache import Cache

CANDIDATE_TTL = 3600
MIN_RESOLUTIONS = [None, "480p", "720p", "1080p", "2160p"]
ORIGIN_LABELS = {"rdcloud": "My account", "torrentio": "Torrentio", "nyaa": "Nyaa"}


def _size(n):
    if not n:
        return None
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


STATUS_STRINGS = {precheck.READY: 30193, precheck.DOWNLOAD: 30194, precheck.BLOCKED: 30192}


def details_line(c, check=None):
    parts = []
    if c.pinned:
        parts.append(ui.string(30140))
    if c.match == "best_guess":
        parts.append(ui.string(30141))
    parts += [c.resolution, _size(c.size_bytes), c.codec]
    parts.append({"dub": ui.string(30142), "dual": ui.string(30143)}.get(c.audio))
    origin = ORIGIN_LABELS.get(c.origin, c.origin)
    parts.append(f"{origin} ({c.site})" if c.site and c.origin != "nyaa" else origin)
    if c.seeders is not None:
        parts.append(f"{c.seeders} seeders")
    if c.origin == "rdcloud":
        parts.append(ui.string(30144) % service.label())
    else:
        parts.append(ui.string(STATUS_STRINGS.get(check, 30145)))
    return " · ".join(p for p in parts if p)


_STATUS_ORDER = {precheck.READY: 0, precheck.DOWNLOAD: 1}


def _arrange(shown, cache):
    """(playable, unchecked, blocked) — playable keeps ranking order, ready before download."""
    playable, unchecked, blocked = [], [], []
    for c in shown:
        status = precheck.cached_status(cache, c)
        if status in precheck.PLAYABLE:
            playable.append((c, status))
        elif status == precheck.BLOCKED:
            blocked.append((c, status))
        else:
            unchecked.append((c, status))
    playable.sort(key=lambda pair: _STATUS_ORDER[pair[1]])
    return playable, unchecked, blocked


def _precheck(rd, shown, wanted, cache, needed, heading):
    progress = ui.Progress(heading, ui.string(30195) % service.label())
    try:
        precheck.run(rd, shown, wanted, cache, needed=needed, cancelled=progress.cancelled,
                     on_progress=lambda done, ok: progress.update(min(done * 10, 100), ui.string(30196) % (done, ok)))
    finally:
        progress.close()


def _settings():
    a = ui.addon()
    min_index = a.getSettingInt("min_resolution")
    excluded = [codec for codec, key in (("HEVC", "exclude_hevc"), ("AV1", "exclude_av1")) if a.getSettingBool(key)]
    filters = ranking.Filters(
        min_resolution=MIN_RESOLUTIONS[min_index] if 0 <= min_index < len(MIN_RESOLUTIONS) else None,
        max_size_gb=float(a.getSettingInt("max_size_gb")),
        excluded_codecs=excluded,
    )
    found = discovery.Settings(
        torrentio_enabled=a.getSettingBool("torrentio_enabled"),
        torrentio_url=ui.setting("torrentio_url") or discovery.torrentio.DEFAULT_BASE,
        nyaa_enabled=a.getSettingBool("nyaa_enabled"),
    )
    return filters, found, a.getSettingBool("dub_only")


def _last_choice(anilist_id):
    conn = db.open_user_db(paths.profile_dir())
    try:
        row = conn.execute("SELECT last_release_group, last_resolution FROM show_prefs WHERE anilist_id = ?",
                           (int(anilist_id),)).fetchone()
    finally:
        conn.close()
    return row or (None, None)


def _rd_client():
    """Client of the active playback service (TorBox or Real-Debrid), or None."""
    return service.client()


def _setup_service(request):
    """Ask the owner to enter the TorBox API key. Returns None (settings open instead)."""
    if ui.confirm("TorBox", ui.string(30203)):
        ui.open_settings()
    return None


def _wanted(show, catalog, number):
    episode = next((e for e in catalog.episodes(show) if e.number == number), None)
    tvdb = (episode.tvdb_season, episode.tvdb_episode) if episode and episode.tvdb_season and episode.tvdb_episode else None
    return discovery.Wanted(show=show, number=number, absolute=episode.absolute_number if episode else None,
                            tvdb=tvdb, kitsu_id=catalog.mappings(show).get("kitsu_id"))


def _cache_key(show, number):
    return f"sources:v2:{show.anilist_id}:{number}"  # v2: other-language dubs and seasons fixed


def _discover(wanted, found_settings, cache, cancelled):
    outcomes, candidates = discovery.discover(wanted, found_settings, _rd_client(), cancelled=cancelled)
    if wanted.kitsu_id is None and found_settings.torrentio_enabled:
        outcomes["torrentio"] = "no_id"
    # Don't cache an all-failed result: next open should try again.
    if any(v in ("ok", "empty") for v in outcomes.values()):
        cache.set(_cache_key(wanted.show, wanted.number),
                  {"candidates": [c.to_dict() for c in candidates], "outcomes": outcomes}, CANDIDATE_TTL)
    return outcomes, candidates


def _find(show, catalog, number, refresh):
    wanted = _wanted(show, catalog, number)
    filters, found_settings, dub_only = _settings()
    cache = Cache(paths.profile_dir())
    cached = None if refresh else cache.get(_cache_key(show, number))
    if cached is not None:
        return wanted, [Candidate.from_dict(c) for c in cached["candidates"]], cached["outcomes"], filters, dub_only
    progress = ui.Progress(show.title, ui.string(30146))
    try:
        outcomes, candidates = _discover(wanted, found_settings, cache, progress.cancelled)
    finally:
        progress.close()
    return wanted, candidates, outcomes, filters, dub_only


def presearch(show, number, cancelled=lambda: False):
    """Up next (DEC-030): fill the source cache for an episode without any UI, so
    its list opens at once. Runs in the service; failures are only logged."""
    try:
        cache = Cache(paths.profile_dir())
        if cache.get(_cache_key(show, number)) is not None:
            return
        _, found_settings, _ = _settings()
        _, candidates = _discover(_wanted(show, Catalog(), number), found_settings, cache, cancelled)
        log.info(f"pre-searched episode {number}: {len(candidates)} sources")
    except Exception as exc:
        log.warning(f"pre-search failed: {type(exc).__name__}: {exc}")


def _report(outcomes):
    names = {"torrentio": "Torrentio", "nyaa": "Nyaa", "rdcloud": f"My {service.label()}"}
    failed = [names[k] for k, v in outcomes.items() if v == "failed"]
    if failed:
        ui.notify("NovaFlix", ui.string(30147) % ", ".join(failed), error=True)
    if outcomes.get("torrentio") == "no_id":
        ui.notify("NovaFlix", ui.string(30148))


def choose(request):
    """Episode selected: discover, let the owner pick (DEC-004), then play."""
    if not _choose(request):
        ui.resolve_failed(request.handle)


def _choose(request):
    catalog = Catalog()
    show = catalog.show(request.params["id"])
    number = int(request.params.get("ep", 1))
    wanted, candidates, outcomes, filters, dub_only = _find(show, catalog, number, request.params.get("refresh") == "1")
    _report(outcomes)
    last_group, last_resolution = _last_choice(show.anilist_id)
    heading_base = show.title if show.is_movie else f"{show.title} — {ui.string(30036) % number}"
    rd = _rd_client()
    needed, show_blocked = 2, False  # DEC-053: check until 2 playable
    cache = Cache(paths.profile_dir())

    while True:
        result = ranking.build(candidates, filters, dub_only, last_group, last_resolution)
        if dub_only and not result.shown and result.hidden_non_dub:
            if ui.confirm(heading_base, ui.string(30149)):
                dub_only = False
                continue
            return False
        if not result.shown:
            ui.ok(heading_base, ui.string(30150) if not result.hidden_by_filters
                  else ui.string(30151) % result.hidden_by_filters)
            return False
        heading = heading_base
        if result.hidden_by_filters:
            heading += " · " + ui.string(30152) % result.hidden_by_filters
        if rd is not None:
            _precheck(rd, result.shown, wanted, cache, needed, heading_base)  # DEC-053
            playable, unchecked, blocked = _arrange(result.shown, cache)
            listed = playable + (blocked if show_blocked else [])
        else:
            listed = [(c, None) for c in result.shown]
            unchecked, blocked = [], []
        rows = [(c.file_name or c.release_name, details_line(c, status)) for c, status in listed]
        actions = []
        if unchecked:
            actions.append(("more", ui.string(30197) % len(unchecked)))
        if blocked and not show_blocked:
            actions.append(("blocked", ui.string(30198) % len(blocked)))
        if dub_only and result.hidden_non_dub:
            actions.append(("all", ui.string(30153) % result.hidden_non_dub))
        if not listed and not actions:
            ui.ok(heading_base, ui.string(30199))
            return False
        if not listed:
            heading = f"{heading_base} · {ui.string(30199)}"
        choice = ui.select_details(heading, rows + [(label, "") for _, label in actions])
        if choice < 0:
            return False
        if choice >= len(listed):
            action = actions[choice - len(listed)][0]
            if action == "more":
                needed += 2
            elif action == "blocked":
                show_blocked = True
            else:
                dub_only = False
            continue
        picked = listed[choice][0]
        log.info(f"source chosen: {picked.origin} {picked.resolution or ''} match={picked.match}")
        rd = _connected_client(request)
        if rd is None:
            return False
        outcome = play.play_candidate(request, rd, show, wanted, picked, heading_base)
        if outcome == play.PLAYED:
            return True
        if outcome == play.STOP:
            return False
        # BACK: same list again; the owner picks another source (never automatic).


def _connected_client(request):
    rd = _rd_client()
    if rd is None:
        rd = _setup_service(request)
    return rd


# -- My Real-Debrid ---------------------------------------------------------------

def _require_rd(request):
    client = _rd_client()
    if client is None:
        ui.end_directory(request.handle, succeeded=False)
        _setup_service(request)
    return client


def cloud(request):
    client = _require_rd(request)
    if client is None:
        return
    ui.add_item(request.handle, ui.string(30154), router.build_url("rd/add_magnet"), is_folder=False)
    for t in client.torrents():
        if t.get("status") != "downloaded":
            continue
        label = t.get("filename") or "?"
        size = _size(t.get("bytes"))
        ui.add_item(request.handle, f"{label}  [COLOR FF9E9E9E]{size}[/COLOR]" if size else label,
                    router.build_url("rd/torrent", id=t["id"]))
    ui.end_directory(request.handle, cache=False)


def torrent(request):
    client = _require_rd(request)
    if client is None:
        return
    info = client.torrent_info(request.params["id"])
    for f in info.get("files") or []:
        path = (f.get("path") or "").lstrip("/")
        if not f.get("selected") or not re.search(r"\.(mkv|mp4|avi|m4v|webm|ts|mov)$", path, re.I):
            continue
        ui.add_video_item(request.handle, router.build_url("rd/play", torrent=info.get("id"), file=f.get("id")),
                          path, {"Title": path, "MediaType": "video"}, {}, is_folder=False, playable=True)
    ui.end_directory(request.handle, cache=False)


def rd_play(request):
    rd = _connected_client(request)
    if rd is None:
        ui.resolve_failed(request.handle)
        return
    play.play_account_file(request, rd, request.params["torrent"], request.params["file"])


def add_magnet(request):
    client = _rd_client()
    if client is None:
        _setup_service(request)
        return
    magnet = ui.keyboard(ui.string(30155))
    if not magnet:
        return
    if not re.match(r"magnet:\?xt=urn:btih:[0-9a-zA-Z]{32,40}", magnet):
        ui.ok(service.label(), ui.string(30156))
        return
    torrent_id = client.add_magnet(magnet)
    if torrent_id:
        client.select_files(torrent_id, "all")
    log.info(f"magnet added to {service.label()} by owner")
    ui.notify(service.label(), ui.string(30157) % service.label())
    ui.refresh()
