"""The source list (DEC-004, DEC-021..025, DEC-053) used by the watch route, and "My TorBox".

The owner always picks. Unknown details are left out, never guessed.
"""

import re

from resources.lib import router
from resources.lib.debrid import service
from resources.lib.kodi import log, paths, ui
from resources.lib.sources import discovery, precheck, quality, ranking
from resources.lib.views import play
from resources.lib.storage.cache import Cache

CANDIDATE_TTL = 3600
MIN_RESOLUTIONS = [None, "480p", "720p", "1080p", "2160p"]
ORIGIN_LABELS = {"rdcloud": "My account", "torrentio": "Torrentio"}


def _size(n):
    if not n:
        return None
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


STATUS_STRINGS = {precheck.READY: 30193, precheck.DOWNLOAD: 30194, precheck.BLOCKED: 30192}
TIER_STRINGS = {quality.UHD: 30461, quality.FHD: 30462, quality.HD: 30463, quality.SD: 30464, quality.OTHER: 30465}
SORT_STRINGS = {ranking.BEST: 30467, ranking.RESOLUTION: 30468, ranking.SOURCE: 30469, ranking.HDR: 30470,
                ranking.SIZE: 30471}
ALL_TIERS = "all"


def details_line(c, check=None, extra=None):
    """One line of source details; `extra` goes just before the status, which stays last."""
    parts = []
    if c.pinned:
        parts.append(ui.string(30140))
    if c.match == "best_guess":
        parts.append(ui.string(30141))
    q = c.quality or quality.Quality()
    if q.is_cam:
        parts.append(ui.string(30472))
    if q.hardsub:
        parts.append(ui.string(30473) % q.hardsub)
    parts.append(q.resolution or c.resolution)
    parts += quality.summary(q)
    parts += [_size(c.size_bytes), q.video_codec or c.codec]
    parts.append({"dub": ui.string(30142), "dual": ui.string(30143)}.get(c.audio))
    origin = ORIGIN_LABELS.get(c.origin, c.origin)
    parts.append(f"{origin} ({c.site})" if c.site else origin)
    if c.seeders is not None:
        parts.append(f"{c.seeders} seeders")
    parts.append(extra)
    if c.origin == "rdcloud":
        parts.append(ui.string(30144) % service.label())
    else:
        parts.append(ui.string(STATUS_STRINGS.get(check, 30145)))
    return " · ".join(p for p in parts if p)


_STATUS_ORDER = {precheck.READY: 0, precheck.DOWNLOAD: 1}


def _arrange(shown, cache, ready_first=True):
    """(playable, unchecked, blocked) — playable keeps ranking order, ready before download
    unless the owner picked another order."""
    playable, unchecked, blocked = [], [], []
    for c in shown:
        status = precheck.cached_status(cache, c)
        if status in precheck.PLAYABLE:
            playable.append((c, status))
        elif status == precheck.BLOCKED:
            blocked.append((c, status))
        else:
            unchecked.append((c, status))
    if ready_first:
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
        hide_cam=a.getSettingBool("hide_cam"),
        hide_hardsubs=a.getSettingBool("hide_hardsubs"),
    )
    found = discovery.Settings(
        torrentio_enabled=a.getSettingBool("torrentio_enabled"),
        torrentio_url=ui.setting("torrentio_url") or discovery.torrentio.DEFAULT_BASE,
    )
    return filters, found


def _rd_client():
    """The TorBox client, or None when no key is set."""
    return service.client()


def _setup_service(request):
    """Ask the owner to enter the TorBox API key. Returns None (settings open instead)."""
    if ui.confirm("TorBox", ui.string(30203)):
        ui.open_settings()
    return None


def _report(outcomes):
    names = {"torrentio": "Torrentio", "rdcloud": f"My {service.label()}"}
    failed = [names[k] for k, v in outcomes.items() if v == "failed"]
    if failed:
        ui.notify("NovaFlix", ui.string(30147) % ", ".join(failed), error=True)


