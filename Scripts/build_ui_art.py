#!/usr/bin/env python3
"""build_ui_art.py -- generate the HUD's artwork.

Run outside the editor (it needs Pillow, the editor's embedded Python does
not have it):

    python3 Scripts/build_ui_art.py

Writes PNGs to assets/ui/.  Scripts/asset_pipeline/import_ui_art.py imports
them.  assets/ is git-ignored, so THIS FILE is the source of truth for how the
HUD looks -- the PNGs are build output, the same as every other asset here.

── Why textures at all ─────────────────────────────────────────────────────

The HUD draws with HUD::DrawRect and HUD::DrawText.  DrawRect gives a flat,
hard-edged, single-colour rectangle: no corner radius, no gradient, no border,
no shadow.  Every panel and every inventory slot was one of those, and a
weapon was a coloured square with its name under it.  That is what made the UI
look unfinished, and no amount of rearranging rectangles fixes it.

DrawTexture takes a tint and a blend mode, so one generated PNG per element
buys rounded corners, a border, a gradient and a soft shadow -- and, for the
weapons, an actual silhouette instead of a colour swatch.

Sizes are exact rather than stretched.  The panels are fixed-size in the HUD,
so a texture generated at that exact size is drawn 1:1 and its corner radius
and 1px border stay crisp; a stretched texture would smear both.

Everything is drawn at SUPERSAMPLE x and reduced, which is where the clean
edges come from -- PIL's polygon fill is hard-edged.
"""

import math
import os

# Pillow is imported lazily, inside the functions that draw. The editor's
# embedded Python has no Pillow but DOES need WEAPON_ICON_ROWS below, and a
# module-level import would make this file unimportable there.

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "assets", "ui")

SUPERSAMPLE = 4

# ── Palette ─────────────────────────────────────────────────────────────────
# One dark, slightly blue, low-chroma scheme.  Blue-grey rather than neutral
# grey because the game is a night forest lit by a 0.12 lux moon: a neutral
# panel reads as a grey hole punched in the picture, a cool one sits in it.
INK_TOP = (16, 20, 28)
INK_BOTTOM = (8, 10, 15)
BORDER = (125, 145, 175)
ACCENT = (255, 209, 82)
DANGER_TOP = (34, 12, 14)
DANGER_BOTTOM = (16, 6, 8)
DANGER_BORDER = (190, 70, 60)


def _canvas(w, h):
    from PIL import Image
    return Image.new("RGBA", (w * SUPERSAMPLE, h * SUPERSAMPLE), (0, 0, 0, 0))


def _down(img, w, h):
    from PIL import Image
    return img.resize((w, h), Image.LANCZOS)


def _vertical_gradient(size, top, bottom, alpha_top, alpha_bottom):
    from PIL import Image
    w, h = size
    grad = Image.new("RGBA", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = (
            round(top[0] + (bottom[0] - top[0]) * t),
            round(top[1] + (bottom[1] - top[1]) * t),
            round(top[2] + (bottom[2] - top[2]) * t),
            round(alpha_top + (alpha_bottom - alpha_top) * t),
        )
    return grad.resize((w, h))


def panel(w, h, radius=12, top=INK_TOP, bottom=INK_BOTTOM, border=BORDER,
          border_alpha=70, alpha_top=238, alpha_bottom=248, accent=None):
    """A rounded, gradient-filled panel with a hairline border.

    The border is the detail that does the most work: a dark panel with no
    edge reads as a hole, and one with a faint light edge reads as a surface.
    """
    from PIL import Image, ImageDraw
    s = SUPERSAMPLE
    img = _canvas(w, h)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1), radius=radius * s, fill=255)

    fill = _vertical_gradient(img.size, top, bottom, alpha_top, alpha_bottom)
    img.paste(fill, (0, 0), mask)

    edge = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1), radius=radius * s,
        outline=border + (border_alpha,), width=max(1, s))
    img.alpha_composite(edge)

    # A brighter line along the TOP edge only. Light comes from above, so this
    # is what makes the panel look like it has thickness rather than a decal.
    #
    # It is a single horizontal line, not a rounded-rectangle outline: the
    # first attempt drew an outline over the top half, and its bottom edge
    # showed up as a seam straight across the middle of every panel and slot.
    gloss = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gloss).line(
        ((radius + 2) * s, 1.5 * s, (w - radius - 2) * s, 1.5 * s),
        fill=(255, 255, 255, 34), width=max(1, s))
    img.alpha_composite(gloss)

    if accent:
        bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(bar).rounded_rectangle(
            (0, 0, w * s - 1, 2 * s), radius=s, fill=accent + (200,))
        img.alpha_composite(Image.composite(
            bar, Image.new("RGBA", img.size, (0, 0, 0, 0)), mask))
    return _down(img, w, h)


