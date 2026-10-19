"""Maps plugin:// URLs to view functions.

Routes are stored as "module:function" strings and imported on demand, so
opening one menu does not import every view (keeps Fire TV startup fast).
"""

import importlib
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit

from resources.lib import errors
from resources.lib.kodi import log, paths, ui
from resources.lib.net import http

PLUGIN_ID = "plugin.video.novaflix"
BASE_URL = f"plugin://{PLUGIN_ID}/"

ROUTES = {
    "": "resources.lib.views.home:root",
    "settings": "resources.lib.views.home:open_settings",
    "launch": "resources.lib.views.home:launch",
    "clear_cache": "resources.lib.views.maintenance:clear_cache",
    "airing": "resources.lib.views.browse:airing",
    "recent": "resources.lib.views.browse:recent",
    "trending": "resources.lib.views.browse:trending",
    "popular": "resources.lib.views.browse:popular",
    "upcoming": "resources.lib.views.browse:upcoming",
    "genres": "resources.lib.views.browse:genres",
    "genre": "resources.lib.views.browse:genre",
    "search": "resources.lib.views.browse:search_menu",
    "search/new": "resources.lib.views.browse:search_new",
    "search/results": "resources.lib.views.browse:search_results",
    "search/clear": "resources.lib.views.browse:search_clear",
    "show": "resources.lib.views.show:show",
    "related": "resources.lib.views.show:related",
    "play": "resources.lib.views.sources:choose",
    "noop": "resources.lib.views.show:noop",
    "mal": "resources.lib.views.mylists:mal_menu",
    "mal/list": "resources.lib.views.mylists:mal_list",
    "mal/account": "resources.lib.views.mal_account:menu",
    "favourites": "resources.lib.views.mylists:favourites",
    "favourites/add": "resources.lib.views.mylists:favourite_add",
    "favourites/remove": "resources.lib.views.mylists:favourite_remove",
    "rd/cloud": "resources.lib.views.sources:cloud",
    "rd/torrent": "resources.lib.views.sources:torrent",
    "rd/play": "resources.lib.views.sources:rd_play",
    "rd/add_magnet": "resources.lib.views.sources:add_magnet",
    "continue": "resources.lib.views.history:continue_watching",
    "history/mark": "resources.lib.views.history:mark",
    "history/mark_show": "resources.lib.views.history:mark_show",
}


# Kodi waits for setResolvedUrl on these; failures must answer False, not end a directory.
PLAYABLE = {"play", "rd/play"}


@dataclass
class Request:
    handle: int
    path: str
    params: dict = field(default_factory=dict)


def build_url(path, **params):
    url = BASE_URL + path.strip("/")
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    return url


def parse(argv):
    """Turn Kodi's sys.argv (url, handle, query) into a Request."""
    path = urlsplit(argv[0]).path.strip("/")
    query = argv[2][1:] if len(argv) > 2 and argv[2].startswith("?") else ""
    return Request(handle=int(argv[1]), path=path, params=dict(parse_qsl(query)))


def setup():
    """Per-call setup shared by plugin calls and the service. With
    reuselanguageinvoker the interpreter (and module state) outlives a call,
    so anything read from settings is read again here."""
    log.reset_debug_flag()
    http.configure(ca_file=paths.ca_file(), version=ui.addon().getAddonInfo("version"))


def dispatch(argv):
    started = time.monotonic()
    try:
        _dispatch(argv)
    finally:
        # Path only; query strings may hold search text and never reach the log.
        log.debug(f"route /{urlsplit(argv[0]).path.strip('/')} took {int((time.monotonic() - started) * 1000)} ms")


def _dispatch(argv):
    setup()
    request = parse(argv)
    target = ROUTES.get(request.path)
    if target is None:
        log.warning(f"unknown route: {request.path}")
        ui.end_directory(request.handle, succeeded=False)
        return
    module_name, func_name = target.split(":")
    view = getattr(importlib.import_module(module_name), func_name)
    try:
        view(request)
    except Exception as exc:
        _end_failed(request)
        report_error(exc, request.path or "home")


def report_error(exc, where):
    """DEC-035: show any error the same way, from a plugin view or an NovaFlix window.
    Call from inside an `except` block."""
    if isinstance(exc, errors.AuthError):
        # Expired/revoked login is never shown as "no results".
        log.warning(f"{where}: {exc}")
        if ui.confirm("TorBox", ui.string(30229)):  # API key rejected
            ui.open_settings()
    elif isinstance(exc, errors.AccountError):
        log.warning(f"{where}: {exc}")
        from resources.lib.debrid import service
        name = service.label()
        ui.ok(name, ui.string(30136) % (name, str(exc).replace(f"{name}: ", "")))
    elif isinstance(exc, errors.RateLimited):
        log.warning(f"{where}: rate limited")
        ui.notify("NovaFlix", ui.string(30023), error=True)
    elif isinstance(exc, (errors.NetworkError, errors.HttpError)):
        # Includes ServiceUnavailable. Expected outages: no traceback needed.
        log.warning(f"{where}: {exc}")
        ui.notify("NovaFlix", ui.string(30022), error=True)
    else:
        # Last-resort guard: log redacted traceback, tell the user, never hang Kodi.
        log.exception(f"{where} failed")
        ui.notify("NovaFlix", ui.string(30021), error=True)


def _end_failed(request):
    if request.path in PLAYABLE:
        ui.resolve_failed(request.handle)
    elif request.handle >= 0:
        ui.end_directory(request.handle, succeeded=False)
