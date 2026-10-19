"""Background service: housekeeping plus the player monitor (DEC-047)."""

import time

from resources.lib import router
from resources.lib.kodi import log, paths, system, ui
from resources.lib.metadata import dubs
from resources.lib.myanimelist import sync
from resources.lib.playback.monitor import PlaybackMonitor, cleanup_after_start  # noqa: F401

HOUSEKEEPING_EVERY_S = 60
TICK_S = 1  # player monitor resolution (skip button, Up next, 30 s saves)


def housekeeping():
    """Cheap checks run every minute; network work only when something is due."""
    log.reset_debug_flag()  # pick up a changed "Debug logging" setting
    directory = paths.profile_dir()
    sync.start_drain(directory)  # MyAnimeList changes left from before (offline, restart)
    sync.check_login(directory)
    if dubs.is_stale(directory):
        dubs.refresh(directory)


def run():
    router.setup()
    log.info("service started")
    player = PlaybackMonitor()
    monitor = system.monitor()
    next_housekeeping = 0
    while True:
        now = time.monotonic()
        if now >= next_housekeeping:
            next_housekeeping = now + HOUSEKEEPING_EVERY_S
            try:
                housekeeping()
            except Exception:
                log.exception("service housekeeping failed")
        try:
            if ui.get_window_property(sync.KICK_PROPERTY):
                ui.clear_window_property(sync.KICK_PROPERTY)
                sync.start_drain(paths.profile_dir())
        except Exception:
            log.exception("MyAnimeList sync failed")
        try:
            player.tick(now)
        except Exception:
            log.exception("player monitor failed")
        if monitor.waitForAbort(TICK_S):
            break
    log.info("service stopped")
