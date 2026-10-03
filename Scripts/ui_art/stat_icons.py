"""The stat icons: one white glyph per HUD bar, tinted to the bar's colour by
the Image widget that shows it (the same one-white-texture rule as T_UI_Bar).

    HP           a heart
    Stamina      a lightning bolt
    Hunger       a chicken leg
    Thirst       a drop
    Temperature  a thermometer

Pillow is imported inside the drawing functions: the editor, which has no
Pillow, imports stat_icon_name() to point the HUD's brushes at the textures.
build_ui_art.py writes them into assets/ui/ with the rest of the art.
"""

import os

ICON_PX = 32          # drawn 1:1 at the HUD's icon size (umg_consts.STAT_ICON)
SS = 8                # supersample; the glyphs are all curves
STATS = ("Health", "Stamina", "Hunger", "Thirst", "Temperature")
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


def stat_icon_name(stat):
    """Health -> T_UI_Stat_Health."""
    return f"T_UI_Stat_{stat}"


def _xy(points):
    return [(x * SS, y * SS) for x, y in points]


def _box(x0, y0, x1, y1):
    return (x0 * SS, y0 * SS, x1 * SS, y1 * SS)


def _heart(d):
    d.ellipse(_box(3, 5, 17, 19), fill=WHITE)
    d.ellipse(_box(15, 5, 29, 19), fill=WHITE)
    d.polygon(_xy([(3.6, 14.5), (28.4, 14.5), (16, 28.5)]), fill=WHITE)


def _bolt(d):
    d.polygon(_xy([(19, 2), (6, 18), (15, 18), (12, 30), (26, 13), (17, 13),
                   (21, 2)]), fill=WHITE)


def _chicken_leg(d):
    d.ellipse(_box(11, 2, 30, 21), fill=WHITE)                 # the meat
    d.polygon(_xy([(12, 9), (23, 20), (12, 23), (9, 20)]), fill=WHITE)  # tapering
    d.line(_box(13, 19, 6.5, 25.5), fill=WHITE, width=int(3.4 * SS))   # the bone
    for cx, cy in ((4.6, 24.2), (7.8, 27.4)):                  # its two knobs
        d.ellipse(_box(cx - 2.7, cy - 2.7, cx + 2.7, cy + 2.7), fill=WHITE)
    d.arc(_box(17, 5, 27, 15), 285, 15, fill=CLEAR, width=int(1.4 * SS))  # gloss


def _drop(d):
    d.ellipse(_box(7, 12, 25, 30), fill=WHITE)
    d.polygon(_xy([(16, 2), (7.6, 18), (24.4, 18)]), fill=WHITE)


def _thermometer(d):
    d.rounded_rectangle(_box(12, 2, 20, 22), radius=4 * SS, fill=WHITE)
    d.ellipse(_box(8, 17, 24, 31), fill=WHITE)
    d.rounded_rectangle(_box(14.5, 5, 17.5, 20), radius=1.5 * SS, fill=CLEAR)
    for y in (8, 12, 16):                                      # the scale
        d.line(_box(20, y, 25, y), fill=WHITE, width=2 * SS)


GLYPHS = {"Health": _heart, "Stamina": _bolt, "Hunger": _chicken_leg,
          "Thirst": _drop, "Temperature": _thermometer}


def draw(stat):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (ICON_PX * SS, ICON_PX * SS), CLEAR)
    GLYPHS[stat](ImageDraw.Draw(img))
    return img.resize((ICON_PX, ICON_PX), Image.LANCZOS)


def write_stat_icons(out_dir):
    """One PNG per stat into ``out_dir``; returns the names written."""
    made = []
    for stat in STATS:
        name = stat_icon_name(stat)
        draw(stat).save(os.path.join(out_dir, f"{name}.png"))
        made.append(name)
    return made
