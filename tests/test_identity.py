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
    from resources.lib.playback import monitor
    for name in (monitor.HANDOFF_PROPERTY, monitor.OPEN_SHOW_PROPERTY, monitor.GUI_PROPERTY):
        assert name.startswith("novaflix.")


def _manifest(addon_id):
    return ET.parse(os.path.join(ROOT, addon_id, "addon.xml")).getroot()


def test_addon_ids_and_versions():
    found = {_manifest(a).get("id"): _manifest(a).get("version") for a in PACKAGES}
    assert found == {"plugin.video.novaflix": "0.2.0", "script.novaflix": "0.1.0", "repository.novaflix": "1.0.0"}
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


def test_no_real_debrid_in_visible_settings_text():
    # Settings show labels and help texts by string id; none may still name Real-Debrid.
    settings = open(os.path.join(ROOT, "plugin.video.novaflix", "resources", "settings.xml"), encoding="utf-8").read()
    used = set(re.findall(r'(?:label|help)="(\d+)"', settings))
    po = open(os.path.join(ROOT, "plugin.video.novaflix", "resources", "language", "resource.language.en_gb",
                           "strings.po"), encoding="utf-8").read()
    texts = dict(re.findall(r'msgctxt "#(\d+)"\nmsgid "(.*)"', po))
    assert [i for i in used if "Real-Debrid" in texts.get(i, "")] == []


ANIME_WORDS = re.compile(r"anilist|anizip|myanimelist|aniskip|nyaa|kitsu|real-debrid|realdebrid|animeschedule", re.I)


def test_no_anime_or_mal_code_left():
    hits = []
    for path in _text_files():
        if not path.startswith(os.path.join(ROOT, "plugin.video.novaflix")) or path.endswith("migrations.py"):
            continue  # migrations.py keeps the released schema steps of 0.1.0 unchanged (never edited)
        with open(path, encoding="utf-8", errors="ignore") as f:
            hits += [f"{os.path.relpath(path, ROOT)}:{n}" for n, line in enumerate(f, 1) if ANIME_WORDS.search(line)]
    assert hits == []


def test_every_string_id_in_code_exists():
    # Every 30xxx number in the add-on's code and settings is a string ID of strings.po.
    po = open(os.path.join(ROOT, "plugin.video.novaflix", "resources", "language", "resource.language.en_gb",
                           "strings.po"), encoding="utf-8").read()
    known = set(re.findall(r'msgctxt "#(\d+)"', po))
    used = {}
    for path in _text_files():
        if path.startswith(os.path.join(ROOT, "plugin.video.novaflix")) and path.endswith((".py", ".xml")):
            for number in re.findall(r"(30[0-9]{3})", open(path, encoding="utf-8", errors="ignore").read()):
                used.setdefault(number, os.path.relpath(path, ROOT))
    assert {n: f for n, f in used.items() if n not in known} == {}


def test_only_title_routes():
    from resources.lib import router
    assert set(router.ROUTES) == {"", "settings", "launch", "clear_cache", "watch", "rd/cloud", "rd/torrent",
                                  "rd/play", "rd/add_magnet"}
