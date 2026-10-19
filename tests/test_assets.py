# tests/test_assets.py
"""M12: generated images exist with the sizes the layouts assume (no Pillow needed here)."""

import os
import struct

import pytest

MEDIA = os.path.join(os.path.dirname(__file__), "..", "plugin.video.aniverse", "resources", "skins", "Default", "media")
ICONS = ["home", "search", "play_circle", "format_list_bulleted", "star", "schedule", "calendar_month",
         "trending_up", "local_fire_department", "auto_awesome", "grid_view", "inventory_2", "settings",
         "play_arrow", "info", "check_circle", "favorite", "chevron_right", "history", "add_link", "folder", "movie",
         "explore", "expand_more", "expand_less",
         "visibility", "bookmark", "pause_circle", "cancel"]
SHAPES = {"av-white.png": (8, 8), "av-round.png": (64, 64), "av-round-border.png": (64, 64), "av-glow.png": (128, 128),
          "av-gradient.png": (256, 64), "av-fade-left.png": (512, 8), "av-fade-bottom.png": (8, 256),
          "av-mask-poster.png": (230, 345), "av-mask-wide.png": (320, 180), "av-pill.png": (64, 32),
          "av-progress.png": (32, 8), "av-divider.png": (8, 512), "av-dot.png": (16, 16),
          "av-placeholder.png": (230, 345), "av-logo.png": (280, 280), "av-accent.png": (8, 256)}


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", head[16:24])


@pytest.mark.parametrize("name,size", sorted(SHAPES.items()))
def test_shapes_exist_with_expected_size(name, size):
    assert png_size(os.path.join(MEDIA, name)) == size


@pytest.mark.parametrize("name", ICONS)
def test_icons_exist(name):
    assert png_size(os.path.join(MEDIA, f"av-icon-{name}.png")) == (64, 64)


def test_addon_icon_is_square_512():
    assert png_size(os.path.join(MEDIA, "..", "..", "..", "..", "aniverse-icon.png")) == (512, 512)


def test_icon_licence_shipped():
    text = open(os.path.join(MEDIA, "LICENSE-material-symbols.txt"), encoding="utf-8").read()
    assert "Apache License" in text


@pytest.mark.parametrize("path", [os.path.join(MEDIA, "av-logo.png"),
                                  os.path.join(MEDIA, "..", "..", "..", "..", "aniverse-icon.png")])
def test_logo_is_only_what_is_inside_the_frame(path):
    # Owner: use only what is inside the neon outline — no dark background around it.
    image = pytest.importorskip("PIL.Image").open(path).convert("RGBA")
    w, h = image.size
    assert image.getpixel((2, 2))[3] == 0 and image.getpixel((w - 3, h - 3))[3] == 0
    assert image.getpixel((w // 2, h // 2))[3] == 255


@pytest.mark.parametrize("addon", ["plugin.video.aniverse", "repository.aniverse"])
def test_addon_icons_use_the_new_logo_under_a_new_name(addon):
    # Kodi caches icons by path for about a day; a new file name shows the new logo at once.
    import xml.etree.ElementTree as ET
    base = os.path.join(os.path.dirname(__file__), "..", addon)
    icon = ET.parse(os.path.join(base, "addon.xml")).getroot().find(".//assets/icon").text
    assert icon == "aniverse-icon.png"
    path = os.path.join(base, icon)
    assert png_size(path) == (512, 512)
    assert open(path, "rb").read() == open(os.path.join(os.path.dirname(__file__), "..", "plugin.video.aniverse",
                                                         "aniverse-icon.png"), "rb").read()


@pytest.mark.parametrize("name", ["aniverse-sources.xml", "aniverse-menu.xml"])
def test_list_popups_do_not_focus_their_empty_list_on_open(name):
    # Python fills the list in onInit and then focuses it; a defaultcontrol logs "can't focus".
    text = open(os.path.join(MEDIA, "..", "1080i", name), encoding="utf-8").read()
    assert "<defaultcontrol" not in text


def test_logo_keeps_the_neon_frame():
    # Owner: keep the border; only the background outside it goes.
    image = pytest.importorskip("PIL.Image").open(os.path.join(MEDIA, "av-logo.png")).convert("RGBA")
    w, h = image.size
    left_edge = [image.getpixel((x, h // 2)) for x in range(0, 12)]
    assert any(p[3] == 255 and max(p[:3]) > 150 for p in left_edge), "bright frame line missing on the left edge"