def pick_source(request, rd, wanted, candidates, filters, dub_only, last_group, last_resolution, heading_base, play_fn,
                note=None, row_note=None):
    """The source list (DEC-004, DEC-021..025, DEC-053) until the owner plays one or leaves.
    play_fn(rd, picked) -> play.PLAYED | play.BACK | play.STOP. `note` is added to the heading
    (e.g. how many other-language releases were hidden). True when something plays."""
    needed, show_blocked = 2, False  # DEC-053: check until 2 playable
    tier, sort = ALL_TIERS, ranking.BEST  # quality tab and order the owner picked
    cache = Cache(paths.profile_dir())

    while True:
        result = ranking.build(candidates, filters, dub_only, last_group, last_resolution,
                               getattr(wanted, "titles", None), sort)
        if dub_only and not result.shown and result.hidden_non_dub:
            if ui.confirm(heading_base, ui.string(30149)):
                dub_only = False
                continue
            return False
        if not result.shown:
            if result.hidden_cam and result.hidden_cam == result.hidden_by_filters:
                message = ui.string(30475) % result.hidden_cam
            elif result.hidden_by_filters:
                message = ui.string(30151) % result.hidden_by_filters
            else:
                message = ui.string(30150)
            ui.ok(heading_base, message)
            return False
        heading = heading_base + (f" · {note}" if note else "")
        if result.hidden_cam:
            heading += " · " + ui.string(30474) % result.hidden_cam
        if result.hidden_by_filters > result.hidden_cam:
            heading += " · " + ui.string(30152) % (result.hidden_by_filters - result.hidden_cam)
        if rd is not None:
            _precheck(rd, result.shown, wanted, cache, needed, heading_base)  # DEC-053
            playable, unchecked, blocked = _arrange(result.shown, cache, ready_first=sort == ranking.BEST)
            listed = playable + (blocked if show_blocked else [])
        else:
            listed = [(c, None) for c in result.shown]
            unchecked, blocked = [], []
        counts = ranking.tier_counts(c for c, _ in listed)
        if tier not in counts:
            tier = ALL_TIERS  # nothing of that quality left (e.g. blocked ones hidden again)
        if tier != ALL_TIERS:
            heading += " · " + ui.string(TIER_STRINGS[tier])
            listed = [(c, status) for c, status in listed if c.quality.tier == tier]
        rows = [(c.file_name or c.release_name, details_line(c, status, row_note)) for c, status in listed]
        # Quality tabs: one row on top, only when the sources are of more than one quality.
        top = [("tiers", _tiers_label(tier, counts))] if len(counts) > 1 else []
        actions = []
        if unchecked:
            actions.append(("more", ui.string(30197) % len(unchecked)))
        if blocked and not show_blocked:
            actions.append(("blocked", ui.string(30198) % len(blocked)))
        if dub_only and result.hidden_non_dub:
            actions.append(("all", ui.string(30153) % result.hidden_non_dub))
        if len(listed) > 1:
            actions.append(("sort", ui.string(30466) % ui.string(SORT_STRINGS[sort])))
        if not listed and not actions:
            ui.ok(heading_base, ui.string(30199))
            return False
        if not listed:
            heading = f"{heading_base} · {ui.string(30199)}"
        choice = ui.select_details(heading, [(label, "") for _, label in top] + rows
                                   + [(label, "") for _, label in actions], focus=len(top) if rows else 0)
        if choice < 0:
            if tier != ALL_TIERS:
                tier = ALL_TIERS  # back from a quality tab: all qualities again
                continue
            return False
        if choice < len(top):
            tier = _pick_tier(heading_base, tier, counts)
            continue
        choice -= len(top)
        if choice >= len(listed):
            action = actions[choice - len(listed)][0]
            if action == "sort":
                sort = _pick_sort(heading_base, sort)
            elif action == "more":
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
        outcome = play_fn(rd, picked)
        if outcome == play.PLAYED:
            return True
        if outcome == play.STOP:
            return False
        # BACK: same list again; the owner picks another source (never automatic).


def _tiers_label(tier, counts):
    """"Quality: All (23) — 4K / UHD 5 · 1080p 12 · Other / unknown 6": the open tab, then every tab's count."""
    current = ui.string(30460) if tier == ALL_TIERS else ui.string(TIER_STRINGS[tier])
    total = counts.get(tier) if tier != ALL_TIERS else sum(counts.values())
    others = " · ".join(f"{ui.string(TIER_STRINGS[t])} {n}" for t, n in counts.items())
    return ui.string(30476) % (current, total, others)


def _pick_tier(heading, tier, counts):
    """The quality tab the owner picks; the current one when they back out."""
    keys = [ALL_TIERS] + list(counts)
    options = [f"{ui.string(30460)} ({sum(counts.values())})"]
    options += [f"{ui.string(TIER_STRINGS[t])} ({n})" for t, n in counts.items()]
    choice = ui.menu(heading, options)
    return keys[choice] if 0 <= choice < len(keys) else tier


def _pick_sort(heading, sort):
    choice = ui.menu(heading, [ui.string(SORT_STRINGS[s]) for s in ranking.SORTS])
    return ranking.SORTS[choice] if 0 <= choice < len(ranking.SORTS) else sort


def _connected_client(request):
    rd = _rd_client()
    if rd is None:
        rd = _setup_service(request)
    return rd


# -- My TorBox ---------------------------------------------------------------------

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
