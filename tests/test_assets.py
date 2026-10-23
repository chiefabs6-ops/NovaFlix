# tests/test_assets.py
"""M12: generated images exist with the sizes the layouts assume (no Pillow needed here)."""

import os
import struct

import pytest

MEDIA = os.path.join(os.path.dirname(__file__), "..", "plugin.video.novaflix", "resources", "skins", "Default", "media")
ICONS = ["home", "search", "play_circle", "format_list_bulleted", "star", "schedule", "calendar_month",
         "trending_up", "local_fire_department", "auto_awesome", "grid_view", "inventory_2", "settings",
         "play_arrow", "info", "check_circle", "favorite", "chevron_right", "history", "add_link", "folder", "movie",
         "explore", "expand_more", "expand_less",
         "visibility", "bookmark", "pause_circle", "cancel"]
SHAPES = {"av-white.png": (8, 8), "av-round.png": (64, 64), "av-round-border.png": (64, 64), "av-glow.png": (128, 128),
          "av-gradient.png": (256, 64), "av-fade-left.png": (512, 8), "av-fade-bottom.png": (8, 256),
          "av-mask-poster.png": (230, 345), "av-mask-wide.png": (320, 180), "av-pill.png": (64, 32),
          "av-progress.png": (32, 8), "av-divider.png": (8, 512), "av-dot.png": (16, 16),
          "av-placeholder.png": (230, 345), "av-logo.png": (280, 280), "av-accent.png": (8, 256),
          # Cinematic UI (0.4.0)
          "av-r10.png": (64, 64), "av-r10-ring.png": (64, 64), "av-pill66.png": (132, 66),
          "av-pill66-ring.png": (132, 66), "av-r22.png": (96, 96), "av-shade-hero.png": (1920, 8),
          "av-shade-bottom.png": (8, 512), "av-shade-card.png": (8, 256), "av-shade-menu.png": (1920, 8),
          "av-vignette.png": (480, 270), "av-bar.png": (32, 6),
          "av-mask-wide10.png": (420, 236), "av-mask-poster10.png": (200, 300), "av-spinner.png": (64, 64)}


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


def test_shades_fade_from_ground_to_clear():
    image = pytest.importorskip("PIL.Image").open(os.path.join(MEDIA, "av-shade-hero.png")).convert("RGBA")
    r, g, b, a = image.getpixel((0, 4))
    assert (r, g, b) == (5, 7, 10) and a >= 230
    assert image.getpixel((int(image.width * 0.6), 4))[3] == 0


def test_addon_icon_is_square_512():
    assert png_size(os.path.join(MEDIA, "..", "..", "..", "..", "novaflix-icon.png")) == (512, 512)


def test_icon_licence_shipped():
    text = open(os.path.join(MEDIA, "LICENSE-material-symbols.txt"), encoding="utf-8").read()
    assert "Apache License" in text


@pytest.mark.parametrize("path", [os.path.join(MEDIA, "av-logo.png"),
                                  os.path.join(MEDIA, "..", "..", "..", "..", "novaflix-icon.png")])
def test_logo_is_only_what_is_inside_the_frame(path):
    # Owner: use only what is inside the neon outline — no dark background around it.
    image = pytest.importorskip("PIL.Image").open(path).convert("RGBA")
    w, h = image.size
    assert image.getpixel((2, 2))[3] == 0 and image.getpixel((w - 3, h - 3))[3] == 0
    assert image.getpixel((w // 2, h // 2))[3] == 255


@pytest.mark.parametrize("addon", ["plugin.video.novaflix", "repository.novaflix"])
def test_addon_icons_use_the_new_logo_under_a_new_name(addon):
    # Kodi caches icons by path for about a day; a new file name shows the new logo at once.
    import xml.etree.ElementTree as ET
    base = os.path.join(os.path.dirname(__file__), "..", addon)
    icon = ET.parse(os.path.join(base, "addon.xml")).getroot().find(".//assets/icon").text
    assert icon == "novaflix-icon.png"
    path = os.path.join(base, icon)
    assert png_size(path) == (512, 512)
    assert open(path, "rb").read() == open(os.path.join(os.path.dirname(__file__), "..", "plugin.video.novaflix",
                                                         "novaflix-icon.png"), "rb").read()


@pytest.mark.parametrize("name", ["novaflix-sources.xml", "novaflix-menu.xml"])
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


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(MEDIA, "..", "1080i")
# AniVerse's backgrounds and accents; NovaFlix uses darker ones (owner, 2026-10-19).
OLD_ACCENTS = ["FF050B18", "FF0C1930", "FF132443", "FF1A2747", "FF00CFFF", "FFA855F7", "FF702CFF", "FF087BFF",
               "FF5A8BFF"]


def test_skins_use_the_darker_palette():
    for name in sorted(os.listdir(SKINS)):
        text = open(os.path.join(SKINS, name), encoding="utf-8").read().upper()
        assert [c for c in OLD_ACCENTS if c in text] == [], name


def test_phone_page_uses_the_darker_palette():
    from resources.lib.net import phone_keyboard
    css = (phone_keyboard.PAGE + phone_keyboard.EXPIRED).lower()
    assert [c for c in ("#050b18", "#00cfff", "#a855f7", "#0c1930", "#132443", "#5a6bff") if c in css] == []


def test_fanart_is_1920x1080():
    for addon in ("plugin.video.novaflix", "script.novaflix", "repository.novaflix"):
        assert png_size(os.path.join(ROOT, addon, "fanart.png")) == (1920, 1080)


def test_logo_comes_from_the_novaflix_artwork():
    pytest.importorskip("PIL.Image")
    from tools import make_assets
    assert os.path.basename(make_assets.LOGO_SOURCE) == "novaflix-logo-source.png"
    assert os.path.isfile(make_assets.LOGO_SOURCE)
    assert make_assets.LOGO_INSIDE == (50, 65, 1203, 1187)


def test_launcher_tile_uses_the_same_icon():
    plugin = open(os.path.join(ROOT, "plugin.video.novaflix", "novaflix-icon.png"), "rb").read()
    assert open(os.path.join(ROOT, "script.novaflix", "novaflix-icon.png"), "rb").read() == plugin
