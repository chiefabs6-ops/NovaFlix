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


def test_title_page_buttons_size_to_their_words():
    # Fixed widths left "Play S1 E1" in a 420 px pill; Kodi sizes a grouplist button to its label.
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-show.xml")).getroot()
    buttons = {int(c.get("id")): c.find("width") for c in root.iter("control") if c.get("id") in ("500", "501", "502", "503")}
    for control_id, width in buttons.items():
        assert width.text == "auto" and int(width.get("min")) <= 220, control_id
    assert int(buttons[501].get("max")) >= 400  # "Remove from My List" needs ~400 px at font30_title


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
    assert "[Control.HasFocus(100) | Control.HasFocus(101)]" in text


def test_generated_sections_are_current():
    """tools/gen_layouts.py writes the generated parts of the layouts; the files must match it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_layouts", os.path.join(SKIN, "..", "..", "..", "..", "tools",
                                                                              "gen_layouts.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert gen.stale() == [], "run tools/gen_layouts.py"


def test_labelled_fields_hide_when_empty():
    """Cinematic UI: a labelled value (small grey title over the value) sits in a group that hides,
    title and all, when its property is empty."""
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-app.xml")).getroot()
    for key in ("hero_rating", "hero_year", "hero_kind", "hero_genres"):
        wanted = f"!String.IsEmpty(Window.Property({key}))"
        groups = [g for g in root.iter("control") if g.get("type") == "group" and g.findtext("visible") == wanted]
        assert groups, f"no group hides with {key}"
        labels = [c for g in groups for c in g.iter("control") if c.get("type") == "label"]
        assert any(f"Window.Property({key})" in (c.findtext("label") or "") for c in labels)
        assert len(labels) >= 2, f"{key}: the grey title must hide with the value"


# -- final review fixes ---------------------------------------------------------------------------

def _app_root():
    return ET.parse(os.path.join(LAYOUTS, "novaflix-app.xml")).getroot()


@pytest.mark.parametrize("grid_id", ids.GRIDS)
def test_grid_panel_fits_on_screen(grid_id):
    """A panel scrolls only past its last row: rows below the screen would hide the focused card."""
    panel = next(c for c in _app_root().iter("control") if c.get("id") == str(grid_id))
    top, height = int(panel.findtext("top")), int(panel.findtext("height"))
    assert top + height <= 1080


def test_sidebar_right_reaches_the_empty_list_offer():
    sidebar = next(c for c in _app_root().iter("control") if c.get("id") == str(ids.SIDEBAR))
    targets = [(o.get("condition"), o.text) for o in sidebar.findall("onright")]
    offer = [i for i, (cond, t) in enumerate(targets) if t == str(ids.GRID_EMPTY_ACTION)]
    grid = [i for i, (cond, t) in enumerate(targets) if t == str(ids.GRID)]
    assert offer and grid and offer[0] < grid[0]


@pytest.mark.parametrize("name", XMLS)
def test_no_double_negation(name):
    assert "!!" not in open(os.path.join(LAYOUTS, name), encoding="utf-8").read()


@pytest.mark.parametrize("name", XMLS)
def test_remote_images_load_in_the_background(name):
    root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
    for texture in root.iter("texture"):
        text = texture.text or ""
        if any(k in text for k in ("Property(hero_logo)", "Property(logo)", "Property(art)", "Property(hero_art)", "search_art",
                                   "Art(")):
            assert texture.get("background") == "true", f"{name}: {text}"


# -- PC look-through fixes (owner screenshots, 2026-10-23) --------------------------------------------

@pytest.mark.parametrize("name", XMLS)
def test_menu_condition_does_not_use_controlgroup_without_an_id(name):
    """ControlGroup(9100).HasFocus without "(id)" never turned true on the PC: the menu never opened."""
    assert "ControlGroup(" not in open(os.path.join(LAYOUTS, name), encoding="utf-8").read()


@pytest.mark.parametrize("name", XMLS)
def test_zoom_animations_centre_on_the_control(name):
    """An explicit centre is in screen coordinates: the focused Play button slid down and right."""
    root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
    for anim in root.iter("animation"):
        if anim.get("effect") == "zoom":
            assert anim.get("center") == "auto", f"{name}: zoom centre {anim.get('center')}"


def test_card_focus_rings_only_show_while_their_list_has_focus():
    root = _app_root()
    for container in root.iter("control"):
        if container.get("type") not in ("list", "panel") or container.get("id") in ("100",):
            continue
        cid = container.get("id")
        for layout in container.findall("focusedlayout"):
            for image in layout.iter("control"):
                tex = image.find("texture")
                if tex is not None and tex.text == "av-r10-ring.png":
                    assert f"Control.HasFocus({cid})" in (image.findtext("visible") or ""), cid


@pytest.mark.parametrize("grid_id", ids.GRIDS)
def test_genre_tiles_fill_whole_rows_of_the_grid(grid_id):
    panel = next(c for c in _app_root().iter("control") if c.get("id") == str(grid_id))
    height = int(panel.findtext("height"))
    for layout in panel.findall("itemlayout"):
        assert height % int(layout.get("height")) == 0, layout.get("height")


def test_hero_plot_shows_whole_lines_only():
    root = _app_root()
    box = next(c for c in root.iter("control") if c.get("type") == "textbox"
               and "hero_plot" in (c.findtext("label") or ""))
    assert int(box.findtext("height")) == 102  # three font12 lines


def test_focused_cards_have_room_for_their_ring_and_zoom():
    """The ring sits 6 px outside the card and the zoom adds ~8 px: rows clip anything beyond their edge."""
    for name in ("novaflix-app.xml", "novaflix-show.xml"):
        root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
        for container in root.iter("control"):
            if container.get("type") not in ("list", "panel"):
                continue
            for layout in container.findall("focusedlayout"):
                card = layout.find("control")
                if card is None or card.get("type") != "group":
                    continue
                assert int(card.findtext("left")) >= 16 and int(card.findtext("top")) >= 14, \
                    f"{name} {container.get('id')}"


@pytest.mark.parametrize("name", ["novaflix-app.xml", "novaflix-login.xml"])
def test_search_screens_use_the_shipped_backdrop(name):
    text = open(os.path.join(LAYOUTS, name), encoding="utf-8").read()
    assert "av-search-backdrop.jpg" in text and "search_art" not in text


def test_peek_pictures_fill_the_screen_and_fade_out():
    """A 640 px band left a hard edge behind the posters; the picture fills the screen like Home's."""
    for image in _app_root().iter("control"):
        tex = image.find("texture")
        if image.get("type") == "image" and tex is not None and ".ListItem.Art(fanart)" in (tex.text or ""):
            assert int(image.findtext("height")) == 1080


