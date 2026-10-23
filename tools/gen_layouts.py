# tools/gen_layouts.py
"""Writes the generated sections of the NovaFlix layouts (Cinematic UI, 0.4.0).

Kodi add-on skins cannot use <include>, so parts that repeat (the sidebar's row kinds, the
poster and wide item layouts of every row) are written here once and spliced into the XML
between <!-- gen:NAME --> and <!-- /gen:NAME --> markers.

Usage:  .venv\\Scripts\\python tools\\gen_layouts.py
tests/test_layouts.py::test_generated_sections_are_current fails when a file is out of date.
"""

import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LAYOUTS = os.path.join(ROOT, "plugin.video.novaflix", "resources", "skins", "Default", "1080i")

# Colours (plan: Global Constraints)
GROUND, S1, S2, S3 = "FF05070A", "FF0C1015", "FF141A21", "FF1E2630"
INK, INK2, INK3 = "FFFFFFFF", "FFD3D8DF", "FF8F98A4"
CYAN, CYAN_HI, CYAN_INK = "FF00A6D6", "FF35CDF5", "FF001820"
OK, WARN, BAD = "FF3FD28F", "FFF5B04F", "FFFF6B7A"

# ControlGroup(9100).HasFocus without an id never turned true on Kodi 21: test the two controls
MENU_OPEN = "[Control.HasFocus(100) | Control.HasFocus(101)]"
VIEW_TARGETS = [  # (condition, control) the sidebar and Settings hand focus to on Right
    ("String.IsEqual(Window.Property(view),home) + String.IsEmpty(Window.Property(offline))", 201),
    ("String.IsEqual(Window.Property(view),home) + !String.IsEmpty(Window.Property(offline))", 340),
    ("String.IsEqual(Window.Property(view),grid) + !String.IsEmpty(Window.Property(grid_empty_action))", 410),
    ("String.IsEqual(Window.Property(view),grid) + !String.IsEmpty(Window.Property(grid_panel))", 401),
    ("String.IsEqual(Window.Property(view),grid)", 400),
    ("String.IsEqual(Window.Property(view),related)", 800),
]


# -- XML helpers -----------------------------------------------------------------------------------

def neg(cond):
    """The opposite condition, without a double "!!" (cond is one term)."""
    return cond[1:] if cond.startswith("!") else "!" + cond


def _visible(cond):
    return f"<visible>{cond}</visible>" if cond else ""


def img(left, top, width, height, texture, diffuse=None, border=None, visible=None, extra=""):
    attrs = (f' border="{border}"' if border is not None else "") + (f' colordiffuse="{diffuse}"' if diffuse else "")
    return (f'<control type="image"><left>{left}</left><top>{top}</top><width>{width}</width><height>{height}</height>'
            f'<texture{attrs}>{texture}</texture>{extra}{_visible(visible)}</control>')


def lbl(left, top, width, height, font, color, label, visible=None, align=None, aligny="center", extra=""):
    parts = [f'<control type="label"><left>{left}</left><top>{top}</top><width>{width}</width><height>{height}</height>',
             f"<font>{font}</font><textcolor>{color}</textcolor>"]
    if align:
        parts.append(f"<align>{align}</align>")
    if aligny:
        parts.append(f"<aligny>{aligny}</aligny>")
    parts.append(f"<label>{label}</label>{extra}{_visible(visible)}</control>")
    return "".join(parts)


def onright():
    return "".join(f'<onright condition="{cond}">{target}</onright>' for cond, target in VIEW_TARGETS)


def lines(*parts):
    return "\n".join(p for p in parts if p)


# -- sidebar: icon rail that opens into the menu ---------------------------------------------------

def _is(kind):
    return f"String.IsEqual(ListItem.Property(kind),{kind})"


ACTIVE = "!String.IsEmpty(ListItem.Property(active))"
IDLE = "String.IsEmpty(ListItem.Property(active))"
EXPLORE_HERE = "String.IsEqual(Window.Property(current_group),explore)"


def _sidebar_row(focused):
    """One row layout. `focused`: the focusedlayout, which only looks focused while the list has focus."""
    me = "Control.HasFocus(100)" if focused else "false"
    not_me = "!Control.HasFocus(100)" if focused else "true"
    icon = "$INFO[ListItem.Property(icon)]"
    rows = []
    for kind in ("main", "explore"):
        here = ACTIVE if kind == "main" else EXPLORE_HERE
        away = IDLE if kind == "main" else "!" + EXPLORE_HERE
        k = _is(kind)
        rows += [
            # icon: white while focused, cyan for the page shown (menu open) / white (rail), grey otherwise
            img(41, 15, 30, 30, icon, INK, visible=f"{k} + {me}"),
            img(41, 15, 30, 30, icon, CYAN, visible=f"{k} + {not_me} + {here} + {MENU_OPEN}"),
            img(41, 15, 30, 30, icon, INK, visible=f"{k} + {not_me} + {here} + !{MENU_OPEN}"),
            img(41, 15, 30, 30, icon, INK3, visible=f"{k} + {not_me} + {away}"),
            # the rail's mark under the page shown
            img(53, 50, 6, 6, "av-dot.png", CYAN, visible=f"{k} + {here} + !{MENU_OPEN}"),
            # labels, only while the menu is open
            lbl(96, 0, 300, 60, "font30_title", INK, "$INFO[ListItem.Label]", visible=f"{k} + {me}"),
            lbl(96, 0, 300, 60, "font13", INK, "$INFO[ListItem.Label]",
                visible=f"{k} + {not_me} + {here} + {MENU_OPEN}"),
            lbl(96, 0, 300, 60, "font13", INK3, "$INFO[ListItem.Label]",
                visible=f"{k} + {not_me} + {away} + {MENU_OPEN}"),
        ]
    k = _is("sub")
    rows += [
        lbl(110, 0, 290, 60, "font13", INK, "$INFO[ListItem.Label]", visible=f"{k} + {me}"),
        lbl(110, 0, 290, 60, "font12", INK, "$INFO[ListItem.Label]",
            visible=f"{k} + {not_me} + {ACTIVE} + {MENU_OPEN}"),
        lbl(110, 0, 290, 60, "font12", INK3, "$INFO[ListItem.Label]",
            visible=f"{k} + {not_me} + {IDLE} + {MENU_OPEN}"),
        # Explore's open / closed chevron
        img(352, 18, 24, 24, "av-icon-expand_more.png", INK3,
            visible=f"{_is('explore')} + String.IsEmpty(Window.Property(explore_open)) + {MENU_OPEN}"),
        img(352, 18, 24, 24, "av-icon-expand_less.png", INK3,
            visible=f"{_is('explore')} + !String.IsEmpty(Window.Property(explore_open)) + {MENU_OPEN}"),
    ]
    if focused:
        rows.insert(0, img(0, 12, 5, 36, "av-white.png", CYAN, visible=me))
    return "\n".join(rows)


