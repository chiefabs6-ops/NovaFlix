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

# Cinematic UI (0.4.0, owner 2026-10-23): near-black ground, cyan the one accent; no purple or blue.
BG = (5, 7, 10)
CYAN = (0, 166, 214)
BLACK = (0, 0, 0)
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


def stops(size, horizontal, colour, points):
    """A one-colour fade whose alpha runs piecewise-linearly through (position 0..1, alpha 0..1) points."""
    w, h = size
    length = w if horizontal else h
    alphas = []
    for i in range(length):
        t = i / (length - 1)
        for (p0, a0), (p1, a1) in zip(points, points[1:]):
            if p0 <= t <= p1:
                alphas.append(a0 + (a1 - a0) * ((t - p0) / (p1 - p0) if p1 > p0 else 0))
                break
        else:
            alphas.append(points[-1][1] if t > points[-1][0] else points[0][1])
    img = Image.new("RGBA", size)
    px = img.load()
    for x in range(w):
        for y in range(h):
            px[x, y] = colour + (round(255 * alphas[x if horizontal else y]),)
    return img


def vignette():
    """Darkens the edges of a hero picture; clear around (78 %, 30 %). Drawn small, scaled by Kodi."""
    w, h = 480, 270
    cx, cy = 0.78 * w, 0.30 * h
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for x in range(w):
        for y in range(h):
            d = (((x - cx) / (1.2 * w)) ** 2 + ((y - cy) / (0.9 * h)) ** 2) ** 0.5 / 0.5
            if d <= 0.35:
                a = 0.0
            elif d <= 0.75:
                a = 0.55 * (d - 0.35) / 0.40
            else:
                a = min(0.85, 0.55 + 0.30 * (d - 0.75) / 0.25)
            px[x, y] = BG + (round(255 * a),)
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


LOGO_INSIDE = (50, 65, 1203, 1187)  # ~8 px outside the neon frame's glow (frame: x 58-1195, y 73-1179)
LOGO_RADIUS = 150                   # the frame's rounded corners; the drawn checkerboard outside goes


def _backdrop(image):
    """Mask of the drawn grey checkerboard reachable from the edges (the source PNG has no
    transparency). Grey = low saturation and light; the neon glow is saturated, so it stops there."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    mask = Image.new("L", (w, h), 0)
    out = mask.load()

    def grey(xy):
        r, g, b = px[xy]
        return max(r, g, b) - min(r, g, b) < 28 and min(r, g, b) > 140

    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        if out[x, y] or not grey((x, y)):
            continue
        out[x, y] = 255
        stack.extend(n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if 0 <= n[0] < w and 0 <= n[1] < h)
    return mask


def logo():
    """Owner: keep the neon frame, drop the background outside it. Everything outside the
    frame's rounded shape and the padding to a square are transparent."""
    inside = Image.open(LOGO_SOURCE).convert("RGBA").crop(LOGO_INSIDE)
    w, h = inside.size
    alpha = rounded((w, h), LOGO_RADIUS).getchannel("A")
    alpha.paste(0, mask=_backdrop(inside))
    inside.putalpha(alpha)
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(inside, ((side - w) // 2, (side - h) // 2))
    square.resize((280, 280), Image.LANCZOS).save(os.path.join(MEDIA, "av-logo.png"), optimize=True)
    icon = square.resize((512, 512), Image.LANCZOS)
    # New file name: Kodi caches icons by path, so the new logo shows without waiting a day.
    for addon in ("plugin.video.novaflix", "script.novaflix", "repository.novaflix"):
        icon.save(os.path.join(ROOT, addon, "novaflix-icon.png"), optimize=True)


def fanart():
    """1920x1080 add-on background: the ground with one soft cyan glow bottom right.
    Drawn small and scaled up, so the glow stays smooth."""
    small = Image.new("RGB", (192, 108), BG)
    layer = Image.new("L", small.size, 0)
    ImageDraw.Draw(layer).ellipse((100, 50, 250, 160), fill=60)
    small = Image.composite(Image.new("RGB", small.size, CYAN), small, layer.filter(ImageFilter.GaussianBlur(28)))
    image = small.resize((1920, 1080), Image.BICUBIC)
    for addon in ("plugin.video.novaflix", "script.novaflix", "repository.novaflix"):
        image.save(os.path.join(ROOT, addon, "fanart.png"), optimize=True)


def main():
    os.makedirs(MEDIA, exist_ok=True)
    save(Image.new("RGBA", (8, 8), WHITE + (255,)), "av-white.png")
    # Cinematic UI
    save(rounded((64, 64), 10), "av-r10.png")
    save(outline((64, 64), 10, 3), "av-r10-ring.png")
    save(rounded((132, 66), 33), "av-pill66.png")
    save(outline((132, 66), 33, 3), "av-pill66-ring.png")
    save(rounded((96, 96), 22), "av-r22.png")
    save(rounded((32, 6), 3), "av-bar.png")
    save(stops((1920, 8), True, BG, [(0, .92), (.28, .70), (.58, 0), (1, 0)]), "av-shade-hero.png")
    save(stops((8, 512), False, BG, [(0, 0), (.38, 0), (.58, .60), (.78, 1), (1, 1)]), "av-shade-bottom.png")
    save(stops((8, 256), False, BLACK, [(0, 0), (.28, 0), (.52, .20), (1, .85)]), "av-shade-card.png")
    save(stops((1920, 8), True, BG, [(0, .98), (.26, .97), (.40, .80), (.64, 0), (1, 0)]), "av-shade-menu.png")
    save(vignette(), "av-vignette.png")
    # Masks drawn at the card's own size, so the 10 px corners stay round (diffuse textures do not take a border)
    save(rounded((420, 236), 10), "av-mask-wide10.png")
    save(rounded((200, 300), 10), "av-mask-poster10.png")
    # Pill buttons for rows of buttons in a grouplist (the ring cannot be a separate image there):
    # the fill inset 6 px, and on focus a 3 px cyan ring at the edge with a 3 px gap.
    for name, fill in (("primary", WHITE + (255,)), ("secondary", WHITE + (36,))):
        for focused in (False, True):
            tex = Image.new("RGBA", (156, 78), (0, 0, 0, 0))
            draw = ImageDraw.Draw(tex)
            draw.rounded_rectangle((6, 6, 149, 71), 33, fill=fill)
            if focused:
                draw.rounded_rectangle((0, 0, 155, 77), 39, outline=CYAN + (255,), width=3)
            save(tex, f"av-btn-{name}{'-focus' if focused else ''}.png")
    spinner = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(spinner).arc((6, 6, 57, 57), 300, 210, fill=WHITE + (255,), width=5)
    save(spinner, "av-spinner.png")
    dot = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse((0, 0, 15, 15), fill=WHITE + (255,))
    save(dot, "av-dot.png")
    icons()
    logo()
    fanart()
    print(f"assets written to {MEDIA}")


if __name__ == "__main__":
    main()