def slot(w, h, radius=8, active=False):
    """One inventory slot: the same panel language, one step lighter."""
    img = panel(w, h, radius=radius,
                top=(26, 31, 42) if active else (18, 22, 30),
                bottom=(14, 17, 24) if active else (10, 12, 18),
                border=ACCENT if active else BORDER,
                border_alpha=210 if active else 55,
                alpha_top=225, alpha_bottom=235)
    if active:
        from PIL import Image, ImageDraw, ImageFilter
        # A glow outside the border, so the equipped slot separates from its
        # neighbours at a glance instead of on inspection.
        s = SUPERSAMPLE
        big = img.resize((w * s, h * s), Image.LANCZOS)
        glow = Image.new("RGBA", big.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle(
            (0, 0, w * s - 1, h * s - 1), radius=radius * s,
            outline=ACCENT + (120,), width=3 * s)
        glow = glow.filter(ImageFilter.GaussianBlur(3 * s))
        out = Image.alpha_composite(glow, big)
        return _down(out, w, h)
    return img


def slot_frame(w, h, radius=8):
    """Just the equipped slot's amber edge and glow, with nothing inside.

    A separate texture from T_UI_SlotActive because this one is drawn OVER the
    weapon icon: a filled highlight would hide the very thing the player is
    looking at. The filled variant stays for the background pass.
    """
    from PIL import Image, ImageDraw, ImageFilter
    s = SUPERSAMPLE
    glow = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1), radius=radius * s,
        outline=ACCENT + (110,), width=3 * s)
    glow = glow.filter(ImageFilter.GaussianBlur(3 * s))
    edge = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1), radius=radius * s,
        outline=ACCENT + (235,), width=max(1, s))
    return _down(Image.alpha_composite(glow, edge), w, h)


def bar_fill(w, h, colour):
    """A bar lit from above and darkened at the foot, so it reads as a solid.

    A flat fill of the same colour reads as a progress bar from a settings
    dialog. The range matters more than the midpoint: shading from well above
    to well below the base colour is what gives it a surface.
    """
    from PIL import Image, ImageDraw
    s = SUPERSAMPLE
    img = _canvas(w, h)
    top = tuple(min(255, round(c * 1.45 + 22)) for c in colour)
    bottom = tuple(max(0, round(c * 0.62)) for c in colour)
    fill = _vertical_gradient(img.size, top, bottom, 255, 255)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1), radius=2 * s, fill=255)
    img.paste(fill, (0, 0), mask)
    return _down(img, w, h)


# ── Weapon silhouettes ──────────────────────────────────────────────────────
#
# Side profiles facing right, drawn white on transparent so the HUD can tint
# them per weapon.  They are silhouettes, not illustrations: at 112x50 on screen
# the only thing that survives is the outline, and the five have to be
# distinguishable from each other at a glance while the player is being chased.
#
# The first pass got that wrong and it is worth recording how: each weapon was
# given its identifying feature, but as DETAIL -- a pump 8 units deep, a 6-unit
# scope, a front sight post 6 x 9.  Reduced to slot size those land on two or
# three pixels each, and two or three pixels of a 50-pixel icon is noise.  The
# player reported "lots of small dots", which is exactly what a 3px feature
# antialiased down to a HUD looks like.
#
# So the rule now is that the distinguishing feature is not a detail but the
# BULK, and the five differ in where their bulk sits:
#
#     Pistol    small, and nothing else in the set is
#     Shotgun   two full-length horizontal tubes with daylight between them
#     SMG       a magazine dropping below the body -- a T
#     Rifle     a raked magazine, the only slanted mass here
#     Sniper    a scope, the only mass ABOVE the barrel
#
# Every one of those survives being shrunk, because shrinking a big shape
# leaves a smaller big shape.

ICON_W, ICON_H = 128, 64


def _shape(draw, polys, rounds=(), circles=()):
    s = SUPERSAMPLE
    white = (255, 255, 255, 255)
    for p in polys:
        draw.polygon([(x * s, y * s) for x, y in p], fill=white)
    for (x0, y0, x1, y1, r) in rounds:
        draw.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s),
                               radius=r * s, fill=white)
    for (cx, cy, rad) in circles:
        draw.ellipse(((cx - rad) * s, (cy - rad) * s,
                      (cx + rad) * s, (cy + rad) * s), fill=white)


