"""TV QR screen: QR code + address (+ short code), used by the phone search (gui/actions.search_phone).

Scanning the QR on a phone opens the address. If the QR module is missing the
dialog still shows the address.
"""

import os

import xbmc
import xbmcgui

from resources.lib.kodi import log, paths, ui

_BACK_ACTIONS = {9, 10, 92}  # parent dir, previous menu, back
_CANCEL_BUTTON = 9000


class _LoginWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cancelled = False

    def onAction(self, action):
        if action.getId() in _BACK_ACTIONS:
            self.cancelled = True
            self.close()

    def onClick(self, control_id):
        if control_id == _CANCEL_BUTTON:
            self.cancelled = True
            self.close()


class KodiLoginPresenter:
    def __init__(self):
        self._window = None
        self._qr_path = os.path.join(paths.profile_dir(), "rd_login_qr.png")
        self._monitor = xbmc.Monitor()

    def _make_qr(self, url):
        try:
            import pyqrcode
            pyqrcode.create(url).png(self._qr_path, scale=12, quiet_zone=2)
            return self._qr_path
        except Exception as exc:
            log.warning(f"QR code unavailable: {type(exc).__name__}")
            return ""

    def show(self, info):
        """info: heading, text, qr (the address to encode) and url (shown under it)."""
        self._window = _LoginWindow("novaflix-login.xml", ui.addon().getAddonInfo("path"), "Default", "1080i")
        qr = self._make_qr(info.get("qr"))
        self._window.setProperty("qr", qr)
        self._window.setProperty("heading", info.get("heading") or "")
        self._window.setProperty("text", info.get("text") or "")
        self._window.setProperty("url", info.get("url") or "")
        self._window.setProperty("code", info.get("user_code", ""))
        self._window.show()

    def set(self, key, value):
        """Change one shown property (phone keyboard: typed text, status)."""
        if self._window:
            self._window.setProperty(key, value)

    def update(self, seconds_left):
        if self._window:
            minutes, seconds = divmod(max(seconds_left, 0), 60)
            self._window.setProperty("status", ui.string(30123) % (minutes, seconds))

    def wait(self, seconds):
        """Sleep in short steps; True if the owner cancelled or Kodi is closing."""
        for _ in range(int(seconds * 4)):
            if self._window is None or self._window.cancelled:
                return True
            if self._monitor.waitForAbort(0.25):
                return True
        return self._window is None or self._window.cancelled

    def close(self):
        if self._window:
            self._window.close()
            self._window = None
        if os.path.exists(self._qr_path):
            os.remove(self._qr_path)
