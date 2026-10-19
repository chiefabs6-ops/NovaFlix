"""NovaFlix runs next to AniVerse on the same device: nothing may still use AniVerse's
add-on IDs, profile folder, window properties or update site."""

import os
import re
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGES = ["plugin.video.novaflix", "script.novaflix", "repository.novaflix"]
TOOLS = [os.path.join("tools", "build.py"), os.path.join("tools", "dev_kodi.py")]
BINARY = (".png", ".jpg", ".pyc")


def _text_files():
    for package in PACKAGES:
        for folder, dirs, files in os.walk(os.path.join(ROOT, package)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(BINARY):
                    yield os.path.join(folder, name)
    for path in TOOLS:
        yield os.path.join(ROOT, path)


def test_no_aniverse_left_in_packages():
    hits = []
    for path in _text_files():
        with open(path, encoding="utf-8", errors="ignore") as f:
            for number, line in enumerate(f, 1):
                if re.search(r"aniverse", line, re.I):
                    hits.append(f"{os.path.relpath(path, ROOT)}:{number}")
    for package in PACKAGES:
        for folder, dirs, files in os.walk(os.path.join(ROOT, package)):
            hits += [os.path.relpath(os.path.join(folder, n), ROOT) for n in files + dirs if "aniverse" in n.lower()]
    assert hits == []


def test_window_properties_are_novaflix():
    from resources.lib.myanimelist import sync
    from resources.lib.playback import monitor
    for name in (monitor.HANDOFF_PROPERTY, monitor.OPEN_SHOW_PROPERTY, monitor.GUI_PROPERTY, sync.KICK_PROPERTY):
        assert name.startswith("novaflix.")


def _manifest(addon_id):
    return ET.parse(os.path.join(ROOT, addon_id, "addon.xml")).getroot()


def test_addon_ids_and_versions():
    found = {_manifest(a).get("id"): _manifest(a).get("version") for a in PACKAGES}
    assert found == {"plugin.video.novaflix": "0.1.0", "script.novaflix": "0.1.0", "repository.novaflix": "1.0.0"}
    imports = {i.get("addon"): i.get("version") for i in _manifest("plugin.video.novaflix").iter("import")}
    assert imports["script.novaflix"] == "0.1.0"
    launcher = open(os.path.join(ROOT, "script.novaflix", "launcher.py"), encoding="utf-8").read()
    assert "RunPlugin(plugin://plugin.video.novaflix/launch)" in launcher
    settings = ET.parse(os.path.join(ROOT, "plugin.video.novaflix", "resources", "settings.xml")).getroot()
    assert settings.find("section").get("id") == "plugin.video.novaflix"


def test_profile_and_log_prefix_are_novaflix():
    from resources.lib import router
    from resources.lib.kodi import log, paths
    assert router.PLUGIN_ID == "plugin.video.novaflix"
    assert paths._PROFILE == "special://profile/addon_data/plugin.video.novaflix/"
    assert log._PREFIX == "[plugin.video.novaflix]"
