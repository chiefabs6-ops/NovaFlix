"""NovaFlix launcher (script.novaflix): the Video add-ons tile starts the NovaFlix window
without Kodi's folder screen first."""

import os
import runpy
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcplugin

from resources.lib import router

ROOT = os.path.join(os.path.dirname(__file__), "..")
LAUNCHER_DIR = os.path.join(ROOT, "script.novaflix")
PLUGIN_DIR = os.path.join(ROOT, "plugin.video.novaflix")
BASE = "plugin://plugin.video.novaflix/"


def _xml(folder):
    return ET.parse(os.path.join(folder, "addon.xml")).getroot()


def test_launcher_is_a_video_script_named_novaflix():
    root = _xml(LAUNCHER_DIR)
    assert root.get("id") == "script.novaflix" and root.get("name") == "NovaFlix"
    script = next(e for e in root.iter("extension") if e.get("point") == "xbmc.python.script")
    assert script.get("library") == "launcher.py" and script.findtext("provides") == "video"
    assert os.path.isfile(os.path.join(LAUNCHER_DIR, "launcher.py"))
    imports = {i.get("addon"): i.get("version") for i in root.iter("import")}
    assert imports == {"xbmc.python": "3.0.1"}  # no import of the plugin: the plugin imports the launcher
    for asset in root.iter("assets"):
        for child in asset:
            assert os.path.isfile(os.path.join(LAUNCHER_DIR, child.text)), child.text


def test_plugin_pulls_in_launcher_and_has_no_own_video_tile():
    root = _xml(PLUGIN_DIR)
    imports = {i.get("addon"): i.get("version") for i in root.iter("import")}
    assert imports.get("script.novaflix") == _xml(LAUNCHER_DIR).get("version")
    plugin = next(e for e in root.iter("extension") if e.get("point") == "xbmc.python.pluginsource")
    assert plugin.find("provides") is None


def test_launcher_runs_plugin_launch_route_in_background():
    runpy.run_path(os.path.join(LAUNCHER_DIR, "launcher.py"), run_name="__main__")
    assert xbmc.builtins_executed[-1] == "RunPlugin(plugin://plugin.video.novaflix/launch)"


def test_launch_route_opens_app_window_when_look_is_on(monkeypatch):
    from resources.lib.gui import app
    opened = []
    monkeypatch.setattr(app, "run", lambda show_id=None: opened.append(show_id))
    xbmcaddon.settings["novaflix_look"] = True
    router.dispatch([BASE + "launch", "-1", ""])
    assert opened == [None] and xbmcplugin.end_calls == []
    router.dispatch([BASE + "launch", "-1", "?show=154587"])  # End episode with no NovaFlix window open
    assert opened == [None, 154587]


def test_launch_route_opens_classic_lists_when_look_is_off(monkeypatch):
    from resources.lib.gui import app
    monkeypatch.setattr(app, "run", lambda show_id=None: (_ for _ in ()).throw(AssertionError("app opened")))
    xbmcaddon.settings["novaflix_look"] = False
    router.dispatch([BASE + "launch", "-1", ""])
    assert xbmc.builtins_executed[-1] == "ActivateWindow(Videos,plugin://plugin.video.novaflix/,return)"
