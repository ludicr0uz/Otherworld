"""The consumables' inventory icons, drawn the way build_ui_art.py draws the
weapons': white silhouettes at SUPERSAMPLE, cropped, scaled into the 128x64
icon canvas by build_ui_art._icon, and tinted at draw time with each item's
SlotColor. Pure Python + Pillow, run outside the editor.

Each drawing commits to one shape, for the reason the weapon set does -- what
survives the reduction to 112x50 in a slot is where the bulk sits:

    Mushroom   a wide dome on a short stem: the only mass wider at the top.
    Canteen    a flat round flask with a rim, a spout and two strap lugs:
               the only round thing in the strip.

Spots and the canteen's rim are punched OUT of the silhouette (drawn with a
fully transparent fill), so they read as detail under any tint.
"""

import os

from build_ui_art import ICON_NAME_FOR, OUT_DIR, SUPERSAMPLE, _icon

HOLE = (0, 0, 0, 0)
INK = (255, 255, 255, 255)


def _box(x0, y0, x1, y1):
    s = SUPERSAMPLE
    return (x0 * s, y0 * s, x1 * s, y1 * s)


def icon_mushroom(d):
    s = SUPERSAMPLE
    d.chord(_box(20, 4, 108, 60), 180, 360, fill=INK)            # the cap
    d.rounded_rectangle(_box(52, 30, 76, 62), radius=7 * s, fill=INK)  # stem
    d.rectangle(_box(24, 30, 104, 33), fill=HOLE)                 # gill line
    for cx, cy, r in ((46, 18, 5), (70, 12, 4), (86, 22, 4)):     # spots
        d.ellipse(_box(cx - r, cy - r, cx + r, cy + r), fill=HOLE)


def icon_canteen(d):
    s = SUPERSAMPLE
    d.ellipse(_box(30, 10, 98, 64), fill=INK)                     # the flask
    d.ellipse(_box(37, 17, 91, 57), outline=HOLE, width=3 * s)    # its rim
    d.rounded_rectangle(_box(56, 2, 72, 14), radius=2 * s, fill=INK)  # spout
    d.rounded_rectangle(_box(27, 15, 41, 24), radius=3 * s, fill=INK)  # strap lugs
    d.rounded_rectangle(_box(87, 15, 101, 24), radius=3 * s, fill=INK)


ICONS = {"Mushroom": icon_mushroom, "Canteen": icon_canteen}


def write_icons():
    os.makedirs(OUT_DIR, exist_ok=True)
    made = []
    for display, builder in ICONS.items():
        name = ICON_NAME_FOR(display)
        _icon(builder, 0.62).save(os.path.join(OUT_DIR, f"{name}.png"))
        made.append(name)
    return made
