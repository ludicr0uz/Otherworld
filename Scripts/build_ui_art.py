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
# them per weapon.  They are silhouettes, not illustrations: at 84x42 on screen
# the only thing that survives is the outline, and the five have to be
# distinguishable from each other at a glance while the player is being chased.
# So each leans on its one unmistakable feature -- the shotgun's pump, the
# SMG's vertical magazine, the sniper's scope.

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
          fill=(255, 255, 255, 255), width=3 * s)


# How long each weapon reads relative to the longest. Applied as a scale after
# drawing, so the five sit in one family instead of each being hand-fitted to
# the canvas: a pistol that fills the slot as completely as a sniper rifle
# tells the player the wrong thing about it.
ICON_RELATIVE_LENGTH = {
    "Pistol": 0.60, "SMG": 0.76, "Shotgun": 0.94, "Rifle": 1.00, "Sniper": 1.00,
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
    target_w = max(1, round(ICON_W * SUPERSAMPLE * 0.94 * relative))
    scale = target_w / img.width
    target_h = max(1, round(img.height * scale))
    limit = round(ICON_H * SUPERSAMPLE * 0.94)
    if target_h > limit:
        target_w = max(1, round(target_w * limit / target_h))
        target_h = limit
    img = img.resize((target_w, target_h), Image.LANCZOS)

    out = _canvas(ICON_W, ICON_H)
    out.alpha_composite(img, ((out.width - target_w) // 2,
                              (out.height - target_h) // 2))
    return _down(out, ICON_W, ICON_H)


def icon_pistol(d):
    """Compact: a short slide over a deep grip. The grip is the whole tell --
    lengthen the slide and it reads as an SMG, which is what the first pass
    did."""
    _shape(d, polys=[[(40, 38), (56, 38), (50, 60), (32, 60)]],   # grip, raked
           rounds=[(36, 22, 86, 34, 3),      # slide
                   (82, 26, 92, 32, 2),      # muzzle
                   (40, 34, 58, 39, 1)])     # frame under the slide
    _guard(d, 52, 38, 68, 52)


def icon_shotgun(d):
    """The pump under the barrel is the tell."""
    _shape(d, polys=[[(14, 28), (32, 26), (32, 42), (16, 47)]],   # stock
           rounds=[(14, 26, 116, 33, 2),     # barrel, full length
                   (32, 25, 58, 38, 3),      # receiver
                   (64, 35, 96, 43, 4),      # pump / forend
                   (108, 26, 120, 33, 2)])   # muzzle
    _guard(d, 50, 37, 66, 51)


def icon_smg(d):
    """The vertical box magazine is the tell, so it is long and square-cut --
    the first pass tucked it under the body and the icon read as a pistol."""
    _shape(d, polys=[],
           rounds=[(30, 22, 88, 36, 3),      # boxy receiver
                   (84, 26, 100, 32, 2),     # stubby barrel
                   (18, 26, 32, 32, 2),      # folded stock
                   (50, 36, 64, 62, 2),      # MAGAZINE, straight and long
                   (72, 36, 80, 50, 2)])     # foregrip
    _guard(d, 62, 34, 76, 48)


def icon_rifle(d):
    """Long, with a curved magazine and a full stock."""
    _shape(d, polys=[[(12, 27), (32, 25), (32, 40), (14, 45)],    # stock
                     [(58, 36), (72, 36), (77, 56), (63, 56)]],   # curved mag
           rounds=[(12, 25, 120, 32, 2),     # full length
                   (32, 23, 64, 37, 3),      # receiver
                   (80, 33, 100, 39, 2),     # handguard
                   (112, 25, 124, 31, 2)])   # muzzle
    _guard(d, 46, 35, 62, 49)


def icon_sniper(d):
    """The scope is the tell, so it sits proud of the barrel with visible
    mounts and the bipod anchors the far end."""
    _shape(d, polys=[[(8, 30), (30, 27), (30, 43), (10, 48)],     # long stock
                     [(92, 35), (96, 35), (89, 54), (85, 54)],    # bipod leg
                     [(96, 35), (100, 35), (107, 54), (103, 54)]],
           rounds=[(8, 28, 124, 34, 2),      # very long barrel
                   (30, 26, 60, 39, 3),      # receiver
                   (42, 12, 84, 21, 4),      # scope tube
                   (47, 21, 52, 27, 1),      # front mount
                   (74, 21, 79, 27, 1),      # rear mount
                   (116, 27, 126, 33, 2)])   # muzzle brake
    _guard(d, 44, 35, 60, 49)


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
SLOTS = {
    "T_UI_Slot":       dict(w=104, h=68, active=False),
    "T_UI_SlotActive": dict(w=104, h=68, active=True),
}
FRAMES = {"T_UI_SlotFrame": dict(w=104, h=68)}
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
