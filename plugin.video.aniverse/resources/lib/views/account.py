"""Real-Debrid account screen (DEC-017, DEC-018): connect, status, disconnect."""

import datetime

from resources.lib import errors
from resources.lib.debrid import auth
from resources.lib.debrid.realdebrid import RealDebrid
from resources.lib.kodi import log, paths, ui

HEADING = "Real-Debrid"


def _presenter():
    from resources.lib.kodi.login_dialog import KodiLoginPresenter
    return KodiLoginPresenter()


def _date(timestamp):
    return datetime.date.fromtimestamp(timestamp).isoformat() if timestamp else None


def status_text(account):
    if not account:
        return ui.string(30124)
    name = account.get("username") or "?"
    if account.get("type") == "premium" and account.get("premium_until"):
        return ui.string(30125) % (name, _date(account["premium_until"]))
    return ui.string(30126) % (name, account.get("type") or "?")


def menu(request):
    store = auth.TokenStore(paths.profile_dir())
    if not store.connected:
        if ui.confirm(HEADING, ui.string(30127)):
            connect(request)
        return
    options = [ui.string(30128), ui.string(30129)]
    choice = ui.select(status_text(store.data.get("account")), options)
    if choice == 0:
        check_status(request)
    elif choice == 1:
        disconnect(request)


def connect(request):
    store = auth.TokenStore(paths.profile_dir())
    presenter = _presenter()
    if not auth.run_device_login(store, presenter, presenter.wait):
        return
    # SEC-13: only say "connected" once the account call actually works.
    try:
        account = RealDebrid(store).user()
    except errors.AniVerseError as exc:
        log.warning(f"Real-Debrid connected but status check failed: {exc}")
        ui.ok(HEADING, ui.string(30130))
        return
    log.info(f"Real-Debrid connected ({account.get('type')})")
    if account.get("type") != "premium":
        ui.ok(HEADING, ui.string(30131))
    else:
        ui.notify(HEADING, status_text(account))


def check_status(request):
    store = auth.TokenStore(paths.profile_dir())
    account = RealDebrid(store).user()
    ui.ok(HEADING, status_text(account))


def disconnect(request):
    if not ui.confirm(HEADING, ui.string(30132)):
        return
    store = auth.TokenStore(paths.profile_dir())
    revoked = True
    try:
        RealDebrid(store).disable_access_token()
    except errors.AniVerseError as exc:
        revoked = False
        log.warning(f"Real-Debrid revoke failed: {exc}")
    store.clear()
    log.info("Real-Debrid disconnected" + ("" if revoked else " locally only"))
    ui.ok(HEADING, ui.string(30133 if revoked else 30134))
