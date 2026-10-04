"""The weapon slots' silhouettes: one white glyph per KIND of weapon (a rifle,
a pistol, a knife), drawn here as the stat icons are, and shown translucent in
an empty weapon slot (WBP_InventorySlot's Ghost image, at COL_GHOST's alpha).

They are drawings of the kind, not pictures of a weapon: the slot says what
belongs in it, and a render of the AK or the M9 there read as that very gun.
The items' own icons stay renders of their models (the item_icons package).

Each glyph is built round one fat feature that survives the 78 x 35 it is
drawn at: the rifle's raked magazine, the pistol's deep grip under a short
slide, the knife's pointed blade and crossguard.

Pillow is imported inside the drawing functions: the editor, which has no
Pillow, imports ghost_name() to point the slots at the textures.
build_ui_art.py writes them into assets/ui/ with the rest of the art.
"""

import os

GHOST_W, GHOST_H = 128, 64      # the item icons' canvas: the Ghost image's own 2:1
SS = 4                          # supersample
KINDS = ("Rifle", "Pistol", "Knife")
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)
# How long each kind reads beside the longest, applied after drawing: a pistol
# that fills the slot as a rifle does says the wrong thing about it.
RELATIVE_LENGTH = {"Rifle": 1.00, "Pistol": 0.55, "Knife": 0.70}
FILL = 0.94                     # of the canvas, the longest glyph's share


def ghost_name(kind):
    """Rifle -> T_UI_Ghost_Rifle."""
    return f"T_UI_Ghost_{kind}"


def _shape(d, polys=(), rounds=()):
    for p in polys:
        d.polygon([(x * SS, y * SS) for x, y in p], fill=WHITE)
    for x0, y0, x1, y1, r in rounds:
        d.rounded_rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS), radius=r * SS,
                            fill=WHITE)


def _guard(d, x0, y0, x1, y1):
    """A trigger guard: a half-loop hanging off the receiver."""
    d.arc((x0 * SS, y0 * SS, x1 * SS, y1 * SS), 0, 180, fill=WHITE, width=3 * SS)


def _rifle(d):
    _shape(d, polys=[[(2, 21), (30, 21), (30, 33), (4, 44)],      # stock
                     [(34, 32), (46, 32), (41, 50), (30, 50)],    # pistol grip
                     [(56, 32), (70, 32), (82, 55), (68, 58)]],   # raked magazine
           rounds=[(28, 19, 76, 33, 2),      # receiver
                   (74, 21, 102, 32, 2),     # handguard
                   (100, 23, 126, 28, 1),    # barrel
                   (114, 15, 118, 25, 1),    # front sight
                   (62, 15, 68, 21, 1)])     # rear sight
    _guard(d, 44, 26, 58, 42)


def _pistol(d):
    _shape(d, polys=[[(26, 34), (56, 34), (48, 62), (16, 62)]],   # grip, raked
           rounds=[(14, 12, 112, 29, 3),     # slide
                   (20, 27, 92, 37, 2),      # frame under the slide
                   (104, 8, 108, 14, 1)])    # front sight
    _guard(d, 54, 28, 80, 48)


def _knife(d):
    _shape(d, polys=[[(50, 21), (100, 21), (126, 33), (108, 41), (50, 41)]],  # blade
           rounds=[(4, 23, 46, 39, 6),       # handle
                   (43, 14, 51, 48, 2)])     # crossguard


GLYPHS = {"Rifle": _rifle, "Pistol": _pistol, "Knife": _knife}


def draw(kind):
    """The glyph, cropped to its ink, scaled to its share of the canvas and
    centred, so the drawings need only be right, not also pre-aligned."""
    from PIL import Image, ImageDraw
    big = (GHOST_W * SS, GHOST_H * SS)
    img = Image.new("RGBA", big, CLEAR)
    GLYPHS[kind](ImageDraw.Draw(img))
    img = img.crop(img.getbbox())
    w = max(1, round(big[0] * FILL * RELATIVE_LENGTH[kind]))
    h = max(1, round(img.height * w / img.width))
    limit = round(big[1] * FILL)
    if h > limit:
        w, h = max(1, round(w * limit / h)), limit
    img = img.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", big, CLEAR)
    out.alpha_composite(img, ((big[0] - w) // 2, (big[1] - h) // 2))
    return out.resize((GHOST_W, GHOST_H), Image.LANCZOS)


def write_slot_ghosts(out_dir):
    """One PNG per kind into ``out_dir``; returns the names written."""
    made = []
    for kind in KINDS:
        name = ghost_name(kind)
        draw(kind).save(os.path.join(out_dir, f"{name}.png"))
        made.append(name)
    return made
