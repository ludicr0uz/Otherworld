"""The half outside the editor: light each item's passes and fit it to the icon
canvas. Needs Pillow and numpy, which the editor's embedded Python lacks.

    colour  = base colour x (ambient + sky + key light) + highlight + rim
    then    levelled, so a black gun still reads on the HUD's dark slot;
            cropped to the model, scaled to its share of the canvas (the
            item's `length`), centred, and given a thin pale edge, which is
            what separates a dark model from that slot

The light is fixed in the camera's space (upper left, towards the viewer), so
every icon is lit from the same side whatever view its item is shot from.
Every number that decides the look is a constant below.
"""

import json
import os

import numpy as np
from PIL import Image, ImageFilter

from item_icons.items import ICON_H, ICON_W, ITEMS, icon_name
from item_icons.paths import ICON_DIR, PASSES_DIR, SHEET_PATH
from item_icons.portrait import PORTRAIT, PORTRAIT_H, PORTRAIT_TEXTURE, PORTRAIT_W

KEY_LIGHT = (-0.45, 0.60, 0.66)   # camera space: right, up, towards the viewer
AMBIENT = 0.42
SKY = 0.22                        # extra on faces that look up
KEY = 0.85
HIGHLIGHT = 0.16                  # Blinn-Phong, white
HIGHLIGHT_POWER = 28.0
RIM = 0.10                        # on faces turning away from the viewer
# Levelling: the brightest tenth of the model is brought up to this (never
# down), the hue kept. The FPS bundle's guns are near-black steel, and the
# slot behind an icon is near-black too.
LEVEL_PERCENTILE = 90.0
LEVEL_TO = 0.62
LEVEL_MAX_GAIN = 6.0
# The portrait's: a clothed body brought up to the guns' level washes out,
# and left as captured is lost on the panel's dark.
PORTRAIT_LEVEL_TO = 0.40
FILL = 0.96                       # of the canvas, for an item of length 1
EDGE_PX = 1.0                     # the pale edge, in icon pixels
EDGE_COLOUR = (205, 215, 232)
EDGE_ALPHA = 0.60
SUPERSAMPLE = 4                   # the canvas is built at this and reduced

# What the render must show before it replaces an icon: a real picture of a
# real model, not an empty frame or a flat blob.
MIN_COVERAGE = 0.02               # of the capture, on the model
MIN_SHADES = 24                   # distinct grey levels inside the icon


def _load(folder, name):
    return np.asarray(Image.open(os.path.join(folder, f"{name}.png")).convert("RGBA"),
                      dtype=np.float32) / 255.0


def _to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def _lit(folder, level_to=LEVEL_TO):
    """The model lit and levelled, as straight-alpha float RGBA at the
    capture's size."""
    base = _load(folder, "base")[..., :3]
    world_normal = _load(folder, "normal")[..., :3] * 2.0 - 1.0
    alpha = 1.0 - _load(folder, "mask")[..., 3]
    with open(os.path.join(folder, "view.json")) as fh:
        view = json.load(fh)
    axes = np.array([view["right"], view["up"], [-c for c in view["forward"]]],
                    dtype=np.float32)
    n = world_normal @ axes.T
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-4)

    key = np.array(KEY_LIGHT, dtype=np.float32)
    key /= np.linalg.norm(key)
    half = key + np.array([0.0, 0.0, 1.0], dtype=np.float32)
    half /= np.linalg.norm(half)
    diffuse = np.clip(n @ key, 0.0, 1.0)
    light = AMBIENT + SKY * (n[..., 1] * 0.5 + 0.5) + KEY * diffuse
    shine = HIGHLIGHT * np.power(np.clip(n @ half, 0.0, 1.0), HIGHLIGHT_POWER)
    rim = RIM * np.power(1.0 - np.clip(n[..., 2], 0.0, 1.0), 3.0)
    colour = base * light[..., None] + (shine + rim)[..., None]

    on = alpha > 0.5
    if on.mean() < MIN_COVERAGE:
        raise RuntimeError(f"{folder}: the model covers {on.mean():.1%} of its capture")
    luma = colour @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bright = float(np.percentile(luma[on], LEVEL_PERCENTILE))
    gain = min(LEVEL_MAX_GAIN, max(1.0, level_to / max(bright, 1e-4)))
    return np.dstack([_to_srgb(colour * gain), alpha])


