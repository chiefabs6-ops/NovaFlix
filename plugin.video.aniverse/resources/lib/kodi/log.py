"""Logging to kodi.log, prefixed with the add-on ID and always redacted.

Debug lines are written only when the add-on's "Debug logging" setting is on,
at LOGINFO so they show without Kodi's own debug mode (DEC-037).
"""

import traceback

import xbmc
import xbmcaddon

from resources.lib import redact

_PREFIX = "[plugin.video.aniverse]"
_debug_enabled = None


def _write(message, level):
    xbmc.log(f"{_PREFIX} {redact.text(message)}", level)


def _debug_on():
    global _debug_enabled
    if _debug_enabled is None:
        try:
            _debug_enabled = xbmcaddon.Addon().getSettingBool("debug_logging")
        except Exception:
            _debug_enabled = False
    return _debug_enabled


def reset_debug_flag():
    """Re-read the setting on next use (tests; long-running service)."""
    global _debug_enabled
    _debug_enabled = None


def debug(message):
    if _debug_on():
        _write(f"[debug] {message}", xbmc.LOGINFO)


def info(message):
    _write(message, xbmc.LOGINFO)


def warning(message):
    _write(message, xbmc.LOGWARNING)


def error(message):
    _write(message, xbmc.LOGERROR)


def exception(message):
    """Log message plus the current traceback, redacted."""
    _write(f"{message}\n{traceback.format_exc()}", xbmc.LOGERROR)
