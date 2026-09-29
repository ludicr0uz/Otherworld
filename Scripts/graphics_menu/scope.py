"""The sniper's scope on the HUD: when it is drawn instead of the crosshair
(_author_scope_gate) and the glass itself (_author_scope). Split out of
build_graphics_menu.py, which calls both from _author_reticle.

The scope belongs to aiming down the sights, not to aiming: the sniper's
shoulder aim (1.5x, COMBAT.shoulder_zoom) keeps the crosshair, and the glass
only arrives with zoom past that -- which only the sights give it.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.tuning import COMBAT
from graphics_menu.canvas import _draw_texture

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
ITEM_CLASS_PATH = "/Game/Weapons/BP_WeaponItem.BP_WeaponItem_C"

FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_DRAW_RECT = "/Script/Engine.HUD.DrawRect"
FN_FCLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_FMAX = "/Script/Engine.KismetMathLibrary.FMax"
FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_MAKE_COLOR = "/Script/Engine.KismetMathLibrary.MakeColor"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"

# --- the sniper's scope -------------------------------------------------------
# T_UI_Scope is a square: an opaque black field with a circular hole and the
# reticle etched across it. It is drawn as a square of the viewport's HEIGHT,
# centred, with the two leftover side strips filled black -- stretched to the
# viewport instead, its hole would be an ellipse, and drawn any smaller the
# corners of the world would show past the surround.
#
# It fades with the zoom rather than with a flag of its own: alpha is how far
# CurrentFOV has travelled from the shoulder aim's zoom toward this weapon's
# AdsZoom, so the glass arrives exactly as the camera settles and leaves with
# it, and there is no second interpolation to keep in step with the first.
SCOPE_TEX = "T_UI_Scope"

# The crosshair gives way to the glass only once the zoom is this far past the
# shoulder aim's. Not zero: the shoulder aim's FInterpTo settles on
# BaseFOV / shoulder_zoom to within rounding, and a zoom that read 1.5000001
# would swap the sniper's crosshair for an invisible scope while it is only
# shouldered. The glass's own alpha there is 0.02 / 2.5 -- nothing to see.
SCOPE_GATE_SLACK = 0.02


def _author_scope_gate(ed, as_weapon, scoped_out, keep, x0, y0):
    """The condition for drawing the scope instead of the crosshair.

        Held.Scoped AND BaseFOV / CurrentFOV > shoulder_zoom + SCOPE_GATE_SLACK

    Read off the zoom rather than off SightAiming for the reason the fade is:
    the flag drops the frame the key comes up, and the glass would vanish a
    frame after the sights were let go instead of opening out with the zoom.
    So a sniper at the hip or on the shoulder shows the crosshair, and one
    down its sights shows the glass for exactly as long as the zoom says so.

    Returns the condition pin.
    """
    base = keep(_at(ed.add_get_member_variable_node("BaseFOV",
                                                    WEAPON_COMP_CLASS_PATH),
                    x0, y0))
    _connect(as_weapon, _pin(base, "self"))
    now = keep(_at(ed.add_get_member_variable_node("CurrentFOV",
                                                   WEAPON_COMP_CLASS_PATH),
                   x0, y0 + 120))
    _connect(as_weapon, _pin(now, "self"))
    zoom = keep(_at(_node(ed, FN_DIV), x0 + 240, y0))
    _connect(_pin(base, "BaseFOV", is_input=False), _pin(zoom, "A"))
    _connect(_pin(now, "CurrentFOV", is_input=False), _pin(zoom, "B"))
    past = keep(_at(_node(ed, FN_GREATER), x0 + 480, y0))
    _connect(_pin(zoom, "ReturnValue", is_input=False), _pin(past, "A"))
    _set(past, "B", COMBAT.shoulder_zoom + SCOPE_GATE_SLACK)
    both = keep(_at(_node(ed, FN_AND), x0 + 720, y0 - 60))
    _connect(scoped_out, _pin(both, "A"))
    _connect(_pin(past, "ReturnValue", is_input=False), _pin(both, "B"))
    return _pin(both, "ReturnValue", is_input=False)


def _author_scope(ed, x0, y0, in_exec, as_weapon, held_out, cx, cy, height):
    """The world blacked out except for a circle, with the sniper's reticle in it.

    Three draws: two black rects for the strips either side, and T_UI_Scope as
    a square of the viewport's height between them. The square is what keeps
    the hole circular -- the texture is square, so stretching it across a 16:9
    viewport would flatten the circle into an ellipse -- and the strips are
    what keep the corners of the world from showing past it at any aspect.

    A portrait viewport makes those strips negative-width, which DrawRect
    renders as a rectangle running the wrong way rather than as nothing, so
    they are clamped at zero. The square then overhangs both edges and covers
    the viewport on its own, which is the right answer for that shape anyway.

    Everything fades on one alpha:

        alpha = clamp((BaseFOV / CurrentFOV - shoulder) / (AdsZoom - shoulder), 0, 1)

    i.e. how far the camera has travelled from the shoulder aim's zoom
    (COMBAT.shoulder_zoom) toward this weapon's zoom down its sights -- 0 when
    only shouldered, 1 when fully down the scope.
    That is deliberately not "Aiming", which is a key state and would snap the
    glass on a frame before the camera moved and off a frame before it came
    back. Reading it off the FOV means the scope and the zoom are the same
    animation by construction, with nothing to keep in step.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # cx - cy is both the square's left edge and the width of each side strip,
    # because the square is the viewport's height wide and centred: the two
    # leftovers are equal by construction.
    left = keep(_at(_node(ed, FN_SUB), x0, y0 + 300))
    _connect(cx, _pin(left, "A"))
    _connect(cy, _pin(left, "B"))
    left_out = _pin(left, "ReturnValue", is_input=False)
    right = keep(_at(_node(ed, FN_ADD), x0, y0 + 440))
    _connect(cx, _pin(right, "A"))
    _connect(cy, _pin(right, "B"))
    bar_w = keep(_at(_node(ed, FN_FMAX), x0 + 240, y0 + 300))
    _connect(left_out, _pin(bar_w, "A"))
    _set(bar_w, "B", 0.0)
    bar_w_out = _pin(bar_w, "ReturnValue", is_input=False)

    base = keep(_at(ed.add_get_member_variable_node("BaseFOV",
                                                    WEAPON_COMP_CLASS_PATH),
                    x0, y0 + 600))
    _connect(as_weapon, _pin(base, "self"))
    now = keep(_at(ed.add_get_member_variable_node("CurrentFOV",
                                                   WEAPON_COMP_CLASS_PATH),
                   x0, y0 + 720))
    _connect(as_weapon, _pin(now, "self"))
    zoom = keep(_at(_node(ed, FN_DIV), x0 + 240, y0 + 600))
    _connect(_pin(base, "BaseFOV", is_input=False), _pin(zoom, "A"))
    _connect(_pin(now, "CurrentFOV", is_input=False), _pin(zoom, "B"))
    travelled = keep(_at(_node(ed, FN_SUB), x0 + 480, y0 + 600))
    _connect(_pin(zoom, "ReturnValue", is_input=False), _pin(travelled, "A"))
    _set(travelled, "B", COMBAT.shoulder_zoom)

    # The denominator is this weapon's own zoom, not the config's scope
    # figure: the scope and the zoom factor are separate facts about a
    # weapon, and a 6x scope
    # would otherwise be fully opaque a third of the way in.
    ads = keep(_at(ed.add_get_member_variable_node("AdsZoom", ITEM_CLASS_PATH),
                   x0 + 240, y0 + 840))
    _connect(held_out, _pin(ads, "self"))
    span = keep(_at(_node(ed, FN_SUB), x0 + 480, y0 + 840))
    _connect(_pin(ads, "AdsZoom", is_input=False), _pin(span, "A"))
    _set(span, "B", COMBAT.shoulder_zoom)

    frac = keep(_at(_node(ed, FN_DIV), x0 + 720, y0 + 600))
    _connect(_pin(travelled, "ReturnValue", is_input=False), _pin(frac, "A"))
    _connect(_pin(span, "ReturnValue", is_input=False), _pin(frac, "B"))
    alpha = keep(_at(_node(ed, FN_FCLAMP), x0 + 960, y0 + 600))
    _connect(_pin(frac, "ReturnValue", is_input=False), _loose_pin(alpha, "Value"))
    _set(alpha, "Min", 0.0)
    _set(alpha, "Max", 1.0)
    alpha_out = _pin(alpha, "ReturnValue", is_input=False)

    ink = keep(_at(_node(ed, FN_MAKE_COLOR), x0 + 1200, y0 + 600))
    for ch in ("R", "G", "B"):
        _set(ink, ch, 0.0)
    _connect(alpha_out, _pin(ink, "A"))
    ink_out = _pin(ink, "ReturnValue", is_input=False)
    tint = keep(_at(_node(ed, FN_MAKE_COLOR), x0 + 1200, y0 + 760))
    for ch in ("R", "G", "B"):
        _set(tint, ch, 1.0)
    _connect(alpha_out, _pin(tint, "A"))

    flow = in_exec
    for i, at_x in enumerate((None, right)):
        r = keep(_at(_node(ed, FN_DRAW_RECT), x0 + 1460 + i * 260, y0))
        if at_x is None:
            _set(r, "ScreenX", 0.0)
        else:
            _connect(_pin(at_x, "ReturnValue", is_input=False), _pin(r, "ScreenX"))
        _set(r, "ScreenY", 0.0)
        _connect(bar_w_out, _pin(r, "ScreenW"))
        _connect(height, _pin(r, "ScreenH"))
        _connect(ink_out, _pin(r, "RectColor"))
        _connect(flow, _pin(r, "execute"))
        flow = BEL.find_then_pin(r)

    glass = keep(_draw_texture(ed, x0 + 1980, y0, SCOPE_TEX))
    _connect(left_out, _pin(glass, "ScreenX"))
    _set(glass, "ScreenY", 0.0)
    _connect(height, _pin(glass, "ScreenW"))
    _connect(height, _pin(glass, "ScreenH"))
    _connect(_pin(tint, "ReturnValue", is_input=False), _pin(glass, "TintColor"))
    _connect(flow, _pin(glass, "execute"))

    ed.add_comment_to_nodes(
        "The sniper's scope. Drawn as a square of the viewport's height with "
        "the side strips blacked out, so the hole stays a circle at any "
        "aspect ratio, and faded on how far CurrentFOV has travelled toward "
        "the weapon's AdsZoom -- the glass and the zoom are one animation.",
        made)

    return BEL.find_then_pin(glass)
