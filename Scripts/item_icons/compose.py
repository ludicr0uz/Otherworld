"""The half outside the editor: fit each item's lit picture to the icon canvas.
Needs Pillow and numpy, which the editor's embedded Python lacks.

    light.py lights the passes (shadows, occlusion, gloss, levelling); then
    the picture is cropped to the model, scaled to its share of the canvas
    (the item's `length`), centred, and given a thin black contour, which is
    what holds the item's shape against whatever the slot is drawn over

Every number that decides the fit and the contour is a constant below; the
light's are light.py's.
"""

import os

import numpy as np
from PIL import Image

from item_icons.items import ICON_H, ICON_W, ITEMS, icon_name
from item_icons.light import lit
from item_icons.paths import ICON_DIR, PASSES_DIR, SHEET_PATH
from item_icons.portrait import PORTRAIT, PORTRAIT_H, PORTRAIT_TEXTURE, PORTRAIT_W

# The portrait's level: a clothed body brought up to the guns' (light.LEVEL_TO)
# washes out, and left as captured is lost on the panel's dark.
PORTRAIT_LEVEL_TO = 0.40
FILL = 0.96                       # of the canvas, for an item of length 1
CONTOUR_PX = 1.0                  # the black contour, in icon pixels
CONTOUR_COLOUR = (0, 0, 0)
CONTOUR_ALPHA = 0.95
SUPERSAMPLE = 4                   # the canvas is built at this and reduced
SHEET_DARK = (12, 15, 21, 255)    # the contact sheet's: the slot's dark,
SHEET_MID = (96, 110, 84, 255)    # and the forest seen through a slot

# What the render must show before it replaces an icon: a shaded picture, not
# a flat blob. (An empty frame is light.py's to refuse.)
MIN_SHADES = 24                   # distinct grey levels inside the icon


def _fit(rgba, length, fit_to=(ICON_W, ICON_H)):
    """Crop to the model, scale to its share of the canvas, centre, contour."""
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

    # The contour: the model's own shape, grown by CONTOUR_PX all round (a
    # disc, so it is as thick on a diagonal as on a straight edge), in black
    # under the model.
    grow = round(CONTOUR_PX * SUPERSAMPLE)
    disc = [(dx, dy) for dx in range(-grow, grow + 1) for dy in range(-grow, grow + 1)
            if dx * dx + dy * dy <= grow * grow + 1]
    shape = np.asarray(canvas.getchannel("A"))
    spread = np.zeros_like(shape)
    for dx, dy in disc:
        spread = np.maximum(spread, np.roll(shape, (dy, dx), axis=(0, 1)))
    contour = Image.new("RGBA", (w, h), CONTOUR_COLOUR + (0,))
    contour.putalpha(Image.fromarray((spread * CONTOUR_ALPHA).astype(np.uint8), "L"))
    contour.alpha_composite(canvas)
    return contour.convert("RGBa").resize(fit_to, Image.LANCZOS).convert("RGBA")


def _check(display, icon):
    """Raise unless the icon is a shaded picture (see MIN_SHADES)."""
    a = np.asarray(icon.getchannel("A"))
    grey = np.asarray(icon.convert("L"))[a > 200]
    if len(np.unique(grey)) < MIN_SHADES:
        raise RuntimeError(f"{display}: the icon is flat ({len(np.unique(grey))} shades)")


def _sheet(icons):
    """Every icon at 4x, to judge the set by eye: its left half on the slot's
    own dark, its right half on a mid tone, where the black contour shows."""
    zoom, pad = 4, 12
    cell = (ICON_W * zoom + pad, ICON_H * zoom + pad)
    columns = 3
    rows = -(-len(icons) // columns)
    sheet = Image.new("RGBA", (cell[0] * columns + pad, cell[1] * rows + pad), SHEET_DARK)
    for i, icon in enumerate(icons):
        at = (pad + cell[0] * (i % columns), pad + cell[1] * (i // columns))
        sheet.paste(SHEET_MID, (at[0] + ICON_W * zoom // 2, at[1],
                                at[0] + ICON_W * zoom, at[1] + ICON_H * zoom))
        sheet.alpha_composite(icon.resize((ICON_W * zoom, ICON_H * zoom), Image.NEAREST), at)
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
        icon = _fit(lit(folder), item.length)
        _check(item.display, icon)
        icon.save(os.path.join(ICON_DIR, f"{icon_name(item.display)}.png"))
        made.append(icon_name(item.display))
        icons.append(icon)
    if icons:
        _sheet(icons)
    # The character's portrait: the same light, on its own taller canvas.
    folder = os.path.join(PASSES_DIR, PORTRAIT)
    if (not only or PORTRAIT in only) and os.path.isdir(folder):
        portrait = _fit(lit(folder, PORTRAIT_LEVEL_TO), 1.0, (PORTRAIT_W, PORTRAIT_H))
        _check(PORTRAIT, portrait)
        portrait.save(os.path.join(ICON_DIR, f"{PORTRAIT_TEXTURE}.png"))
        made.append(PORTRAIT_TEXTURE)
    return made