def sidebar():
    return lines(
        '<!-- Closed: a 112 px rail of icons over the page. Open (focus in group 9100): a dark fade from the left,',
        '     labels beside the icons, the page dimmed and pushed right (each view group animates on the same',
        '     condition). List 100 rows: main entries, Explore, and Explore\'s lists while it is open. -->',
        img(0, 0, 1920, 1080, "av-shade-menu.png", visible=MENU_OPEN,
            extra='<animation effect="fade" start="0" end="100" time="250">Visible</animation>'
                  '<animation effect="fade" start="100" end="0" time="200">Hidden</animation>'),
        img(30, 40, 52, 52, "av-logo.png", extra="<aspectratio>keep</aspectratio>"),
        lbl(98, 40, 320, 52, "font30_title", INK, "NOVA[COLOR " + CYAN + "]FLIX[/COLOR]", visible=MENU_OPEN,
            extra='<animation effect="fade" start="0" end="100" time="200">Visible</animation>'),
        '<control type="group" id="9100">',
        '<control type="list" id="100">',
        "<left>0</left><top>160</top><width>420</width><height>800</height>",
        '<orientation>vertical</orientation><scrolltime tween="quadratic" easing="out">120</scrolltime>',
        "<ondown>101</ondown>" + onright(),
        '<itemlayout width="420" height="60">',
        _sidebar_row(focused=False),
        "</itemlayout>",
        '<focusedlayout width="420" height="60">',
        _sidebar_row(focused=True),
        "</focusedlayout>",
        "</control>",
        '<!-- Settings, at the bottom (opens the Settings menu: add-on settings, My TorBox) -->',
        '<control type="button" id="101">',
        "<left>0</left><top>990</top><width>420</width><height>60</height>",
        '<texturefocus colordiffuse="00FFFFFF">av-white.png</texturefocus>'
        '<texturenofocus colordiffuse="00FFFFFF">av-white.png</texturenofocus>',
        "<label></label><onup>100</onup>" + onright(),
        "</control>",
        "</control>",
        img(0, 1002, 5, 36, "av-white.png", CYAN, visible="Control.HasFocus(101)"),
        img(41, 1005, 30, 30, "av-icon-settings.png", INK, visible="Control.HasFocus(101)"),
        img(41, 1005, 30, 30, "av-icon-settings.png", INK3, visible="!Control.HasFocus(101)"),
        lbl(96, 990, 300, 60, "font30_title", INK, "$INFO[Window.Property(settings_label)]",
            visible="Control.HasFocus(101)"),
        lbl(96, 990, 300, 60, "font13", INK3, "$INFO[Window.Property(settings_label)]",
            visible=f"!Control.HasFocus(101) + {MENU_OPEN}"),
    )


def menu_push():
    """Added to each view's outer group: the page dims and moves right while the menu is open."""
    return ('<animation type="Conditional" condition="' + MENU_OPEN + '" reversible="true">'
            '<effect type="fade" start="100" end="45" time="250"/>'
            '<effect type="slide" start="0,0" end="40,0" time="250" tween="cubic" easing="out"/></animation>')


# -- shared pieces -------------------------------------------------------------------------------------

X = 184             # content left edge on every app-window view
PAD = 18            # room around a card inside its row for the focus ring and zoom (rows clip)
PULSE = '<animation effect="fade" start="55" end="100" time="900" pulse="true" condition="true">Conditional</animation>'
SPIN = '<animation effect="rotate" end="-360" center="auto" time="900" loop="true" condition="true">Conditional</animation>'


def group(left, top, width, height, children, visible=None, extra="", control_id=None):
    gid = f' id="{control_id}"' if control_id else ""
    return lines(f'<control type="group"{gid}><left>{left}</left><top>{top}</top><width>{width}</width>'
                 f'<height>{height}</height>{extra}{_visible(visible)}', children, "</control>")


def zoom_when(condition, percent, center):
    return (f'<animation effect="zoom" start="100" end="{percent}" time="150" center="auto" '
            f'condition="{condition}" reversible="true">Conditional</animation>')


def pill_button(control_id, left, top, width, label, primary, nav, icon=None, label_left=None):
    """A 66 px pill. primary: white fill and dark text; else a translucent white fill. Focus: a cyan
    ring and 105 % zoom (both in the group, so they move together)."""
    fill, text = ("FFFFFFFF", GROUND) if primary else ("24FFFFFF", INK)
    offset = 70 if icon else 34
    parts = [
        img(-6, -6, width + 12, 78, "av-pill78-ring.png", CYAN, border=39, visible=f"Control.HasFocus({control_id})"),
        f'<control type="button" id="{control_id}"><left>0</left><top>0</top><width>{width}</width><height>66</height>'
        f'<font>font30_title</font><aligny>center</aligny><textoffsetx>{offset}</textoffsetx>'
        f'<textcolor>{text}</textcolor><focusedcolor>{text}</focusedcolor>'
        f'<texturefocus border="33" colordiffuse="{fill}">av-pill66.png</texturefocus>'
        f'<texturenofocus border="33" colordiffuse="{fill}">av-pill66.png</texturenofocus>'
        f"<label>{label}</label>{nav}</control>",
    ]
    if icon:
        parts.append(img(30, 18, 30, 30, icon, CYAN if primary else INK))
    return group(left, top, width, 66, "\n".join(parts),
                 extra=zoom_when(f"Control.HasFocus({control_id})", 105, f"{width // 2},33"))


def labelled_fields(top, fields, source="Window.Property({})"):
    """Grey titles over values, laid out left to right; a field with no value hides, title and all.
    fields: (title label, property, width). source: the infolabel pattern the property is read from."""
    items = []
    for title, prop, width in fields:
        info = source.format(prop)
        items.append(group(0, 0, width, 64, lines(
            lbl(0, 0, width, 24, "font10", INK3, title, aligny="top"),
            lbl(0, 26, width, 38, "font13", INK2, f"$INFO[{info}]", aligny="top")),
            visible=f"!String.IsEmpty({info})"))
    return lines(f'<control type="grouplist"><left>{X}</left><top>{top}</top><width>1200</width><height>64</height>'
                 '<orientation>horizontal</orientation><itemgap>30</itemgap><usecontrolwidth>true</usecontrolwidth>',
                 "\n".join(items), "</control>")


# -- cards ---------------------------------------------------------------------------------------------

def _wide_art(width, height):
    mask = "av-mask-wide10.png"
    return lines(
        img(0, 0, width, height, "av-r10.png", S2, border=10),
        img(0, 0, width, height, "$INFO[ListItem.Art(thumb)]", visible="!String.IsEmpty(ListItem.Property(has_wide))",
            extra=f'<aspectratio>scale</aspectratio>').replace("<texture>", f'<texture diffuse="{mask}" background="true">'),
        img(0, 0, width, height, "$INFO[ListItem.Art(poster)]", visible="String.IsEmpty(ListItem.Property(has_wide))",
            extra='<aspectratio>scale</aspectratio>').replace("<texture>", f'<texture diffuse="{mask}" background="true">'),
        img(0, 0, width, height, "av-shade-card.png").replace("<texture>", f'<texture diffuse="{mask}">'),
    )


AVAIL_DOTS = (("available", OK), ("upcoming", WARN), ("sub_only", INK2), ("unavailable", BAD),
              ("unknown", INK3), ("checking", INK3))


def wide_card(width, height, focused, episode=False, cid=None):
    """Continue Watching / episodes: the picture with its title, details and progress over it."""
    body = [
        _wide_art(width, height),
        lbl(20, height - 92, width - 40, 40, "font13", INK, "[B]$INFO[ListItem.Label][/B]",
            extra="<scroll>true</scroll>" if focused else ""),
    ]
    for state, colour in AVAIL_DOTS:
        body.append(img(20, height - 42, 10, 10, "av-dot.png", colour,
                        visible=f"String.IsEqual(ListItem.Property(avail),{state})"))
    body += [
        lbl(20, height - 56, width - 40, 36, "font12", INK2, "$INFO[ListItem.Label2]",
            visible="String.IsEmpty(ListItem.Property(avail))"),
        lbl(38, height - 56, width - 58, 36, "font12", INK2, "$INFO[ListItem.Label2]",
            visible="!String.IsEmpty(ListItem.Property(avail))"),
        f'<control type="progress"><left>20</left><top>{height - 16}</top><width>{width - 40}</width><height>4</height>'
        '<info>ListItem.PercentPlayed</info>'
        '<texturebg border="2" colordiffuse="40FFFFFF">av-bar.png</texturebg>'
        f'<midtexture border="2" colordiffuse="{CYAN}">av-bar.png</midtexture>'
        '<visible>Integer.IsGreater(ListItem.PercentPlayed,0)</visible></control>',
    ]
    if episode:  # watched episodes: dimmed, with a check
        body.insert(1, img(0, 0, width, height, "av-white.png", "8C05070A", visible="String.IsEqual(ListItem.Property(watched),true)"
                           ).replace("<texture", '<texture diffuse="av-mask-wide10.png"', 1))
        body += [img(width - 46, 14, 32, 32, "av-dot.png", "B305070A", visible="String.IsEqual(ListItem.Property(watched),true)"),
                 img(width - 42, 18, 24, 24, "av-icon-check_circle.png", OK,
                     visible="String.IsEqual(ListItem.Property(watched),true)")]
    if focused:
        body.insert(0, img(-6, -6, width + 12, height + 12, "av-r10-ring.png", INK, border=10,
                           visible=f"Control.HasFocus({cid})"))
        return group(PAD, 16, width, height, "\n".join(body), extra=zoom_when(f"Control.HasFocus({cid})", 104, "auto"))
    return group(PAD, 16, width, height, "\n".join(body))


