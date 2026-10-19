"""Minimal fake of Kodi's xbmcaddon module for tests.

Localized strings are read from the real strings.po so tests fail if a
string ID used in code is missing from the language file.
"""

import os
import re

ADDON_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "plugin.video.novaflix")
)
_PO_PATH = os.path.join(ADDON_DIR, "resources", "language", "resource.language.en_gb", "strings.po")

settings = {}
opened_settings = []


def _load_strings():
    with open(_PO_PATH, encoding="utf-8") as f:
        text = f.read()
    pairs = re.findall(r'msgctxt "#(\d+)"\s*\nmsgid "(.*)"', text)
    return {int(k): v.replace('\\"', '"') for k, v in pairs}  # Kodi unescapes \"


class Addon:
    def __init__(self, id=None):
        self._strings = _load_strings()

    def getAddonInfo(self, key):
        info = {
            "id": "plugin.video.novaflix",
            "name": "NovaFlix",
            "version": "0.0.0-test",
            "path": ADDON_DIR,
            "icon": os.path.join(ADDON_DIR, "icon.png"),
            "fanart": os.path.join(ADDON_DIR, "fanart.png"),
        }
        return info.get(key, "")

    def getLocalizedString(self, string_id):
        # Kodi returns an empty string for unknown IDs; tests want a loud failure.
        if string_id not in self._strings:
            raise KeyError(f"string id {string_id} missing from strings.po")
        return self._strings[string_id]

    def getSettingBool(self, key):
        return bool(settings.get(key, False))

    def getSettingInt(self, key):
        return int(settings.get(key, 0))

    def getSettingString(self, key):
        return str(settings.get(key, ""))

    def openSettings(self):
        opened_settings.append(True)


def reset():
    settings.clear()
    opened_settings.clear()
