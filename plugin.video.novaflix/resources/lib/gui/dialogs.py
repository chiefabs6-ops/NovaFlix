# plugin.video.novaflix/resources/lib/gui/dialogs.py
"""Styled popups (M12) with the same contracts as the Kodi dialogs they replace:
confirm -> bool, pick_source/menu -> index or -1, Progress -> cancelled/update/wait/close."""

import xbmc
import xbmcgui

from resources.lib.gui import cards, ids, items
from resources.lib.kodi import ui


def _path():
    return ui.addon().getAddonInfo("path")


class _Modal(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None

    def onAction(self, action):
        if action.getId() in ids.ACTION_BACK:
            self.close()


class _ConfirmWindow(_Modal):
    def onInit(self):
        self.setFocusId(ids.CONFIRM_YES)

    def onClick(self, control_id):
        if control_id in (ids.CONFIRM_YES, ids.CONFIRM_NO):
            self.result = control_id == ids.CONFIRM_YES
            self.close()


def confirm(heading, message):
    window = _ConfirmWindow("novaflix-confirm.xml", _path(), "Default", "1080i")
    window.setProperty("heading", heading)
    window.setProperty("message", message)
    window.setProperty("yes", ui.string(30252))
    window.setProperty("no", ui.string(30253))
    window.doModal()
    return bool(window.result)


class _ListWindow(_Modal):
    list_id = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entries = []

    def onInit(self):
        control = self.getControl(self.list_id)
        control.reset()
        control.addItems(self.entries)
        self.setFocusId(self.list_id)

    def onClick(self, control_id):
        if control_id == self.list_id:
            self.result = self.getControl(self.list_id).getSelectedPosition()
            self.close()


class _SourcesWindow(_ListWindow):
    list_id = ids.SOURCES_LIST


class _MenuWindow(_ListWindow):
    list_id = ids.MENU_LIST


def pick_source(heading, rows):
    window = _SourcesWindow("novaflix-sources.xml", _path(), "Default", "1080i")
    window.setProperty("heading", heading)
    window.entries = items.to_listitems([cards.source_row(a, b, ui.string) for a, b in rows])
    window.doModal()
    return -1 if window.result is None else window.result


def menu(heading, options):
    window = _MenuWindow("novaflix-menu.xml", _path(), "Default", "1080i")
    window.setProperty("heading", heading)
    window.entries = [xbmcgui.ListItem(label=o, offscreen=True) for o in options]
    window.doModal()
    return -1 if window.result is None else window.result


def resume_choice(position_s):
    choice = menu("", [ui.string(30250) % cards.clock(position_s), ui.string(30251)])
    return {0: True, 1: False}.get(choice)


class _ProgressWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cancelled = False

    def onInit(self):
        self.setFocusId(ids.PROGRESS_CANCEL)

    def onClick(self, control_id):
        if control_id == ids.PROGRESS_CANCEL:
            self.cancelled = True

    def onAction(self, action):
        if action.getId() in ids.ACTION_BACK:
            self.cancelled = True


class Progress:
    """Same interface as ui._KodiProgress."""

    def __init__(self, heading, message):
        self._window = _ProgressWindow("novaflix-progress.xml", _path(), "Default", "1080i")
        self._window.setProperty("heading", heading)
        self._window.setProperty("message", message)
        self._window.setProperty("cancel", ui.string(30260))
        self._window.show()
        self._monitor = xbmc.Monitor()

    def cancelled(self):
        return self._window.cancelled

    def update(self, percent, message):
        self._window.getControl(ids.PROGRESS_BAR).setPercent(max(0, min(int(percent), 100)))
        self._window.setProperty("message", message)

    def wait(self, seconds):
        for _ in range(int(seconds * 4)):
            if self._window.cancelled or self._monitor.waitForAbort(0.25):
                return True
        return self._window.cancelled

    def close(self):
        self._window.close()
