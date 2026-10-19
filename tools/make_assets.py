# tools/make_assets.py
"""Generate NovaFlix UI images (M12). Developer machine only; the add-on never imports Pillow.

Usage:  .venv\\Scripts\\python tools\\make_assets.py
Colours here are the single source for the PNGs (XML tints white shapes with colordiffuse).
Icons: Material Symbols Rounded (Apache-2.0), downloaded once into tools/.cache.
"""

import os
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "plugin.video.novaflix", "resources", "skins", "Default", "media")
CACHE = os.path.join(ROOT, "tools", ".cache")
LOGO_SOURCE = os.path.join(ROOT, "tools", "source_art", "novaflix-logo-source.png")
FONT_BASE = "https://raw.githubusercontent.com/google/material-design-icons/master/"
FONT_FILE = "variablefont/MaterialSymbolsRounded%5BFILL,GRAD,opsz,wght%5D"
LICENSE_URL = FONT_BASE + "LICENSE"

BG = (5, 11, 24)
PANEL = (12, 25, 48)
PURPLE = (112, 44, 255)
BLUE = (8, 123, 255)
VIOLET = (168, 85, 247)
CYAN = (0, 207, 255)
WHITE = (255, 255, 255)

ICONS = ["home", "search", "play_circle", "format_list_bulleted", "star", "schedule", "calendar_month",
         "trending_up", "local_fire_department", "auto_awesome", "grid_view", "inventory_2", "settings",
         "play_arrow", "info", "check_circle", "favorite", "chevron_right", "history", "add_link", "folder", "movie",
         "explore", "expand_more", "expand_less",
         "visibility", "bookmark", "pause_circle", "cancel", "smartphone"]


def save(img, name):
    img.save(os.path.join(MEDIA, name), optimize=True)


def rounded(size, radius, fill=WHITE + (255,)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=fill)
    return img


def outline(size, radius, width):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, outline=WHITE + (255,), width=width)
    return img


def glow():
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((24, 24, 103, 103), 18, outline=WHITE + (255,), width=6)
    return img.filter(ImageFilter.GaussianBlur(9))


def gradient(size, start, end, radius):
    w, h = size
    img = Image.new("RGBA", size)
    px = img.load()
    for x in range(w):
        t = x / (w - 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(start, end)) + (255,)
        for y in range(h):
            px[x, y] = colour
    mask = rounded(size, radius).getchannel("A")
    img.putalpha(mask)
    return img


def fade(size, horizontal):
    w, h = size
    img = Image.new("RGBA", size)
    px = img.load()
    for x in range(w):
        for y in range(h):
            t = (x / (w - 1)) if horizontal else (1 - y / (h - 1))
            px[x, y] = BG + (round(255 * (1 - t) ** 1.6),)
    return img


def divider():
    img = Image.new("RGBA", (8, 512), (0, 0, 0, 0))
    px = img.load()
    for y in range(512):
        t = y / 511
        colour = tuple(round(a + (b - a) * t) for a, b in zip(VIOLET, CYAN))
        alpha = round(200 * (1 - abs(t - 0.5) * 1.6))
        for x in range(8):
            px[x, y] = colour + (max(alpha - abs(x - 3) * 40, 0),)
    return img


def accent():
    """Slim vertical purple-to-cyan bar beside the open Explore submenu (sidebar redesign)."""
    w, h = 8, 256
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(VIOLET, CYAN)) + (255,)
        for x in range(w):
            px[x, y] = colour
    img.putalpha(rounded((w, h), 4).getchannel("A"))
    return img


def fetch(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def icon_font():
    font_path = fetch(FONT_BASE + FONT_FILE + ".ttf", "MaterialSymbolsRounded.ttf")
    codepoints_path = fetch(FONT_BASE + FONT_FILE + ".codepoints", "MaterialSymbolsRounded.codepoints")
    codepoints = {}
    with open(codepoints_path, encoding="utf-8") as f:
        for line in f:
            name, code = line.split()
            codepoints[name] = chr(int(code, 16))
    font = ImageFont.truetype(font_path, 52)
    font.set_variation_by_axes([0, 0, 48, 400])  # FILL, GRAD, opsz, wght
    return font, codepoints


def icons():
    font, codepoints = icon_font()
    for name in ICONS:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((32, 32), codepoints[name], font=font, fill=WHITE + (255,), anchor="mm")
        save(img, f"av-icon-{name}.png")
    licence = urllib.request.urlopen(LICENSE_URL).read().decode("utf-8")
    with open(os.path.join(MEDIA, "LICENSE-material-symbols.txt"), "w", encoding="utf-8") as f:
        f.write("Icons av-icon-*.png are rendered from Material Symbols Rounded by Google.\n\n" + licence)


def placeholder():
    img = Image.new("RGBA", (230, 345), PANEL + (255,))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((85, 142, 145, 202), 12, outline=(90, 107, 255, 120), width=4)
    return img


LOGO_INSIDE = (252, 37, 1273, 977)  # 10 px outside the neon frame line (line: x 262-1262, y 47-966)
LOGO_RADIUS = 159                   # the frame's own corner radius (~149 px) + the 10 px margin


def logo():
    """Owner: keep the neon frame, drop the background outside it. Everything outside the
    frame's rounded shape and the padding to a square are transparent."""
    inside = Image.open(LOGO_SOURCE).convert("RGBA").crop(LOGO_INSIDE)
    w, h = inside.size
    inside.putalpha(rounded((w, h), LOGO_RADIUS).getchannel("A"))
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(inside, ((side - w) // 2, (side - h) // 2))
    square.resize((280, 280), Image.LANCZOS).save(os.path.join(MEDIA, "av-logo.png"), optimize=True)
    icon = square.resize((512, 512), Image.LANCZOS)
    # New file name: Kodi caches icons by path, so the new logo shows without waiting a day.
    for addon in ("plugin.video.novaflix", "script.novaflix", "repository.novaflix"):
        icon.save(os.path.join(ROOT, addon, "novaflix-icon.png"), optimize=True)


def main():
    os.makedirs(MEDIA, exist_ok=True)
    save(Image.new("RGBA", (8, 8), WHITE + (255,)), "av-white.png")
    save(rounded((64, 64), 16), "av-round.png")
    save(outline((64, 64), 16, 3), "av-round-border.png")
    save(glow(), "av-glow.png")
    save(gradient((256, 64), PURPLE, BLUE, 16), "av-gradient.png")
    save(fade((512, 8), horizontal=True), "av-fade-left.png")
    save(fade((8, 256), horizontal=False), "av-fade-bottom.png")
    save(rounded((230, 345), 14), "av-mask-poster.png")
    save(rounded((320, 180), 14), "av-mask-wide.png")
    save(rounded((64, 32), 16), "av-pill.png")
    save(rounded((32, 8), 4), "av-progress.png")
    save(divider(), "av-divider.png")
    save(accent(), "av-accent.png")
    dot = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse((0, 0, 15, 15), fill=WHITE + (255,))
    save(dot, "av-dot.png")
    save(placeholder(), "av-placeholder.png")
    icons()
    logo()
    print(f"assets written to {MEDIA}")


if __name__ == "__main__":
    main()
