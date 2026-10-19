"""Static checks on addon.xml, settings.xml and strings.po."""

import os
import re
import xml.etree.ElementTree as ET

ADDON_DIR = os.path.join(os.path.dirname(__file__), "..", "plugin.video.novaflix")


def _po_ids():
    path = os.path.join(ADDON_DIR, "resources", "language", "resource.language.en_gb", "strings.po")
    with open(path, encoding="utf-8") as f:
        return {int(x) for x in re.findall(r'msgctxt "#(\d+)"', f.read())}


def test_addon_xml_identity_and_requirements():
    root = ET.parse(os.path.join(ADDON_DIR, "addon.xml")).getroot()
    assert root.get("id") == "plugin.video.novaflix"
    assert root.get("name") == "NovaFlix"
    assert re.fullmatch(r"\d+\.\d+\.\d+", root.get("version"))
    imports = {i.get("addon"): i.get("version") for i in root.iter("import")}
    assert imports.get("xbmc.python") == "3.0.1"


def test_addon_xml_declares_plugin_and_service():
    root = ET.parse(os.path.join(ADDON_DIR, "addon.xml")).getroot()
    points = {e.get("point"): e.get("library") for e in root.iter("extension")}
    assert points["xbmc.python.pluginsource"] == "default.py"
    assert points["xbmc.service"] == "service.py"
    for library in ("default.py", "service.py"):
        assert os.path.isfile(os.path.join(ADDON_DIR, library))


def test_addon_assets_exist():
    root = ET.parse(os.path.join(ADDON_DIR, "addon.xml")).getroot()
    for asset in root.iter("assets"):
        for child in asset:
            assert os.path.isfile(os.path.join(ADDON_DIR, child.text)), child.text


def test_settings_labels_exist_in_strings_po():
    tree = ET.parse(os.path.join(ADDON_DIR, "resources", "settings.xml"))
    ids = _po_ids()
    for element in tree.iter():
        for attr in ("label", "help"):
            value = element.get(attr)
            if value is not None:
                assert int(value) in ids, f"{element.tag} {attr}={value}"


def test_strings_po_ids_are_unique():
    path = os.path.join(ADDON_DIR, "resources", "language", "resource.language.en_gb", "strings.po")
    with open(path, encoding="utf-8") as f:
        found = re.findall(r'msgctxt "#(\d+)"', f.read())
    assert len(found) == len(set(found))
