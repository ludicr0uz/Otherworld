"""What the HUD's canvas layers draw with: the generated art.

The canvas is down to what is placed per frame -- the reticle, the sniper's
scope and the wanderers' bars. Everything else is a UMG screen (umg_consts.py
has their palette).
"""

from combat.graph import _at, _node, _set
from graphics_menu.umg_consts import UI_ART_DIR

FN_DRAW_TEXTURE = "/Script/Engine.HUD.DrawTexture"

# ─── Generated artwork ───────────────────────────────────────────────────────
#
# DrawRect gives a flat, hard-edged, single-colour rectangle: no corner radius,
# no gradient, no border, no shadow. Every panel, bar and inventory slot was
# one of those, and that is what made the HUD look unfinished -- rearranging
# rectangles does not fix it.
#
# DrawTexture takes a tint and a blend mode, so the same layout drawn with
# generated art gets rounded corners, a hairline border and a lit gradient, and
# the weapons get silhouettes instead of colour swatches.
# Scripts/build_ui_art.py draws them; import_ui_art.py imports them, into
# UI_ART_DIR, where the UMG screens' brushes find them too.


def _draw_texture(ed, x, y, tex, w=None, h=None, tint=None):
    """A DrawTexture node with its UV rectangle set to the whole texture.

    The UV pins are NORMALISED (HUD.h: "in normalized UV distance"), so the
    whole texture is 0,0 + 1x1. Left unset they default to zero and the node
    draws nothing at all, which looks exactly like a missing texture. Set to
    the texel size, as they once were, the texture wraps that many times: a
    120x84 slot became a grid of amber borders and the 600x346 panel shrank
    to one transparent corner texel per pixel, i.e. vanished.
    """
    n = _at(_node(ed, FN_DRAW_TEXTURE), x, y)
    _set(n, "Texture", f"{UI_ART_DIR}/{tex}.{tex}")
    if w is not None:
        _set(n, "ScreenW", w)
    if h is not None:
        _set(n, "ScreenH", h)
    _set(n, "TextureU", 0.0)
    _set(n, "TextureV", 0.0)
    _set(n, "TextureUWidth", 1.0)
    _set(n, "TextureVHeight", 1.0)
    if tint:
        _set(n, "TintColor", tint)
    return n
