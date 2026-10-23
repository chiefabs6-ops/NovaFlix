# tests/test_layouts.py
"""M12: every layout parses, uses only Estuary fonts and existing images, and holds every
control ID the Python code addresses."""

import os
import xml.etree.ElementTree as ET

import pytest

from resources.lib.gui import ids

SKIN = os.path.join(os.path.dirname(__file__), "..", "plugin.video.novaflix", "resources", "skins", "Default")
LAYOUTS = os.path.join(SKIN, "1080i")
MEDIA = os.path.join(SKIN, "media")
ESTUARY_FONTS = {"font10", "font12", "font13", "font14", "font23_narrow", "font25_narrow", "font27",
                 "font27_narrow", "font32", "font37", "font45", "font60", "font_clock", "font_flag",
                 "font20_title", "font25_title", "font30_title", "font32_title", "font36_title", "font40_title",
                 "font45_title", "font52_title", "font_MainMenu", "Mono26"}
TEXTURE_TAGS = {"texture", "texturefocus", "texturenofocus", "texturebg", "lefttexture", "midtexture",
                "righttexture", "bordertexture", "alttexturefocus", "alttexturenofocus"}
XMLS = sorted(f for f in os.listdir(LAYOUTS) if f.endswith(".xml"))


@pytest.mark.parametrize("name", XMLS)
def test_layout_parses_and_uses_known_fonts_and_images(name):
    root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
    for font in root.iter("font"):
        assert font.text in ESTUARY_FONTS, f"{name}: unknown font {font.text}"
    for el in root.iter():
        values = []
        if el.tag in TEXTURE_TAGS and el.text:
            values.append(el.text.strip())
        if el.get("diffuse"):
            values.append(el.get("diffuse"))
        for value in values:
            if value and "$" not in value and not value.startswith(("special://", "http")):
                assert os.path.exists(os.path.join(MEDIA, value)), f"{name}: missing image {value}"


@pytest.mark.parametrize("name,wanted", sorted(ids.WINDOW_IDS.items()))
def test_layout_has_every_control_the_code_uses(name, wanted):
    root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
    present = {int(c.get("id")) for c in root.iter("control") if c.get("id", "").isdigit()}
    assert set(wanted) <= present, f"{name}: missing controls {sorted(set(wanted) - present)}"


@pytest.mark.parametrize("name", XMLS)
def test_no_unexpanded_placeholders(name):
    text = open(os.path.join(LAYOUTS, name), encoding="utf-8").read()
    for marker in ("<include", "ROW_ID", "rowN_", ">UP<", ">DOWN<", "expanded inline", "as described above"):
        assert marker not in text, f"{name}: leftover {marker}"


def test_related_view_rows_hide_when_empty_and_sidebar_reaches_them():
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-app.xml")).getroot()
    lists_by_id = {int(c.get("id")): c for c in root.iter("control") if c.get("id", "").isdigit()}
    for n, control_id in enumerate(ids.RELATED_ROWS):
        row = lists_by_id[control_id]
        assert row.get("type") == "list"
        downs = [d.text for d in row.findall("ondown")]
        if n < len(ids.RELATED_ROWS) - 1:
            assert downs == [str(ids.RELATED_ROWS[n + 1])]
    text = open(os.path.join(LAYOUTS, "novaflix-app.xml"), encoding="utf-8").read()
    for control_id in ids.RELATED_ROWS:
        assert f"Integer.IsGreater(Container({control_id}).NumItems,0)" in text
    sidebar = lists_by_id[ids.SIDEBAR]
    targets = {o.get("condition"): o.text for o in sidebar.findall("onright")}
    assert targets["String.IsEqual(Window.Property(view),related)"] == "800"


def test_sidebar_settings_button_sits_below_the_list_and_reaches_every_view():
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-app.xml")).getroot()
    by_id = {int(c.get("id")): c for c in root.iter("control") if c.get("id", "").isdigit()}
    sidebar, settings = by_id[ids.SIDEBAR], by_id[ids.SIDEBAR_SETTINGS]
    assert sidebar.find("ondown").text == str(ids.SIDEBAR_SETTINGS)
    assert settings.get("type") == "button" and settings.find("onup").text == str(ids.SIDEBAR)
    as_targets = lambda c: {o.get("condition"): o.text for o in c.findall("onright")}
    assert as_targets(settings) == as_targets(sidebar)
    list_bottom = int(sidebar.find("top").text) + int(sidebar.find("height").text)
    assert int(settings.find("top").text) >= list_bottom


def test_open_sidebar_fits_without_scrolling():
    # The Explore accent bar is drawn at a fixed position, so the open list must never scroll.
    # Kodi does not choose item layouts per item, so the list has exactly one of each.
    from resources.lib.gui import app
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-app.xml")).getroot()
    sidebar = next(c for c in root.iter("control") if c.get("id") == str(ids.SIDEBAR))
    layouts = sidebar.findall("itemlayout") + sidebar.findall("focusedlayout")
    assert len(layouts) == 2 and not any(l.get("condition") for l in layouts)
    rows = len(app.SIDEBAR) + 1 + len(app.EXPLORE_ITEMS)
    assert rows * int(layouts[0].get("height")) <= int(sidebar.find("height").text)


@pytest.mark.parametrize("name", XMLS)
def test_conditions_do_not_embed_infolabels(name):
    # Kodi logs "Misplaced [" and drops the whole condition for $INFO[...] inside a boolean expression.
    root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
    for el in root.iter():
        texts = [el.get("condition") or ""] + ([el.text or ""] if el.tag == "visible" else [])
        for text in texts:
            assert "$INFO[" not in text, f"{name}: infolabel inside condition {text}"


def test_title_page_buttons_fit_and_my_list_label_has_room():
    # "Remove from My List" needs ~400 px at font30_title; the four buttons share one 1500 px row.
    import re
    xml = open(os.path.join(os.path.dirname(__file__), "..", "plugin.video.novaflix", "resources", "skins", "Default",
                            "1080i", "novaflix-show.xml"), encoding="utf-8").read()
    widths = {i: int(re.search(r'<control type="button" id="%d">\s*<width>(\d+)</width>' % i, xml).group(1))
              for i in (500, 501, 502, 503)}
    assert widths[501] >= 400
    assert sum(widths.values()) + 3 * 24 <= 1500


def test_rail_returns_focus_to_each_view():
    """Cinematic UI: the menu is group 9100 around the sidebar list and Settings; it opens while it has focus."""
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-app.xml")).getroot()
    by_id = {int(c.get("id")): c for c in root.iter("control") if c.get("id", "").isdigit()}
    menu = by_id[ids.MENU_GROUP]
    inside = {int(c.get("id")) for c in menu.iter("control") if c.get("id", "").isdigit()}
    assert {ids.SIDEBAR, ids.SIDEBAR_SETTINGS} <= inside
    targets = {o.get("condition"): o.text for o in by_id[ids.SIDEBAR].findall("onright")}
    assert targets["String.IsEqual(Window.Property(view),grid)"] == str(ids.GRID)
    assert targets["String.IsEqual(Window.Property(view),related)"] == str(ids.RELATED_ROWS[0])
    text = open(os.path.join(LAYOUTS, "novaflix-app.xml"), encoding="utf-8").read()
    assert "ControlGroup(9100).HasFocus" in text


def test_generated_sections_are_current():
    """tools/gen_layouts.py writes the generated parts of the layouts; the files must match it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_layouts", os.path.join(SKIN, "..", "..", "..", "..", "tools",
                                                                              "gen_layouts.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert gen.stale() == [], "run tools/gen_layouts.py"
