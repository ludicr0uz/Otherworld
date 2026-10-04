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
buys rounded corners, a border, a gradient and a soft shadow.  (The items'
icons are not drawn here: Scripts/build_item_icons.py renders each from its
3D model.)

Sizes are exact rather than stretched.  The panels are fixed-size in the HUD,
so a texture generated at that exact size is drawn 1:1 and its corner radius
and 1px border stay crisp; a stretched texture would smear both.

Everything is drawn at SUPERSAMPLE x and reduced, which is where the clean
edges come from -- PIL's polygon fill is hard-edged.
"""

import os

from ui_art.slot_ghosts import write_slot_ghosts
from ui_art.stat_icons import write_stat_icons
from ui_art.vertical_bars import write_vertical_bars

# Pillow is imported lazily, inside the functions that draw.

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


# ── The sniper's scope ──────────────────────────────────────────────────────
#
# One square texture: opaque black everywhere except a circular hole in the
# middle, with the reticle drawn across the hole.  The HUD draws it as a square
# of the viewport's HEIGHT and fills the two side strips with black rects, so
# the circle stays a circle at any aspect ratio -- stretching this to the
# viewport would make it an ellipse, and anything smaller would let the corners
# of the world show past the surround.
#
# Black-and-transparent rather than black-and-a-tinted-lens: the game is a
# night forest at 0.12 lux and the scope is the only way to see anything at
# 200 m, so a lens tint would cost the player the very thing they scoped for.
SCOPE_SIZE = 1024
# Of the texture's width. Just under a half, so the rim has somewhere to sit
# and the reticle's outer posts are not clipped by the edge.
SCOPE_RADIUS = 0.468

# The reticle is a duplex: four fat posts from the rim that taper to a fine
# cross at the centre. The fat outer half is what the eye finds instantly under
# recoil; the fine inner half is what the shot is actually taken with, and a
# reticle that is fine all the way out is invisible against foliage.
SCOPE_POST_INNER = 0.34    # where the fat post stops, as a fraction of radius
SCOPE_TICK_STEP = 0.11     # mil-dot spacing, same units
SCOPE_TICK_LONG = 0.055    # every fifth tick
SCOPE_TICK_SHORT = 0.030

# Black core with a faint white halo under it. A pure black reticle disappears
# against a trunk and a pure white one disappears against the sky; the pair
# reads against both, which is the whole reason scopes are etched this way.
SCOPE_INK = (10, 11, 14)
SCOPE_HALO = (235, 240, 250)


def _scope_line(d, p0, p1, width, colour, alpha):
    d.line((p0[0], p0[1], p1[0], p1[1]), fill=colour + (alpha,),
           width=max(1, int(round(width))))


def scope_overlay(size=SCOPE_SIZE):
    """The sniper's scope: a black field with a hole in it and a reticle across it.

    Drawn at 2x and reduced rather than the strip's 4x: at 1024 square that is
    already a 4096 x 4096 intermediate, and the only edges that matter here are
    the rim and four straight lines.
    """
    from PIL import Image, ImageDraw
    s = 2
    n = size * s
    c = n / 2.0
    r = n * SCOPE_RADIUS

    # The surround, and the hole punched straight through its alpha. putalpha
    # rather than drawing a transparent ellipse: ImageDraw composites nothing,
    # it *replaces*, but only for the colour channels -- an ellipse filled with
    # alpha 0 over black leaves black, not a hole.
    img = Image.new("RGBA", (n, n), (0, 0, 0, 255))
    hole = Image.new("L", (n, n), 255)
    ImageDraw.Draw(hole).ellipse((c - r, c - r, c + r, c + r), fill=0)
    img.putalpha(hole)

    # A soft inner shadow just inside the rim, as concentric rings rather than
    # a blur: a GaussianBlur wide enough to read here is a 40-pixel kernel over
    # four megapixels, and the rings are indistinguishable once reduced.
    shade = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    rings = int(round(n * 0.045))
    for i in range(rings):
        t = i / float(rings)
        rr = r - i
        sd.ellipse((c - rr, c - rr, c + rr, c + rr),
                   outline=(0, 0, 0, int(round(215 * (1.0 - t) ** 1.6))),
                   width=s)
    img.alpha_composite(shade)

    ink = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(ink)
    post_w = n * 0.0135
    fine_w = n * 0.0034
    halo_w = fine_w + 3 * s
    inner = r * SCOPE_POST_INNER

    # Four arms, as (dx, dy) unit steps: right, left, down, up.
    arms = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for layer, (colour, grow, alpha) in enumerate(
            ((SCOPE_HALO, 3 * s, 90), (SCOPE_INK, 0, 240))):
        for dx, dy in arms:
            _scope_line(d, (c + dx * r, c + dy * r),
                        (c + dx * inner, c + dy * inner),
                        post_w + grow, colour, alpha)
            _scope_line(d, (c + dx * inner, c + dy * inner), (c, c),
                        fine_w + grow, colour, alpha)
            # Graduations along the fine section, perpendicular to the arm, so
            # the scope can be held off for range and for a moving target.
            k = 1
            while k * SCOPE_TICK_STEP * r < inner:
                at = k * SCOPE_TICK_STEP * r
                half = r * (SCOPE_TICK_LONG if k % 5 == 0 else SCOPE_TICK_SHORT)
                px, py = c + dx * at, c + dy * at
                _scope_line(d, (px - dy * half, py - dx * half),
                            (px + dy * half, py + dx * half),
                            fine_w + grow, colour, alpha)
                k += 1
        if layer == 0:
            ink = ink.filter(_blur(halo_w * 0.4))
            d = ImageDraw.Draw(ink)

    # The reticle is clipped to the hole: the arms are drawn out to the rim and
    # would otherwise paint over the surround, which is the one place they must
    # not appear -- a line on the black border reads as a scratch on the lens.
    img.alpha_composite(Image.composite(
        ink, Image.new("RGBA", (n, n), (0, 0, 0, 0)),
        Image.eval(hole, lambda v: 255 - v)))
    return _down(img, size, size)


def _blur(radius):
    from PIL import ImageFilter
    return ImageFilter.GaussianBlur(max(0.5, radius))


# ── Item icons ──────────────────────────────────────────────────────────────
#
# Not drawn here any more. Each item's inventory icon is a picture of its own
# 3D model, rendered by Scripts/build_item_icons.py into the same folder
# (T_UI_Icon_<DisplayName>.png), which this script leaves alone.

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

    scope_overlay().save(os.path.join(OUT_DIR, "T_UI_Scope.png"))
    made.append("T_UI_Scope")

    made += write_stat_icons(OUT_DIR)
    made += write_slot_ghosts(OUT_DIR)
    made += write_vertical_bars(OUT_DIR)

    print(f"wrote {len(made)} PNGs to {OUT_DIR}")
    for n in made:
        print(f"   {n}")


if __name__ == "__main__":
    main()