def _fit(rgba, length, fit_to=(ICON_W, ICON_H)):
    """Crop to the model, scale to its share of the canvas, centre, edge."""
    img = Image.fromarray((np.clip(rgba, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), "RGBA")
    img = img.crop(img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
    w, h = fit_to[0] * SUPERSAMPLE, fit_to[1] * SUPERSAMPLE
    scale = min(w * FILL * length / img.width, h * FILL / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    # Reduced with its colour premultiplied, or the capture's black background
    # bleeds into the outline.
    img = img.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((w - size[0]) // 2, (h - size[1]) // 2))

    spread = canvas.getchannel("A").filter(
        ImageFilter.MaxFilter(2 * round(EDGE_PX * SUPERSAMPLE) + 1))
    edge = Image.new("RGBA", (w, h), EDGE_COLOUR + (0,))
    edge.putalpha(spread.point(lambda a: round(a * EDGE_ALPHA)))
    edge.alpha_composite(canvas)
    return edge.convert("RGBa").resize(fit_to, Image.LANCZOS).convert("RGBA")


def _check(display, icon):
    """Raise unless the icon is a shaded picture (see MIN_SHADES)."""
    a = np.asarray(icon.getchannel("A"))
    grey = np.asarray(icon.convert("L"))[a > 200]
    if len(np.unique(grey)) < MIN_SHADES:
        raise RuntimeError(f"{display}: the icon is flat ({len(np.unique(grey))} shades)")


def _sheet(icons):
    """Every icon at 4x on the slot's own dark, to judge the set by eye."""
    zoom, pad = 4, 12
    cell = (ICON_W * zoom + pad, ICON_H * zoom + pad)
    columns = 3
    rows = -(-len(icons) // columns)
    sheet = Image.new("RGBA", (cell[0] * columns + pad, cell[1] * rows + pad), (12, 15, 21, 255))
    for i, icon in enumerate(icons):
        big = icon.resize((ICON_W * zoom, ICON_H * zoom), Image.NEAREST)
        sheet.alpha_composite(big, (pad + cell[0] * (i % columns), pad + cell[1] * (i // columns)))
    sheet.save(SHEET_PATH)


def compose_all(only=()):
    """Write T_UI_Icon_<DisplayName>.png for every captured item, and the
    portrait. Returns the texture names written."""
    os.makedirs(ICON_DIR, exist_ok=True)
    made, icons = [], []
    for item in ITEMS:
        folder = os.path.join(PASSES_DIR, item.display)
        if (only and item.display not in only) or not os.path.isdir(folder):
            continue
        icon = _fit(_lit(folder), item.length)
        _check(item.display, icon)
        icon.save(os.path.join(ICON_DIR, f"{icon_name(item.display)}.png"))
        made.append(icon_name(item.display))
        icons.append(icon)
    if icons:
        _sheet(icons)
    # The character's portrait: the same light, on its own taller canvas.
    folder = os.path.join(PASSES_DIR, PORTRAIT)
    if (not only or PORTRAIT in only) and os.path.isdir(folder):
        portrait = _fit(_lit(folder, PORTRAIT_LEVEL_TO), 1.0, (PORTRAIT_W, PORTRAIT_H))
        _check(PORTRAIT, portrait)
        portrait.save(os.path.join(ICON_DIR, f"{PORTRAIT_TEXTURE}.png"))
        made.append(PORTRAIT_TEXTURE)
    return made
