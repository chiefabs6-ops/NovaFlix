"""Actions triggered from the settings screen."""

from resources.lib.kodi import log, paths, ui
from resources.lib.storage import cache


def clear_cache(request):
    if not ui.confirm(ui.string(30110), ui.string(30111)):
        return
    store = cache.Cache(paths.profile_dir())
    store.clear()
    store.close()
    log.info("cache cleared by user")
    ui.notify("NovaFlix", ui.string(30112))