def _guard(d, x0, y0, x1, y1):
    """A trigger guard, as a half-loop hanging off the receiver."""
    s = SUPERSAMPLE
    d.arc((x0 * s, y0 * s, x1 * s, y1 * s), 0, 180,
          fill=(255, 255, 255, 255), width=4 * s)


# How long each weapon reads relative to the longest. Applied as a scale after
# drawing, so the five sit in one family instead of each being hand-fitted to
# the canvas: a pistol that fills the slot as completely as a sniper rifle
# tells the player the wrong thing about it.
ICON_RELATIVE_LENGTH = {
    "Pistol": 0.55, "SMG": 0.72, "Shotgun": 0.96, "Rifle": 1.00, "Sniper": 1.00,
}


def _icon(builder, relative=1.0):
    """Draw, then crop to ink, scale to its share of the width, and centre.

    Normalising after the fact rather than in each builder's coordinates means
    the drawings only have to be *right*, not also pre-aligned, and the family
    stays consistent when one of them is edited.
    """
    from PIL import Image, ImageDraw
    img = _canvas(ICON_W, ICON_H)
    builder(ImageDraw.Draw(img))
    box = img.getbbox()
    if box:
        img = img.crop(box)
    target_w = max(1, round(ICON_W * SUPERSAMPLE * 0.98 * relative))
    scale = target_w / img.width
    target_h = max(1, round(img.height * scale))
    limit = round(ICON_H * SUPERSAMPLE * 0.98)
    if target_h > limit:
        target_w = max(1, round(target_w * limit / target_h))
        target_h = limit
    img = img.resize((target_w, target_h), Image.LANCZOS)

    out = _canvas(ICON_W, ICON_H)
    out.alpha_composite(img, ((out.width - target_w) // 2,
                              (out.height - target_h) // 2))
    return _down(out, ICON_W, ICON_H)


# The five drawings.  Each one is built around a single feature that no other
# weapon in the set has, and that feature is drawn FAT -- see the note above
# _shape for why.  What each one is for:
#
#   Pistol    small.  It is the only short one, so size alone identifies it.
#   Shotgun   two full-length tubes, barrel over magazine, and a fat pump.
#   SMG       a long straight magazine dropping to the bottom of the frame.
#   Rifle     a raked banana magazine -- the only slanted shape in the set.
#   Sniper    a scope, which is the only mass ABOVE the barrel in the set.
#
# So the five differ by where their bulk sits (small / two bars / below /
# slanted / above) rather than by detail, which is what survives the reduction
# to 112 x 54 on screen.


def icon_pistol(d):
    """Compact: a short slide over a deep grip.

    The whole tell is that it is SMALL -- ICON_RELATIVE_LENGTH draws it at
    just over half the length of the rifles, so it reads before any detail
    does.  The grip is drawn deep and heavily raked to use the height the
    short body leaves free.
    """
    _shape(d, polys=[[(40, 40), (66, 40), (58, 64), (30, 64)]],   # grip, raked
           rounds=[(30, 18, 96, 32, 3),      # slide
                   (34, 31, 74, 41, 2)])     # frame under the slide
    _guard(d, 56, 40, 78, 58)


def icon_shotgun(d):
    """Two full-length tubes and a fat pump.

    Barrel over magazine tube is the one shape in the set that is a DOUBLE
    horizontal bar, and the pump is a solid block bridging both.  The previous
    pass drew a single thin barrel with a small forend, which at slot size was
    the same blob as the rifle.
    """
    _shape(d, polys=[[(2, 18), (28, 15), (28, 40), (6, 48)]],     # stock
           rounds=[(26, 16, 122, 26, 3),     # barrel
                   (44, 32, 112, 40, 3),     # magazine tube, under it
                   (26, 14, 58, 42, 3),      # receiver, joining the two
                   (64, 31, 94, 47, 4)])     # pump, riding the tube
    _guard(d, 44, 42, 62, 58)


def icon_smg(d):
    """A long straight magazine, dropping clear of the body.

    Short receiver plus a magazine that reaches the bottom of the frame: the
    silhouette is a T, which nothing else here is.
    """
    _shape(d, polys=[],
           rounds=[(22, 16, 86, 34, 3),      # boxy receiver
                   (84, 21, 104, 29, 2),     # stubby barrel
                   (8, 20, 24, 30, 2),       # folded stock
                   (46, 34, 62, 64, 2)])     # MAGAZINE -- the tell
    _guard(d, 62, 34, 80, 50)


def icon_rifle(d):
    """Long, with a raked banana magazine.

    The magazine is the only slanted mass in the set, so the rifle is told
    apart from the shotgun by the angle rather than by any detail.
    """
    _shape(d, polys=[[(2, 20), (30, 17), (30, 40), (6, 48)],      # stock
                     [(52, 38), (70, 38), (84, 61), (66, 61)]],   # banana mag
           rounds=[(12, 24, 124, 30, 2),     # thin barrel, full length
                   (28, 18, 72, 38, 3),      # receiver
                   (88, 27, 114, 35, 2)])    # handguard
    _guard(d, 40, 38, 56, 52)


def icon_sniper(d):
    """A scope, which is the only mass above the barrel in the set.

    Drawn long and thick and sitting proud on two mounts, so "something big on
    top" survives even when the mounts and the bipod do not.
    """
    _shape(d, polys=[[(0, 24), (28, 21), (28, 44), (4, 52)],      # long stock
                     [(90, 34), (96, 34), (88, 60), (82, 60)],    # bipod legs
                     [(96, 34), (102, 34), (110, 60), (104, 60)]],
           rounds=[(6, 26, 126, 34, 2),      # very long barrel
                   (26, 22, 64, 40, 3),      # receiver
                   (34, 2, 92, 16, 5),       # SCOPE -- the tell
                   (42, 15, 50, 27, 1),      # front mount
                   (76, 15, 84, 27, 1)])     # rear mount
    _guard(d, 42, 40, 58, 54)


# One texture per weapon, named T_UI_Icon_<DisplayName>. The item carries a
# Texture2D reference to its own, so the HUD draws whatever the weapon says it
# looks like and holds no table of weapon names -- the same rule the rest of
# the strip already follows for SlotColor and DisplayName.
#
# This module keeps its Pillow imports inside its functions so that the editor,
# which has no Pillow, can still import ICON_NAME_FOR to build those defaults.
def ICON_NAME_FOR(display):
    return f"T_UI_Icon_{display}"


ICONS = {
    "Pistol": icon_pistol,
    "Shotgun": icon_shotgun,
    "SMG": icon_smg,
    "Rifle": icon_rifle,
    "Sniper": icon_sniper,
}

# Exact HUD sizes. Generated at the size they are drawn so the corner radius
# and the hairline border land on whole pixels instead of being resampled.
PANELS = {
    "T_UI_Panel":      dict(w=600, h=346, radius=14, accent=ACCENT),
    "T_UI_PanelDeath": dict(w=560, h=300, radius=14, top=DANGER_TOP,
                            bottom=DANGER_BOTTOM, border=DANGER_BORDER,
                            border_alpha=110, accent=(200, 60, 50)),
}
# 120 x 84, up from 104 x 68. The slot exists to make its icon readable and it
# was not big enough to: at the old size the five silhouettes reduced to the
# same white blob and the ammunition count sat on top of the icon because there
# was nowhere else for it. The extra 16 px of height is a text row under the
# icon; the extra 16 px of width is icon.
SLOTS = {
    "T_UI_Slot":       dict(w=120, h=84, active=False),
    "T_UI_SlotActive": dict(w=120, h=84, active=True),
}
FRAMES = {"T_UI_SlotFrame": dict(w=120, h=84)}
# One white bar, tinted at draw time, rather than one texture per colour.
# HUD::DrawTexture takes a tint, and the stamina bar changes colour while it is
# being spent -- with baked colours that would need two textures and a switch,
# and every future bar would need another PNG.
#
# White means the gradient is pure shading, so a tint multiplies to exactly the
# intended colour. The track is separate because it is not a tinted bar, it is
# a hole.
BARS = {
    "T_UI_Bar":      (255, 255, 255),
    "T_UI_BarTrack": (16, 18, 24),
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    made = []

    for name, kw in PANELS.items():
        panel(**kw).save(os.path.join(OUT_DIR, f"{name}.png"))
        made.append(name)

    for name, kw in SLOTS.items():
        slot(**kw).save(os.path.join(OUT_DIR, f"{name}.png"))
        made.append(name)

    for name, kw in FRAMES.items():
        slot_frame(**kw).save(os.path.join(OUT_DIR, f"{name}.png"))
        made.append(name)

    for name, colour in BARS.items():
        bar_fill(240, 32, colour).save(os.path.join(OUT_DIR, f"{name}.png"))
        made.append(name)

    for display, builder in ICONS.items():
        name = ICON_NAME_FOR(display)
        _icon(builder, ICON_RELATIVE_LENGTH.get(display, 1.0)).save(
            os.path.join(OUT_DIR, f"{name}.png"))
        made.append(name)

    print(f"wrote {len(made)} PNGs to {OUT_DIR}")
    for n in made:
        print(f"   {n}")


if __name__ == "__main__":
    main()
