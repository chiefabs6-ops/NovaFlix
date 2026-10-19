"""Plugin root and the Video add-ons tile: both open the NovaFlix window."""

from resources.lib.kodi import log, ui


def root(request):
    # NovaFlix draws its own screens; Kodi's list for this call ends empty.
    ui.end_directory(request.handle, succeeded=False, cache=False)
    _open_app()


def launch(request):
    """Started by the script.novaflix tile through RunPlugin: no Kodi folder screen, no directory to end.
    title=<type:id>: End episode with no NovaFlix window open (playback/monitor.py) opens that title page."""
    _open_app(request.params.get("title"))


def _open_app(title_key=None):
    from resources.lib.gui import app
    try:
        app.run(title_key)
    except Exception:
        log.exception("NovaFlix window failed")
        ui.notify("NovaFlix", ui.string(30021), error=True)


def open_settings(request):
    ui.open_settings()
