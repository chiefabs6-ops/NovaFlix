"""MyAnimeList account (M13): log in by QR code + relay page, check the login, log out."""

import time

from resources.lib import errors
from resources.lib.kodi import log, paths, ui
from resources.lib.myanimelist import auth, relay, sync

HEADING = "MyAnimeList"
LOGIN_SECONDS = 300

_clock = time.monotonic


def _presenter():
    from resources.lib.kodi.login_dialog import KodiLoginPresenter
    return KodiLoginPresenter()


def _server(host):
    return relay.CallbackServer(host)


def menu(request):
    store = auth.MalStore(paths.profile_dir())
    if not store.logged_in:
        if ui.confirm(HEADING, ui.string(30266)):
            login(request)
        return
    choice = ui.select(ui.string(30267) % store.data.get("username", "?"), [ui.string(30268), ui.string(30269)])
    if choice == 0:
        check(request)
    elif choice == 1:
        logout(request)


def login(request):
    client_id = ui.setting("mal_client_id")
    if not client_id:
        if ui.confirm(HEADING, ui.string(30075)):
            ui.open_settings()
        return
    host = relay.lan_address()
    if not host:
        ui.ok(HEADING, ui.string(30270))
        return
    verifier, nonce = auth.new_verifier(), auth.new_nonce()
    server = _server(host)
    try:
        state = auth.make_state(nonce, host, server.port)
        login_url = auth.authorize_url(client_id, verifier, state)
        server.expect(state, login_url)
        server.start()
        result = _wait_for_phone(server, login_url, f"http://{host}:{server.port}")
    finally:
        server.stop()
    if result is None:
        log.info("MyAnimeList login cancelled or timed out")
        return
    if result[0] == "denied":
        log.info("MyAnimeList login denied on the phone")
        ui.ok(HEADING, ui.string(30271))
        return
    try:
        name = auth.complete_login(auth.MalStore(paths.profile_dir()), client_id, result[1], verifier)
    except auth.MalLoginRefused as exc:
        log.warning(str(exc))
        ui.ok(HEADING, ui.string(30272))
        return
    except errors.NovaFlixError as exc:
        log.warning(f"MyAnimeList login failed: {type(exc).__name__}: {exc}")
        ui.ok(HEADING, ui.string(30273))
        return
    ui.notify(HEADING, ui.string(30267) % name)


def _wait_for_phone(server, login_url, short_url):
    """server.result once the phone answered; None after Cancel/Back or 5 minutes."""
    presenter = _presenter()
    presenter.show({"heading": ui.string(30274), "text": ui.string(30275), "qr": login_url, "url": short_url})
    deadline = _clock() + LOGIN_SECONDS
    try:
        while server.result is None:
            remaining = int(deadline - _clock())
            if remaining <= 0:
                return None
            presenter.update(remaining)
            if presenter.wait(1):
                return None
        return server.result
    finally:
        presenter.close()


def check(request):
    from resources.lib.myanimelist.api import MalApi
    try:
        name = MalApi(auth.MalStore(paths.profile_dir())).me()
    except auth.MalLoggedOut:
        ui.ok(HEADING, ui.string(30276))
        return
    except errors.NovaFlixError as exc:
        log.warning(f"MyAnimeList login check failed: {type(exc).__name__}: {exc}")
        ui.ok(HEADING, ui.string(30281))
        return
    ui.ok(HEADING, ui.string(30267) % name)


def logout(request):
    if not ui.confirm(HEADING, ui.string(30277)):
        return
    auth.MalStore(paths.profile_dir()).clear()
    sync.clear_queue(paths.profile_dir())  # nothing left to send them to
    log.info("MyAnimeList logged out")
    ui.ok(HEADING, ui.string(30278))
