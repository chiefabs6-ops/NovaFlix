"""Home menu (DEC-033)."""

import xbmc

from resources.lib import router
from resources.lib.kodi import log, ui

# (string id, route). Settings is the only non-folder entry.
HOME_ENTRIES = [
    (30001, "continue"),     # Continue Watching
    (30002, "search"),       # Search
    (30003, "mal"),          # My MyAnimeList
    (30004, "favourites"),   # Favourites
    (30005, "airing"),       # Airing This Season
    (30006, "recent"),       # Recently Aired Episodes
    (30007, "trending"),     # Trending Now
    (30008, "popular"),      # Most Popular
    (30009, "upcoming"),     # Upcoming Next Season
    (30010, "genres"),       # Genres
    (30011, "rd/cloud"),     # My Real-Debrid
    (30012, "settings"),     # Settings
]


def root(request):
    if ui.styled():
        # M12: NovaFlix draws its own screens; Kodi's list for this call ends empty.
        ui.end_directory(request.handle, succeeded=False, cache=False)
        _open_app()
        return
    from resources.lib.debrid import service
    for string_id, route in HOME_ENTRIES:
        label = ui.string(string_id)
        if string_id == 30011:
            label = label % service.label()  # "My TorBox" / "My Real-Debrid"
        url = router.build_url(route)
        ui.add_item(request.handle, label, url, is_folder=(route != "settings"))
    ui.end_directory(request.handle, cache=False)  # a cached copy would keep old routes after an update


def launch(request):
    """Started by the script.novaflix tile through RunPlugin: no Kodi folder screen, no directory to end.
    title=<type:id>: End episode with no NovaFlix window open (playback/monitor.py) opens that title page."""
    if ui.styled():
        _open_app(request.params.get("title"))
    else:
        xbmc.executebuiltin(f"ActivateWindow(Videos,{router.build_url('')},return)")


def _open_app(title_key=None):
    from resources.lib.gui import app
    try:
        app.run(title_key)
    except Exception:
        log.exception("NovaFlix window failed")
        ui.notify("NovaFlix", ui.string(30021), error=True)


def open_settings(request):
    ui.open_settings()
