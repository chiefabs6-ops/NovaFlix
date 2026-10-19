"""Background service: housekeeping plus the player monitor (DEC-047)."""

import time

from resources.lib import router
from resources.lib.kodi import log, paths, system, ui
from resources.lib.playback.monitor import PlaybackMonitor, cleanup_after_start  # noqa: F401

HOUSEKEEPING_EVERY_S = 60
TICK_S = 1  # player monitor resolution (skip button, Up next, 30 s saves)


def housekeeping():
    """Cheap checks run every minute; network work only when something is due."""
    log.reset_debug_flag()  # pick up a changed "Debug logging" setting


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
            player.tick(now)
        except Exception:
            log.exception("player monitor failed")
        if monitor.waitForAbort(TICK_S):
            break
    log.info("service stopped")