def poster_card(width, height, focused, cid=None):
    """A poster; tiles (search, filter, genres before pictures) and View All are drawn on a surface."""
    mask = "av-mask-poster10.png"
    tile = "[String.IsEqual(ListItem.Property(kind),tile) | String.IsEqual(ListItem.Property(kind),more)]"
    body = [
        img(0, 0, width, height, "av-r10.png", S2, border=10),
        lbl(16, 16, width - 32, height - 32, "font12", INK2, "$INFO[ListItem.Label]", aligny="center", align="center",
            visible=f"!{tile} + String.IsEmpty(ListItem.Art(poster))", extra="<wrapmultiline>true</wrapmultiline>"),
        img(0, 0, width, height, "$INFO[ListItem.Art(poster)]", visible=f"!{tile}",
            extra="<aspectratio>scale</aspectratio>").replace("<texture>", f'<texture diffuse="{mask}" background="true">'),
        img(width // 2 - 32, height // 2 - 70, 64, 64, "$INFO[ListItem.Property(icon)]", INK2,
            visible="String.IsEqual(ListItem.Property(kind),tile)"),
        img(width // 2 - 32, height // 2 - 70, 64, 64, "av-icon-chevron_right.png", CYAN,
            visible="String.IsEqual(ListItem.Property(kind),more)"),
        lbl(14, height // 2 + 6, width - 28, 70, "font12", INK, "$INFO[ListItem.Label]", align="center", aligny="top",
            visible=tile, extra="<wrapmultiline>true</wrapmultiline>"),
        lbl(14, height // 2 + 76, width - 28, 60, "font10", INK3, "$INFO[ListItem.Label2]", align="center", aligny="top",
            visible="String.IsEqual(ListItem.Property(kind),tile)", extra="<wrapmultiline>true</wrapmultiline>"),
        img(12, 12, 130, 32, "av-pill32.png", "D9000000", border=16, visible="!String.IsEmpty(ListItem.Property(dub))"),
        lbl(12, 12, 130, 32, "font10", INK, "$INFO[ListItem.Property(dub)]", align="center",
            visible="!String.IsEmpty(ListItem.Property(dub))"),
    ]
    if focused:
        body.insert(0, img(-6, -6, width + 12, height + 12, "av-r10-ring.png", INK, border=10,
                           visible=f"Control.HasFocus({cid})"))
        return group(PAD, 16, width, height, "\n".join(body), extra=zoom_when(f"Control.HasFocus({cid})", 104, "auto"))
    return group(PAD, 16, width, height, "\n".join(body))


def card_list(control_id, left, top, width, kind, nav, item_gap=20):
    """A horizontal row of `kind` cards ('wide' 420x236 or 'poster' 200x300)."""
    cw, ch = (420, 236) if kind == "wide" else (200, 300)
    build = wide_card if kind == "wide" else poster_card
    height = ch + 30
    return lines(
        f'<control type="list" id="{control_id}"><left>{left}</left><top>{top}</top><width>{width}</width>'
        f'<height>{height}</height><orientation>horizontal</orientation>'
        f'<scrolltime tween="quadratic" easing="out">200</scrolltime>{nav}',
        f'<itemlayout width="{cw + item_gap}" height="{height}">', build(cw, ch, False, cid=control_id), "</itemlayout>",
        f'<focusedlayout width="{cw + item_gap}" height="{height}">', build(cw, ch, True, cid=control_id), "</focusedlayout>",
        "</control>")


# -- Home -----------------------------------------------------------------------------------------------

def _nav(**moves):
    out = []
    for direction, target in moves.items():
        if isinstance(target, list):
            out += [f'<on{direction} condition="{c}">{t}</on{direction}>' for c, t in target]
        else:
            out.append(f"<on{direction}>{target}</on{direction}>")
    return "".join(out)


HAS_CONTINUE = "Integer.IsGreater(Container(300).NumItems,0)"
HERO_FOCUS = "[Control.HasFocus(201) | Control.HasFocus(202) | Control.HasFocus(300)]"


def _hero_dots():
    items = []
    for n in range(5):
        here = f"String.IsEqual(Window.Property(hero_index),{n})"
        exists = f"Integer.IsGreater(Window.Property(hero_count),{n})"
        items.append(img(0, 0, 28, 8, "av-bar.png", INK, border=3, visible=f"{here} + {exists}"))
        items.append(img(0, 0, 8, 8, "av-dot.png", "47FFFFFF", visible=f"!{here} + {exists}"))
    return lines(f'<control type="grouplist"><left>{X}</left><top>648</top><width>400</width><height>8</height>'
                 '<orientation>horizontal</orientation><itemgap>8</itemgap><usecontrolwidth>true</usecontrolwidth>',
                 "\n".join(items), "</control>")


def _row_title(n, top):
    return lines(lbl(X, top, 1200, 44, "font30_title", INK2, f"$INFO[Window.Property(row{n}_title)]"),
                 lbl(X, top + 44, 1200, 36, "font12", INK3, f"$INFO[Window.Property(row{n}_status)]",
                     visible=f"!String.IsEmpty(Window.Property(row{n}_status))"))


