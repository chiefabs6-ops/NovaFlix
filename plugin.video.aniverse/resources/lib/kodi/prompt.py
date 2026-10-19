"""Small non-blocking on-screen prompt shown over playing video: the skip
button (DEC-041) and Up next (DEC-030, with a second button: End episode).

It takes the remote's focus while shown, so it closes itself after a few
seconds; OK runs the action, any other key closes it (left/right move between
two buttons). Mouse movement is ignored so the pointer can reach the button.
Only the first press runs an action: the prompt closes with it.
"""

import xbmcgui

from resources.lib.kodi import log, ui

_SELECT_ACTIONS = {7, 100}         # select, left mouse click
_MOUSE_ACTIONS = range(100, 110)   # clicks, wheel, drag, move (Kodi ACTION_MOUSE_*)
_IGNORED = {0, 999}                # ACTION_NONE, ACTION_NOOP
_BUTTON = 9000
_BUTTON2 = 9001
_MOVE_ACTIONS = {1, 2}             # left, right: between the two buttons


class _PromptWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_click = None
        self.on_click2 = None
        self.is_open = True

    def onAction(self, action):
        action_id = action.getId()
        if action_id in _SELECT_ACTIONS or action_id in _MOUSE_ACTIONS or action_id in _IGNORED:
            return
        if action_id in _MOVE_ACTIONS and self.on_click2:
            return
        self.dismiss()

    def onClick(self, control_id):
        callback = {_BUTTON: self.on_click, _BUTTON2: self.on_click2}.get(control_id)
        if callback:
            self.on_click = self.on_click2 = None
            self.dismiss()
            try:
                callback()
            except Exception:
                log.exception("prompt action failed")

    def dismiss(self):
        if self.is_open:
            self.is_open = False
            self.close()


class Prompt:
    """Prompt(text, button, on_click[, button2, on_click2]).show(); .close(); .is_open."""

    def __init__(self, text, button, on_click, button2=None, on_click2=None):
        self._window = _PromptWindow("aniverse-prompt.xml", ui.addon().getAddonInfo("path"), "Default", "1080i")
        self._window.on_click = on_click
        self._window.on_click2 = on_click2 if button2 else None
        self._window.setProperty("text", text or "")
        self._window.setProperty("button", button)
        self._window.setProperty("button2", button2 or "")

    def show(self):
        self._window.show()

    @property
    def is_open(self):
        return self._window.is_open

    def close(self):
        self._window.dismiss()
