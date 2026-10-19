"""Background service: housekeeping plus the player monitor (DEC-047)."""

import datetime
import time

from resources.lib import router
from resources.lib.kodi import log, paths, system, ui
from resources.lib.metadata import dubs
from resources.lib.myanimelist import sync
from resources.lib.playback.monitor import PlaybackMonitor, cleanup_after_start  # noqa: F401
from resources.lib.storage.cache import Cache

STATUS_CHECK_INTERVAL_S = 24 * 3600
PREMIUM_WARNING_S = 7 * 24 * 3600

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
    from resources.lib.debrid import service
    if service.active() == service.REAL_DEBRID:
        check_real_debrid(directory)


def check_real_debrid(directory, now=None):
    """Daily account refresh; warn once a day when premium ends within 7 days (DEC-018)."""
    from resources.lib.debrid import auth
    from resources.lib.debrid.realdebrid import RealDebrid

    now = now or time.time()
    store = auth.TokenStore(directory)
    if not store.connected:
        return
    account = store.data.get("account") or {}
    if now - account.get("checked_at", 0) > STATUS_CHECK_INTERVAL_S:
        try:
            account = RealDebrid(store).user()
        except Exception as exc:
            log.warning(f"Real-Debrid status check failed: {type(exc).__name__}: {exc}")
            return
    until = account.get("premium_until")
    if not until or until - now > PREMIUM_WARNING_S:
        return
    cache = Cache(directory)
    key = f"rd_warned:{datetime.date.fromtimestamp(now).isoformat()}"
    if cache.get(key):
        return
    days = max(int((until - now) // 86400), 0)
    ui.notify("Real-Debrid", ui.string(30137) % days, error=True)
    cache.set(key, True, 2 * 86400)


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