def home():
    has_art = "!String.IsEmpty(Window.Property(hero_art))"
    logo = "!String.IsEmpty(Window.Property(hero_logo))"
    rows_focus = "[Control.HasFocus(310) | Control.HasFocus(320) | Control.HasFocus(330)]"
    hero = lines(
        lbl(X, 160, 1000, 36, "font12", CYAN_HI, "[B]$INFO[Window.Property(featured)][/B]",
            visible="!String.IsEmpty(Window.Property(hero_title))"),
        img(X, 200, 760, 125, "$INFO[Window.Property(hero_logo)]", visible=logo,
            extra='<aspectratio align="left" aligny="bottom">keep</aspectratio><fadetime>300</fadetime>').replace(
            "<texture>", '<texture background="true">'),
        lbl(X, 200, 1100, 125, "font52_title", INK, "$INFO[Window.Property(hero_title)]", aligny="bottom",
            visible=neg(logo)),
        labelled_fields(345, [("$ADDON[plugin.video.novaflix 30510]", "hero_rating", 110),
                              ("$ADDON[plugin.video.novaflix 30511]", "hero_year", 100),
                              ("$ADDON[plugin.video.novaflix 30512]", "hero_kind", 140),
                              ("$ADDON[plugin.video.novaflix 30513]", "hero_genres", 420)]),
        f'<control type="textbox"><left>{X}</left><top>424</top><width>640</width><height>102</height>'
        f'<font>font12</font><textcolor>{INK2}</textcolor><label>$INFO[Window.Property(hero_plot)]</label></control>',
        pill_button(201, X, 562, 300, "$INFO[Window.Property(play_label)]", True,
                    _nav(left=100, right=202, down=[(HAS_CONTINUE, 300), ("!" + HAS_CONTINUE, 310)]),
                    icon="av-icon-play_arrow.png"),
        pill_button(202, X + 318, 562, 340, "$INFO[Window.Property(info_label)]", False,
                    _nav(left=201, down=[(HAS_CONTINUE, 300), ("!" + HAS_CONTINUE, 310)]), icon="av-icon-info.png"),
        _hero_dots(),
    )
    rows = lines(
        group(0, 0, 1920, 330, lines(_row_title(0, 6), card_list(300, X - PAD, 50, 1920 - X + PAD, "wide",
                                                                 _nav(left=100, up=201, down=310))),
              visible=HAS_CONTINUE),
        group(0, 0, 1920, 420, lines(_row_title(1, 16), card_list(
            310, X - PAD, 60, 1920 - X + PAD, "poster",
            _nav(left=100, up=[(HAS_CONTINUE, 300), ("!" + HAS_CONTINUE, 201)], down=320)))),
        group(0, 0, 1920, 420, lines(_row_title(2, 16), card_list(320, X - PAD, 60, 1920 - X + PAD, "poster",
                                                                  _nav(left=100, up=310, down=330)))),
        group(0, 0, 1920, 420, lines(_row_title(3, 16), card_list(330, X - PAD, 60, 1920 - X + PAD, "poster",
                                                                  _nav(left=100, up=320)))),
    )
    skeleton = lines(*[img(l, t, w, h, "av-r10.png", S2, border=10, extra=PULSE) for l, t, w, h in (
        (X, 170, 200, 24), (X, 214, 560, 96), (X, 345, 460, 56), (X, 430, 620, 22), (X, 466, 540, 22),
        (X, 562, 250, 66), (X + 268, 562, 270, 66), (X, 702, 420, 236), (X + 440, 702, 420, 236),
        (X + 880, 702, 420, 236), (X + 1320, 702, 420, 236))])
    return lines(
        '<!-- the hero picture stays behind the page; the rows scroll over it, darker once focus leaves the hero -->',
        img(0, 0, 1920, 1080, "$INFO[Window.Property(hero_art)]",
            extra='<aspectratio>scale</aspectratio><fadetime>400</fadetime>').replace(
            "<texture>", '<texture background="true">'),
        img(0, 0, 1920, 1080, "av-white.png", "B305070A", visible="!String.IsEmpty(Window.Property(hero_dark))"),
        img(0, 0, 1920, 1080, "av-vignette.png"),
        img(0, 0, 1920, 1080, "av-shade-hero.png"),
        img(0, 0, 1920, 1080, "av-shade-bottom.png"),
        img(0, 0, 1920, 1080, "av-white.png", "D905070A", visible=rows_focus,
            extra='<animation effect="fade" time="250">VisibleChange</animation>'),
        f'<control type="grouplist"><left>0</left><top>0</top><width>1920</width><height>1080</height>'
        '<orientation>vertical</orientation><itemgap>0</itemgap><scrolltime tween="quadratic" easing="out">260</scrolltime>',
        group(0, 0, 1920, 690, hero, visible="String.IsEmpty(Window.Property(offline))"),
        rows,
        "</control>",
        '<!-- first load: the page\'s own shapes, softly pulsing -->',
        group(0, 0, 1920, 1080, skeleton, visible="String.IsEmpty(Window.Property(hero_title)) + "
                                                  "String.IsEmpty(Window.Property(offline))"),
        '<!-- offline -->',
        group(0, 0, 1920, 1080, lines(
            img(902, 300, 116, 116, "av-dot.png", S2),
            img(934, 332, 52, 52, "av-icon-cancel.png", INK3),
            lbl(X, 450, 1920 - 2 * X, 90, "font52_title", INK, "$ADDON[plugin.video.novaflix 30241]", align="center"),
            lbl(X, 548, 1920 - 2 * X, 44, "font13", INK2, "$INFO[Window.Property(offline)]", align="center"),
            pill_button(340, 835, 630, 250, "$INFO[Window.Property(retry_label)]", True, _nav(left=100)),
        ), visible="!String.IsEmpty(Window.Property(offline))"),
    )


# -- Grid -----------------------------------------------------------------------------------------------

def _addon(string_id):
    return f"$ADDON[plugin.video.novaflix {string_id}]"


PEEK_FIELDS = [(_addon(30510), "rating", 110), (_addon(30511), "year", 100), (_addon(30512), "kind_label", 140),
               (_addon(30513), "genres", 420)]


def peek(container, top=150):
    """The focused card's picture, title, labelled details and plot above a grid or rows."""
    item = f"Container({container}).ListItem"
    return lines(
        # the whole screen, faded like Home's hero, so no edge shows behind the posters
        img(0, 0, 1920, 1080, f"$INFO[{item}.Art(fanart)]",
            extra='<aspectratio>scale</aspectratio><fadetime>300</fadetime>').replace(
            "<texture>", '<texture background="true">'),
        img(0, 0, 1920, 1080, "av-vignette.png"),
        img(0, 0, 1920, 1080, "av-shade-hero.png"),
        img(0, 0, 1920, 1080, "av-shade-bottom.png"),
        lbl(X, top, 1300, 90, "font52_title", INK, f"$INFO[{item}.Label]"),
        labelled_fields(top + 100, PEEK_FIELDS, source=item + ".Property({})"),
        f'<control type="textbox"><left>{X}</left><top>{top + 178}</top><width>720</width><height>76</height>'
        f'<font>font12</font><textcolor>{INK2}</textcolor><label>$INFO[{item}.Property(plot)]</label></control>',
    )


def genre_card(width, height, focused, cid=None):
    """A genre: a picture from its own list under a left-to-right shade, the name large at the bottom left."""
    mask = "av-mask-wide10.png"
    body = [
        img(0, 0, width, height, "av-r10.png", S2, border=10),
        img(0, 0, width, height, "$INFO[ListItem.Art(thumb)]",
            extra="<aspectratio>scale</aspectratio><fadetime>300</fadetime>").replace(
            "<texture>", f'<texture diffuse="{mask}" background="true">'),
        img(0, 0, width, height, "av-shade-hero.png").replace("<texture>", f'<texture diffuse="{mask}">'),
        lbl(22, height - 74, width - 44, 60, "font45_title", INK, "$INFO[ListItem.Label]"),
    ]
    if focused:
        body.insert(0, img(-6, -6, width + 12, height + 12, "av-r10-ring.png", INK, border=10,
                           visible=f"Control.HasFocus({cid})"))
        return group(PAD, 16, width, height, "\n".join(body), extra=zoom_when(f"Control.HasFocus({cid})", 104, "auto"))
    return group(PAD, 16, width, height, "\n".join(body))


GENRES_SHOWN = "!String.IsEmpty(Window.Property(grid_genre_tab))"
WIDE_TILES = "String.IsEqual(Window.Property(grid_tiles),wide)"
SEARCH_ART = "av-search-backdrop.jpg"  # the concept's Shinjuku street (CC BY-SA 4.0, media/LICENSE-backdrop.txt)


