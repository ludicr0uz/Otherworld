"""What every panel of BP_GraphicsMenuHUD draws with: the generated art, the
font, and the panel text palette.

Split out of build_graphics_menu.py so the settings page (settings_page.py)
can draw the same way without importing the entry point.
"""

from combat.graph import _at, _node, _set

FN_DRAW_TEXTURE = "/Script/Engine.HUD.DrawTexture"

# The panel text palette: titles, rows, the caret, and the dim hint line.
COL_TITLE = "(R=0.850000,G=0.900000,B=1.000000,A=1.000000)"
COL_ROW = "(R=0.720000,G=0.750000,B=0.800000,A=1.000000)"
COL_CARET = "(R=1.000000,G=0.820000,B=0.320000,A=1.000000)"
COL_MAIN_HINT = "(R=0.560000,G=0.590000,B=0.650000,A=1.000000)"

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
# Scripts/build_ui_art.py draws them; import_ui_art.py imports them.
UI_ART_DIR = "/Game/UI/Art"

# Roboto rather than the engine's default face. The default is a bitmap font
# that does not scale cleanly, and at the sizes this HUD uses -- the HP number
# is drawn at 2.4x, the death title at 3.4x -- it is the single most obviously
# unpolished thing on screen.
UI_FONT = "/Engine/EngineFonts/Roboto.Roboto"


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
