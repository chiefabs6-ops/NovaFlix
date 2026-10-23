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

MENU_OPEN = "ControlGroup(9100).HasFocus"
VIEW_TARGETS = [  # (condition, control) the sidebar and Settings hand focus to on Right
    ("String.IsEqual(Window.Property(view),home) + String.IsEmpty(Window.Property(offline))", 201),
    ("String.IsEqual(Window.Property(view),home) + !String.IsEmpty(Window.Property(offline))", 340),
    ("String.IsEqual(Window.Property(view),grid)", 400),
    ("String.IsEqual(Window.Property(view),related)", 800),
    ("String.IsEqual(Window.Property(view),mal)", 420),
]


# -- XML helpers -----------------------------------------------------------------------------------

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


# -- splicing ----------------------------------------------------------------------------------------

SECTIONS = {
    ("novaflix-app.xml", "sidebar"): sidebar,
    ("novaflix-app.xml", "push-home"): menu_push,
    ("novaflix-app.xml", "push-grid"): menu_push,
    ("novaflix-app.xml", "push-related"): menu_push,
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