def wide_tile(width, height, focused, cid=None):
    """Search page tiles: icon and words side by side on a see-through surface over the backdrop."""
    body = [
        img(0, 0, width, height, "av-r10.png", "B3141A21", border=10),
        img(28, height // 2 - 24, 48, 48, "$INFO[ListItem.Property(icon)]", INK if focused else INK2),
        # one line: centred beside the icon; with a second line: the two stacked around the middle
        lbl(96, 0, width - 116, height, "font13", INK, "[B]$INFO[ListItem.Label][/B]",
            visible="String.IsEmpty(ListItem.Label2)", extra="<scroll>true</scroll>" if focused else ""),
        lbl(96, height // 2 - 46, width - 116, 50, "font13", INK, "[B]$INFO[ListItem.Label][/B]",
            visible="!String.IsEmpty(ListItem.Label2)", extra="<scroll>true</scroll>" if focused else ""),
        lbl(96, height // 2 + 2, width - 116, 40, "font10", INK3, "$INFO[ListItem.Label2]",
            visible="!String.IsEmpty(ListItem.Label2)"),
    ]
    if focused:
        body.insert(0, img(-6, -6, width + 12, height + 12, "av-r10-ring.png", INK, border=10,
                           visible=f"Control.HasFocus({cid})"))
        return group(PAD, 16, width, height, "\n".join(body), extra=zoom_when(f"Control.HasFocus({cid})", 104, "auto"))
    return group(PAD, 16, width, height, "\n".join(body))


def backdrop(texture):
    """A full-screen picture under the page's shades (Search page, phone QR screen)."""
    return lines(
        img(0, 0, 1920, 1080, texture, extra="<aspectratio>scale</aspectratio><fadetime>400</fadetime>").replace(
            "<texture>", '<texture background="true">'),
        img(0, 0, 1920, 1080, "av-white.png", "4005070A"),
        img(0, 0, 1920, 1080, "av-vignette.png"),
        img(0, 0, 1920, 1080, "av-shade-hero.png"))


def genre_tabs():
    """Films / Shows at the top right of the Genres page; the open one white."""
    tabs = []
    for control_id, left, string_id, tab, nav in (
            (411, 1460, 30515, "movie", _nav(left=100, right=412, down=401)),
            (412, 1640, 30516, "tv", _nav(left=411, down=401))):
        here = f"String.IsEqual(Window.Property(grid_genre_tab),{tab})"
        tabs.append(group(left, 60, 160, 56, lines(
            img(-5, -5, 170, 66, "av-pill66-ring.png", CYAN, border=33, visible=f"Control.HasFocus({control_id})"),
            img(0, 0, 160, 56, "av-pill56.png", INK, border=28, visible=here),
            img(0, 0, 160, 56, "av-pill56.png", S2, border=28, visible="!" + here),
            f'<control type="button" id="{control_id}"><left>0</left><top>0</top><width>160</width><height>56</height>'
            '<font>font13</font><align>center</align><aligny>center</aligny>'
            f'<textcolor>{INK2}</textcolor><focusedcolor>{INK2}</focusedcolor>'
            '<texturefocus colordiffuse="00FFFFFF">av-white.png</texturefocus>'
            '<texturenofocus colordiffuse="00FFFFFF">av-white.png</texturenofocus>'
            f"<label></label>{nav}</control>",
            lbl(0, 0, 160, 56, "font13", GROUND, f"[B]{_addon(string_id)}[/B]", align="center", visible=here),
            lbl(0, 0, 160, 56, "font13", INK2, f"[B]{_addon(string_id)}[/B]", align="center", visible="!" + here)),
            extra=zoom_when(f"Control.HasFocus({control_id})", 105, "80,28")))
    return group(0, 0, 1920, 140, "\n".join(tabs), visible=GENRES_SHOWN)


def grid():
    peek_on = "!String.IsEmpty(Window.Property(grid_peek))"
    cw, ch = 180, 270
    tiles_on = "!String.IsEmpty(Window.Property(grid_panel))"
    # title pages: two rows of posters under the peek (a panel scrolls only past its last row)
    panel = lines(
        f'<control type="panel" id="400"><left>{X - PAD}</left><top>440</top><width>{1920 - X + PAD}</width><height>612</height>',
        '<orientation>vertical</orientation><scrolltime tween="quadratic" easing="out">200</scrolltime>',
        "<onleft>100</onleft>",
        f'<itemlayout width="{cw + 22}" height="{ch + 36}">', poster_card(cw, ch, False, cid=400), "</itemlayout>",
        f'<focusedlayout width="{cw + 22}" height="{ch + 36}">', poster_card(cw, ch, True, cid=400), "</focusedlayout>",
        f"{_visible(neg(tiles_on))}</control>")
    # tile pages (Search, Genres, My TorBox): the full height under the heading, 150 to 1050
    gw, gh = 400, 152
    tiles = lines(
        f'<control type="panel" id="401"><left>{X - PAD}</left><top>150</top><width>{1920 - X + PAD}</width><height>900</height>',
        '<orientation>vertical</orientation><scrolltime tween="quadratic" easing="out">200</scrolltime>',
        f'<onleft>100</onleft><onup condition="{GENRES_SHOWN}">411</onup>',
        # Genres: four picture tiles across, five rows of 180 px
        f'<itemlayout width="{gw + 22}" height="180" condition="{GENRES_SHOWN}">', genre_card(gw, gh, False, cid=401),
        "</itemlayout>",
        f'<focusedlayout width="{gw + 22}" height="180" condition="{GENRES_SHOWN}">', genre_card(gw, gh, True, cid=401),
        "</focusedlayout>",
        # Search: four wide tiles across, six rows of 150 px
        f'<itemlayout width="422" height="150" condition="{WIDE_TILES}">', wide_tile(400, 120, False, cid=401),
        "</itemlayout>",
        f'<focusedlayout width="422" height="150" condition="{WIDE_TILES}">', wide_tile(400, 120, True, cid=401),
        "</focusedlayout>",
        # My TorBox and other tiles: posters, three rows of 300 px
        f'<itemlayout width="{cw + 22}" height="300">', poster_card(cw, ch, False, cid=401), "</itemlayout>",
        f'<focusedlayout width="{cw + 22}" height="300">', poster_card(cw, ch, True, cid=401), "</focusedlayout>",
        f"{_visible(tiles_on)}</control>")
    empty = group(0, 0, 1920, 1080, lines(
        img(902, 330, 116, 116, "av-dot.png", S2),
        img(934, 362, 52, 52, "$INFO[Window.Property(grid_empty_icon)]", INK3),
        lbl(X, 480, 1920 - 2 * X, 90, "font52_title", INK, "$INFO[Window.Property(grid_empty)]", align="center"),
        f'<control type="textbox"><left>480</left><top>578</top><width>960</width><height>80</height>'
        f'<font>font13</font><textcolor>{INK2}</textcolor><align>center</align>'
        '<label>$INFO[Window.Property(grid_empty_hint)]</label></control>',
        group(0, 0, 1920, 1080, pill_button(410, 790, 680, 340, "$INFO[Window.Property(grid_empty_action)]", True,
                                            _nav(left=100)),
              visible="!String.IsEmpty(Window.Property(grid_empty_action))"),
    ), visible="!String.IsEmpty(Window.Property(grid_empty))")
    skeleton = lines(*[img(X + i * 202, 534, cw, ch, "av-r10.png", S2, border=10, extra=PULSE) for i in range(8)])
    return lines(
        group(0, 0, 1920, 1080, backdrop(SEARCH_ART), visible=WIDE_TILES),
        group(0, 0, 1920, 1080, peek(400), visible=peek_on + " + Integer.IsGreater(Container(400).NumItems,0)"),
        lbl(X, 52, 1500, 64, "font45_title", INK, "$INFO[Window.Property(grid_title)]"),
        genre_tabs(),
        panel,
        tiles,
        empty,
        group(0, 0, 1920, 1080, skeleton, visible="!String.IsEmpty(Window.Property(loading)) + "
                                                  "!Integer.IsGreater(Container(400).NumItems,0)"),
    )


def related():
    """More like this: the focused row's title in the peek, a collection row of wide cards, then posters."""
    rows_ids = (800, 810, 820, 830, 840, 850)
    peeks = [group(0, 0, 1920, 1080, peek(rid, top=140), visible=f"Control.HasFocus({rid})") for rid in rows_ids]
    rows = []
    for n, rid in enumerate(rows_ids):
        kind = "wide" if n == 0 else "poster"
        moves = {"left": 100}
        if n > 0:
            moves["up"] = rows_ids[n - 1]
        if n < len(rows_ids) - 1:
            moves["down"] = rows_ids[n + 1]
        rows.append(group(0, 0, 1920, 380, lines(
            lbl(X, 0, 1200, 44, "font30_title", INK2, f"$INFO[Window.Property(rel{n}_title)]"),
            card_list(rid, X - PAD, 44, 1920 - X + PAD, kind, _nav(**moves))),
            visible=f"Integer.IsGreater(Container({rid}).NumItems,0)"))
    return lines(
        "\n".join(peeks),
        lbl(X, 52, 1500, 64, "font45_title", INK, "$INFO[Window.Property(related_title)]"),
        lbl(X, 116, 1500, 36, "font12", INK3, "$INFO[Window.Property(related_notice)]"),
        lbl(X, 480, 1920 - 2 * X, 60, "font13", INK2, "$INFO[Window.Property(related_status)]", align="center",
            visible="!String.IsEmpty(Window.Property(related_status))"),
        '<control type="grouplist"><left>0</left><top>500</top><width>1920</width><height>580</height>'
        '<orientation>vertical</orientation><itemgap>0</itemgap><scrolltime tween="quadratic" easing="out">260</scrolltime>',
        "\n".join(rows),
        "</control>",
    )


# -- Title page (novaflix-show.xml) -----------------------------------------------------------------

def row_button(control_id, width, label, primary, visible=None):
    """A pill button for a grouplist row: fill and focus ring are one full-colour texture each."""
    name = "primary" if primary else "secondary"
    text = GROUND if primary else INK
    return (f'<control type="button" id="{control_id}"><width>{width}</width><height>78</height>'
            f'<font>font30_title</font><align>center</align><aligny>center</aligny>'
            f'<textcolor>{text}</textcolor><focusedcolor>{text}</focusedcolor>'
            f'<texturefocus border="39">av-btn-{name}-focus.png</texturefocus>'
            f'<texturenofocus border="39">av-btn-{name}.png</texturenofocus>'
            f'<label>{label}</label>'
            '<animation effect="zoom" start="100" end="105" time="150" center="auto">Focus</animation>'
            f"{_visible(visible)}</control>")


TITLE_FIELDS = [(_addon(30510), "rating", 110), (_addon(30511), "year", 100),
                ("$INFO[Window.Property(length_label)]", "length", 170), (_addon(30513), "genres", 420)]


def show():
    logo = "!String.IsEmpty(Window.Property(logo))"
    avail = [img(X, 683, 10, 10, "av-dot.png", colour, visible=f"String.IsEqual(Window.Property(avail),{state})")
             for state, colour in AVAIL_DOTS]
    skeleton = lines(*[img(l, t, w, h, "av-r10.png", S2, border=10, extra=PULSE) for l, t, w, h in (
        (X, 130, 200, 24), (X, 174, 600, 110), (X, 330, 460, 56), (X, 414, 660, 22), (X, 450, 560, 22),
        (X, 560, 300, 66), (X + 320, 560, 260, 66), (X, 760, 380, 214), (X + 400, 760, 380, 214),
        (X + 800, 760, 380, 214), (X + 1200, 760, 380, 214))])
    return lines(
        img(0, 0, 1920, 1080, "av-white.png", GROUND),
        img(0, 0, 1920, 1080, "$INFO[Window.Property(art)]",
            extra="<aspectratio>scale</aspectratio><fadetime>300</fadetime>").replace(
            "<texture>", '<texture background="true">'),
        img(0, 0, 1920, 1080, "av-white.png", "B305070A", visible="!String.IsEmpty(Window.Property(dark))"),
        img(0, 0, 1920, 1080, "av-vignette.png"),
        img(0, 0, 1920, 1080, "av-shade-hero.png"),
        img(0, 0, 1920, 1080, "av-shade-bottom.png"),
        group(0, 0, 1920, 1080, lines(
            lbl(X, 120, 1500, 36, "font12", CYAN_HI,
                "[B]$INFO[Window.Property(kind)][/B]$INFO[Window.Property(alt),   [COLOR " + INK2 + "],[/COLOR]]"
                "$INFO[Window.Property(dub),   [COLOR " + WARN + "],[/COLOR]]"),
            img(X, 160, 760, 140, "$INFO[Window.Property(logo)]", visible=logo,
                extra='<aspectratio align="left" aligny="bottom">keep</aspectratio><fadetime>300</fadetime>').replace(
                "<texture>", '<texture background="true">'),
            lbl(X, 160, 1300, 140, "font52_title", INK, "$INFO[Window.Property(title)]", aligny="bottom",
                visible=neg(logo)),
            labelled_fields(320, TITLE_FIELDS),
            f'<control type="textbox"><left>{X}</left><top>400</top><width>660</width><height>102</height>'
            f'<font>font12</font><textcolor>{INK2}</textcolor><label>$INFO[Window.Property(plot)]</label></control>',
            f'<control type="grouplist"><left>{X - 6}</left><top>554</top><width>1650</width><height>78</height>'
            '<orientation>horizontal</orientation><itemgap>8</itemgap><ondown>510</ondown>',
            row_button(500, 420, "$INFO[Window.Property(play_label)]", True),
            row_button(503, 260, "$INFO[Window.Property(season_label)]", False,
                       visible="!String.IsEmpty(Window.Property(season_label))"),
            row_button(501, 400, "$INFO[Window.Property(favourite_label)]", False),
            row_button(502, 330, "$INFO[Window.Property(related_label)]", False,
                       visible="!String.IsEmpty(Window.Property(has_related))"),
            "</control>",
            "\n".join(avail),
            lbl(X + 22, 670, 1500, 36, "font12", INK2, "$INFO[Window.Property(avail_line)]"),
            lbl(X, 716, 1200, 44, "font30_title", INK2, "$INFO[Window.Property(episodes_title)]"),
            lbl(X, 770, 1500, 44, "font13", INK3, "$INFO[Window.Property(no_episodes)]"),
            lines(
                f'<control type="list" id="510"><left>{X - PAD}</left><top>758</top><width>{1920 - X + PAD}</width>'
                '<height>250</height><orientation>horizontal</orientation><onup>500</onup>'
                '<scrolltime tween="quadratic" easing="out">200</scrolltime>',
                '<itemlayout width="400" height="250">', wide_card(380, 214, False, episode=True, cid=510), "</itemlayout>",
                '<focusedlayout width="400" height="250">', wide_card(380, 214, True, episode=True, cid=510), "</focusedlayout>",
                "</control>"),
        ), visible="!String.IsEmpty(Window.Property(title))"),
        # first load: the page's shapes; a season switch only shows the spinner
        group(0, 0, 1920, 1080, skeleton, visible="String.IsEmpty(Window.Property(title))"),
        loading(),
    )


# -- Source picker (novaflix-sources.xml) -----------------------------------------------------------

STATUS_COLOURS = (("ready", OK), ("download", WARN), ("blocked", BAD), ("unchecked", INK3))


def _source_row(focused):
    width, height = 900, 100  # drawn 6 px in from the list's edges, so the focus ring is not cut
    tabs = "String.IsEqual(ListItem.Property(kind),tabs)"
    action = "String.IsEqual(ListItem.Property(status),action)"
    source = f"!{action}"
    plain_action = f"{action} + !{tabs}"
    is_4k = "String.IsEqual(ListItem.Property(badge),4K)"
    has_badge = "!String.IsEmpty(ListItem.Property(badge))"
    body = [
        img(0, 4, width, height - 8, "av-r10.png", S3 if focused else S2, border=10, visible=f"!{tabs}"),
        img(0, 4, width, height - 8, "av-r10.png", S2, border=10, visible=tabs) if focused else "",
        # tab rows (language, quality): a grey title, then one chip per tab with the open one in white
        lbl(20, 4, 140, height - 8, "font12", INK3, "$INFO[ListItem.Label]", visible=tabs),
    ]
    # chips: the open tab white; on the focused row a cyan ring marks the chip Left / Right is on.
    # Language rows (few tabs, long counts) get three wide chips, Quality rows six narrow ones.
    for wide, count, chip_w in ((True, 3, 170), (False, 6, 114)):
        size = "!String.IsEmpty(ListItem.Property(chip_wide))" if wide else "String.IsEmpty(ListItem.Property(chip_wide))"
        for n in range(count):
            chip = f"ListItem.Property(chip{n})"
            shown = f"{tabs} + {size} + !String.IsEmpty({chip})"
            is_open = f"String.IsEqual(ListItem.Property(chip_open),{n})"
            left = 160 + n * (chip_w + 8)
            if focused:
                body.append(img(left - 5, 23, chip_w + 10, 54, "av-pill54-ring.png", CYAN, border=27,
                                visible=f"{shown} + String.IsEqual(ListItem.Property(chip_focus),{n})"))
            body += [img(left, 28, chip_w, 44, "av-pill44.png", INK, border=22, visible=f"{shown} + {is_open}"),
                     img(left, 28, chip_w, 44, "av-pill44.png", S3 if focused else S2, border=22,
                         visible=f"{shown} + !{is_open}"),
                     lbl(left, 28, chip_w, 44, "font10", GROUND, f"[B]$INFO[{chip}][/B]", align="center",
                         visible=f"{shown} + {is_open}"),
                     lbl(left, 28, chip_w, 44, "font10", INK2, f"[B]$INFO[{chip}][/B]", align="center",
                         visible=f"{shown} + !{is_open}")]
    body += [
        # other actions (check more sources, sort): a plain row of words
        lbl(28, 4, width - 56, height - 8, "font13", INK if focused else INK2, "[B]$INFO[ListItem.Label][/B]",
            visible=plain_action),
        # sources: quality chip, name, details, and the status in its colour on the right
        img(24, 28, 90, 44, "av-r10.png", "2E00A6D6", border=10, visible=f"{source} + {is_4k}"),
        img(24, 28, 90, 44, "av-r10.png", S3 if not focused else "26FFFFFF", border=10,
            visible=f"{source} + {has_badge} + !{is_4k}"),
        lbl(24, 28, 90, 44, "font12", CYAN_HI, "[B]$INFO[ListItem.Property(badge)][/B]", align="center",
            visible=f"{source} + {is_4k}"),
        lbl(24, 28, 90, 44, "font12", INK, "[B]$INFO[ListItem.Property(badge)][/B]", align="center",
            visible=f"{source} + {has_badge} + !{is_4k}"),
        group(0, 0, width, height, lines(
            lbl(136, 14, width - 160, 42, "font13", INK, "$INFO[ListItem.Label]",
                extra="<scroll>true</scroll>" if focused else ""),
            lbl(136, 56, width - 380, 32, "font12", INK3, "$INFO[ListItem.Property(details)]")), visible=source),
    ]
    for state, colour in STATUS_COLOURS:
        here = f"{source} + String.IsEqual(ListItem.Property(status),{state})"
        body += [img(width - 232, 67, 10, 10, "av-dot.png", colour, visible=here),
                 lbl(width - 214, 52, 190, 40, "font12", colour, "[B]$INFO[ListItem.Property(note)][/B]",
                     visible=here)]
    if focused:
        body.insert(2, img(-3, 1, width + 6, height - 2, "av-r10-ring.png", CYAN, border=10))
    return group(6, 0, width, height, "\n".join(b for b in body if b))


def sources():
    return lines(
        img(0, 0, 1920, 1080, "av-white.png", GROUND),
        img(0, 0, 1920, 1080, "$INFO[Window.Property(art)]",
            extra="<aspectratio>scale</aspectratio>").replace("<texture>", '<texture background="true">'),
        img(0, 0, 1920, 1080, "av-white.png", "7305070A"),  # the picture shows, as in the concept
        img(0, 0, 1920, 1080, "av-shade-bottom.png"),
        lbl(120, 780, 700, 40, "font12", CYAN_HI, f"[B]{_addon(30219)}[/B]",
            visible="!String.IsEmpty(Window.Property(title))"),
        lbl(120, 820, 740, 120, "font52_title", INK, "$INFO[Window.Property(title)]", aligny="bottom"),
        lbl(120, 944, 740, 40, "font12", INK2, "$INFO[Window.Property(meta)]"),
        '<!-- the list is a drawer from the right -->',
        img(880, 0, 1040, 1080, "av-white.png", S1,
            extra='<animation effect="slide" start="300,0" end="0,0" time="250" tween="cubic" easing="out">WindowOpen</animation>'),
        group(0, 0, 1920, 160, lines(
            lbl(944, 44, 912, 64, "font45_title", INK, "$INFO[Window.Property(count)]"),
            lbl(944, 106, 912, 40, "font12", INK3, "$INFO[Window.Property(sub)]")),
            visible="!String.IsEmpty(Window.Property(count))"),
        f'<control type="textbox"><left>944</left><top>48</top><width>912</width><height>100</height>'
        f'<font>font30_title</font><textcolor>{INK}</textcolor><label>$INFO[Window.Property(heading)]</label>'
        '<visible>String.IsEmpty(Window.Property(count))</visible></control>',
        '<control type="list" id="600"><left>944</left><top>164</top><width>912</width><height>842</height>'
        '<orientation>vertical</orientation><scrolltime tween="quadratic" easing="out">160</scrolltime>'
        '<onleft>600</onleft><onright>600</onright>'
        '<animation effect="slide" start="300,0" end="0,0" time="250" tween="cubic" easing="out">WindowOpen</animation>',
        '<itemlayout width="912" height="108">', _source_row(False), "</itemlayout>",
        '<focusedlayout width="912" height="108">', _source_row(True), "</focusedlayout>",
        "</control>",
        lbl(944, 1012, 912, 40, "font12", INK3, _addon(30525), align="right"),
    )


# -- Dialogs -------------------------------------------------------------------------------------------

def _dialog_panel(top, height):
    """The dimmed screen and one 860 px panel in the middle."""
    return lines(img(0, 0, 1920, 1080, "av-white.png", "CC000000"),
                 img(530, top, 860, height, "av-r22.png", S1, border=22))


def confirm():
    single = "!String.IsEmpty(Window.Property(single))"
    return lines(
        _dialog_panel(330, 420),
        lbl(582, 372, 760, 36, "font12", CYAN_HI, "[B]$INFO[Window.Property(heading)][/B]"),
        f'<control type="textbox"><left>582</left><top>418</top><width>760</width><height>150</height>'
        f'<font>font30_title</font><textcolor>{INK}</textcolor><label>$INFO[Window.Property(message)]</label></control>',
        f'<control type="textbox"><left>582</left><top>572</top><width>760</width><height>60</height>'
        f'<font>font12</font><textcolor>{INK3}</textcolor><label>$INFO[Window.Property(note)]</label></control>',
        '<control type="grouplist"><left>576</left><top>644</top><width>800</width><height>78</height>'
        '<orientation>horizontal</orientation><itemgap>8</itemgap>',
        row_button(700, 340, "$INFO[Window.Property(yes)]", True).replace(
            "</label>", "</label><onleft>701</onleft><onright>701</onright>", 1),
        row_button(701, 260, "$INFO[Window.Property(no)]", False, visible=neg(single)).replace(
            "</label>", "</label><onleft>700</onleft><onright>700</onright>", 1),
        "</control>",
        lbl(0, 1000, 1920, 40, "font12", INK3, _addon(30525), align="center"),
    )


def _menu_row(focused):
    body = [img(0, 3, 760, 60, "av-r10.png", INK if focused else S2, border=10)]
    if focused:
        body = [img(0, 3, 760, 60, "av-r10.png", S2, border=10, visible="!Control.HasFocus(720)"),
                img(0, 3, 760, 60, "av-r10.png", INK, border=10, visible="Control.HasFocus(720)"),
                lbl(26, 3, 708, 60, "font13", GROUND, "[B]$INFO[ListItem.Label][/B]", visible="Control.HasFocus(720)",
                    extra="<scroll>true</scroll>"),
                lbl(26, 3, 708, 60, "font13", INK2, "[B]$INFO[ListItem.Label][/B]", visible="!Control.HasFocus(720)")]
    else:
        body.append(lbl(26, 3, 708, 60, "font13", INK2, "[B]$INFO[ListItem.Label][/B]"))
    return "\n".join(body)


def menu():
    """Hold-OK menu, resume choice, Settings, sort and filters, pick a file, stalled download."""
    return lines(
        _dialog_panel(220, 640),
        f'<control type="textbox"><left>582</left><top>262</top><width>760</width><height>96</height>'
        f'<font>font30_title</font><textcolor>{INK}</textcolor><label>$INFO[Window.Property(heading)]</label></control>',
        '<control type="list" id="720"><left>580</left><top>370</top><width>760</width><height>462</height>'
        '<orientation>vertical</orientation><onleft>720</onleft><onright>720</onright>'
        '<scrolltime tween="quadratic" easing="out">140</scrolltime>',
        '<itemlayout height="66" width="760">', _menu_row(False), "</itemlayout>",
        '<focusedlayout height="66" width="760">', _menu_row(True), "</focusedlayout>",
        "</control>",
        lbl(0, 1000, 1920, 40, "font12", INK3, _addon(30525), align="center"),
    )


def progress():
    art = "!String.IsEmpty(Window.Property(art))"
    stats = []
    for key, string_id, width in (("speed", 30522, 190), ("seeders", 30523, 150), ("size", 30524, 360)):
        info = f"Window.Property(stat_{key})"
        stats.append(group(0, 0, width, 64, lines(
            lbl(0, 0, width, 24, "font10", INK3, _addon(string_id), aligny="top"),
            lbl(0, 26, width, 38, "font12", INK2, f"$INFO[{info}]", aligny="top")), visible=f"!String.IsEmpty({info})"))
    return lines(
        _dialog_panel(270, 540),
        img(582, 318, 220, 124, "$INFO[Window.Property(art)]", visible=art,
            extra="<aspectratio>scale</aspectratio>").replace("<texture>", '<texture diffuse="av-mask-wide10.png" background="true">'),
        group(0, 0, 1920, 1080, lines(
            lbl(830, 330, 512, 64, "font45_title", INK, "$INFO[Window.Property(title)]"),
            lbl(830, 394, 512, 40, "font12", INK2, "$INFO[Window.Property(message)]")), visible=art),
        group(0, 0, 1920, 1080, lines(
            lbl(582, 330, 760, 64, "font45_title", INK, "$INFO[Window.Property(heading)]"),
            lbl(582, 394, 760, 40, "font12", INK2, "$INFO[Window.Property(message)]")), visible=neg(art)),
        lbl(582, 470, 400, 80, "font52_title", INK, "$INFO[Window.Property(percent)]"),
        lbl(940, 486, 402, 50, "font12", INK3, "$INFO[Window.Property(stat_left)]", align="right"),
        '<control type="progress" id="710"><left>582</left><top>560</top><width>760</width><height>8</height>'
        f'<texturebg border="3" colordiffuse="{S3}">av-bar.png</texturebg>'
        f'<midtexture border="3" colordiffuse="{CYAN}">av-bar.png</midtexture></control>',
        '<control type="grouplist"><left>582</left><top>590</top><width>760</width><height>64</height>'
        '<orientation>horizontal</orientation><itemgap>34</itemgap><usecontrolwidth>true</usecontrolwidth>',
        "\n".join(stats), "</control>",
        '<control type="grouplist"><left>576</left><top>690</top><width>400</width><height>78</height>'
        '<orientation>horizontal</orientation>',
        row_button(711, 240, "$INFO[Window.Property(cancel)]", False),
        "</control>",
        lbl(0, 1000, 1920, 40, "font12", INK3, _addon(30526), align="center"),
    )


# -- Over the video and the phone QR screen --------------------------------------------------------

def _placed(button_xml, left, top):
    return button_xml.replace("<width>", f"<left>{left}</left><top>{top}</top><width>", 1)


def prompt():
    """Up next (text and two buttons, bottom right over a shade) or a lone Skip pill at the top right."""
    two = "!String.IsEmpty(Window.Property(button2))"
    skip_only = "String.IsEmpty(Window.Property(button2)) + String.IsEmpty(Window.Property(text))"
    main = _placed(row_button(9000, 320, "$INFO[Window.Property(button)]", True), 1504, 930).replace(
        "</label>", "</label><onleft>9001</onleft>", 1).replace(
        "</control>", '<animation effect="slide" start="0,0" end="0,-858" time="0" condition="'
        + skip_only + '">Conditional</animation></control>', 1)
    second = _placed(row_button(9001, 300, "$INFO[Window.Property(button2)]", False, visible=two), 1196, 930).replace(
        "</label>", "</label><onright>9000</onright>", 1)
    return lines(
        img(0, 560, 1920, 520, "av-shade-bottom.png", visible="!String.IsEmpty(Window.Property(text))"),
        lbl(1196, 850, 628, 60, "font30_title", INK, "$INFO[Window.Property(text)]", align="right",
            visible="!String.IsEmpty(Window.Property(text))"),
        second,
        main,
    )


def login():
    """Phone search: the steps, the address and the QR code on a white card."""
    return lines(
        img(0, 0, 1920, 1080, "av-white.png", GROUND),
        backdrop(SEARCH_ART),
        lbl(X, 150, 900, 40, "font12", CYAN_HI, f"[B]{_addon(30002)}[/B]"),
        lbl(X, 190, 960, 100, "font52_title", INK, "$INFO[Window.Property(heading)]"),
        f'<control type="textbox"><left>{X}</left><top>300</top><width>800</width><height>160</height>'
        f'<font>font13</font><textcolor>{INK2}</textcolor><label>$INFO[Window.Property(text)]</label></control>',
        lbl(X, 478, 800, 30, "font10", INK3, _addon(30527), visible="!String.IsEmpty(Window.Property(url))"),
        lbl(X, 508, 960, 64, "font30_title", INK, "$INFO[Window.Property(url)]"),
        lbl(X, 574, 900, 44, "font13", INK2, "$INFO[Window.Property(code)]"),
        img(X, 645, 12, 12, "av-dot.png", CYAN, visible="!String.IsEmpty(Window.Property(status))"),
        lbl(X + 24, 630, 900, 42, "font12", INK2, "$INFO[Window.Property(status)]"),
        _placed(row_button(9000, 300, _addon(30122), False), X - 6, 700),
        img(1240, 200, 460, 460, "av-r22.png", INK, border=22),
        img(1270, 230, 400, 400, "$INFO[Window.Property(qr)]", extra="<aspectratio>keep</aspectratio>"),
    )


def loading():
    """The small spinner while something loads (grid pages, the next page of a grid)."""
    return group(1600, 990, 280, 60, lines(
        img(0, 17, 26, 26, "av-spinner.png", CYAN, extra=SPIN),
        lbl(40, 0, 240, 60, "font12", INK3, _addon(30514))),
        visible="!String.IsEmpty(Window.Property(loading))")


# -- splicing ----------------------------------------------------------------------------------------

SECTIONS = {
    ("novaflix-app.xml", "sidebar"): sidebar,
    ("novaflix-app.xml", "push-home"): menu_push,
    ("novaflix-app.xml", "home"): home,
    ("novaflix-app.xml", "push-grid"): menu_push,
    ("novaflix-app.xml", "grid"): grid,
    ("novaflix-app.xml", "loading"): loading,
    ("novaflix-show.xml", "show"): show,
    ("novaflix-sources.xml", "sources"): sources,
    ("novaflix-confirm.xml", "confirm"): confirm,
    ("novaflix-menu.xml", "menu"): menu,
    ("novaflix-progress.xml", "progress"): progress,
    ("novaflix-prompt.xml", "prompt"): prompt,
    ("novaflix-login.xml", "login"): login,
    ("novaflix-app.xml", "push-related"): menu_push,
    ("novaflix-app.xml", "related"): related,
}


def _pattern(name):
    return re.compile(r"(<!-- gen:%s -->)(.*?)(\n[ \t]*<!-- /gen:%s -->)" % (re.escape(name), re.escape(name)), re.S)


def render(path_name):
    path = os.path.join(LAYOUTS, path_name)
    text = open(path, encoding="utf-8").read()
    for (file_name, name), build in SECTIONS.items():
        if file_name != path_name:
            continue
        pattern = _pattern(name)
        if not pattern.search(text):
            raise ValueError(f"{path_name}: no <!-- gen:{name} --> marker")
        text = pattern.sub(lambda m: m.group(1) + "\n" + build() + m.group(3), text, count=1)
    return text


def stale():
    files = sorted({f for f, _ in SECTIONS})
    return [f for f in files if render(f) != open(os.path.join(LAYOUTS, f), encoding="utf-8").read()]


def main():
    for path_name in sorted({f for f, _ in SECTIONS}):
        text = render(path_name)  # read before the file is opened for writing
        with open(os.path.join(LAYOUTS, path_name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print("layouts written")


if __name__ == "__main__":
    main()