def test_tile_pages_use_the_full_height_grid():
    tiles = next(c for c in _app_root().iter("control") if c.get("id") == str(ids.GRID_TILES))
    assert int(tiles.findtext("top")) <= 160 and int(tiles.findtext("height")) >= 880


def test_source_rows_leave_room_for_the_focus_ring():
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-sources.xml")).getroot()
    sources = next(c for c in root.iter("control") if c.get("id") == str(ids.SOURCES_LIST))
    row = sources.find("focusedlayout").find("control")
    assert row.get("type") == "group" and int(row.findtext("left")) >= 4
    assert int(row.findtext("left")) + int(row.findtext("width")) + 3 <= int(sources.findtext("width"))


@pytest.mark.parametrize("name", XMLS)
def test_pills_are_drawn_at_the_height_they_were_made_for(name):
    """A pill image stretched to another height bends its round ends (the chip ring did not match its chip)."""
    import re
    root = ET.parse(os.path.join(LAYOUTS, name)).getroot()
    for image in root.iter("control"):
        tex = image.find("texture")
        if image.get("type") != "image" or tex is None:
            continue
        found = re.fullmatch(r"av-pill(\d+)(-ring)?\.png", tex.text or "")
        if found:
            size = int(found.group(1))
            assert int(image.findtext("height")) == size, f"{name}: {tex.text} at {image.findtext('height')}"
            assert tex.get("border") == str(size // 2), f"{name}: {tex.text} border {tex.get('border')}"


def test_language_chips_have_room_for_long_counts():
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-sources.xml")).getroot()
    wide = [c for c in root.iter("control") if c.get("type") == "label"
            and "chip_wide" in (c.findtext("visible") or "") and "!String.IsEmpty(ListItem.Property(chip_wide))" in c.findtext("visible")]
    assert wide and min(int(c.findtext("width")) for c in wide) >= 160


def test_source_rows_span_the_drawer():
    """A loop once reused the row's width name for the chip width: every row became 114 px wide."""
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-sources.xml")).getroot()
    sources = next(c for c in root.iter("control") if c.get("id") == str(ids.SOURCES_LIST))
    for layout in ("itemlayout", "focusedlayout"):
        row = sources.find(layout).find("control")
        assert int(row.findtext("width")) >= 880, layout


def test_hero_buttons_fit_their_words_with_a_gap():
    groups = {}
    for g in _app_root().iter("control"):
        if g.get("type") == "group":
            for child in g.findall("control"):
                if child.get("id") in ("201", "202"):
                    groups[child.get("id")] = (int(g.findtext("left")), int(g.findtext("width")))
                    assert not (child.findtext("label") or "").strip(), "the words are a separate label"
    (play_left, play_width), (info_left, info_width) = groups["201"], groups["202"]
    assert info_left - (play_left + play_width) >= 20
    assert play_width <= 260 and info_width <= 290


def test_title_page_plot_can_be_focused_and_scrolls():
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-show.xml")).getroot()
    by_id = {c.get("id"): c for c in root.iter("control") if c.get("id")}
    plot = by_id[str(ids.SHOW_PLOT)]
    assert plot.findtext("ondown") == str(ids.SHOW_PLAY)
    box = next(c for c in root.iter("control") if c.get("type") == "textbox" and "Property(plot)" in (c.findtext("label") or ""))
    assert box.find("autoscroll") is not None and f"Control.HasFocus({ids.SHOW_PLOT})" in box.findtext("autoscroll")
    assert int(box.findtext("width")) >= 1000
    buttons = next(c for c in root.iter("control") if c.get("type") == "grouplist"
                   and any(b.get("id") == str(ids.SHOW_PLAY) for b in c.findall("control")))
    assert buttons.findtext("onup") == str(ids.SHOW_PLOT)


def test_home_plot_and_dots_can_be_focused():
    root = _app_root()
    by_id = {c.get("id"): c for c in root.iter("control") if c.get("id")}
    plot, dots = by_id[str(ids.HERO_PLOT)], by_id[str(ids.HERO_DOTS)]
    assert plot.findtext("ondown") == str(ids.HERO_PLAY)
    assert by_id[str(ids.HERO_PLAY)].findtext("onup") == str(ids.HERO_PLOT)
    downs = {o.get("condition"): o.text for o in by_id[str(ids.HERO_PLAY)].findall("ondown")}
    assert str(ids.HERO_DOTS) in downs.values()
    assert dots.findtext("onup") == str(ids.HERO_PLAY)
    box = next(c for c in root.iter("control") if c.get("type") == "textbox" and "hero_plot" in (c.findtext("label") or ""))
    assert f"Control.HasFocus({ids.HERO_PLOT})" in box.findtext("autoscroll")


def test_up_next_buttons_line_up_with_the_picture():
    root = ET.parse(os.path.join(LAYOUTS, "novaflix-prompt.xml")).getroot()
    text = open(os.path.join(LAYOUTS, "novaflix-prompt.xml"), encoding="utf-8").read()
    assert '"8C05070A"' not in text and "8C05070A" not in text  # no hard-edged box over the video
    by_id = {c.get("id"): c for c in root.iter("control") if c.get("id")}
    for control_id, left in (("9001", 1196), ("9000", 1504)):
        button = by_id[control_id]
        assert int(button.findtext("left")) == left
        slides = [a for a in button.findall("animation") if a.get("effect") == "slide"
                  and "Property(title)" in (a.get("condition") or "")]
        assert slides and slides[0].get("end") == "-132,0", control_id  # 1196 - 132 = 1064, the picture's left
