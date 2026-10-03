"""The sniper's scope on the HUD: when it is drawn instead of the crosshair
(_author_scope_gate) and the glass itself (_author_scope). Split out of
build_graphics_menu.py, which calls both from _author_reticle.

The scope belongs to aiming down the sights, not to aiming: the sniper's
shoulder aim (1.5x, COMBAT.shoulder_zoom) keeps the crosshair, and the glass
only arrives with zoom past that -- which only the sights give it.
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, out, then
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


def _author_scope_gate(ed, as_weapon, scoped_out, keep):
    """The condition for drawing the scope instead of the crosshair.

        Held.Scoped AND BaseFOV / CurrentFOV > shoulder_zoom + SCOPE_GATE_SLACK

    Read off the zoom rather than off SightAiming for the reason the fade is:
    the flag drops the frame the key comes up, and the glass would vanish a
    frame after the sights were let go instead of opening out with the zoom.
    So a sniper at the hip or on the shoulder shows the crosshair, and one
    down its sights shows the glass for exactly as long as the zoom says so.

    Returns the condition pin.
    """
    base = keep(ed.add_get_member_variable_node("BaseFOV", WEAPON_COMP_CLASS_PATH))
    _connect(as_weapon, _pin(base, "self"))
    now = keep(ed.add_get_member_variable_node("CurrentFOV", WEAPON_COMP_CLASS_PATH))
    _connect(as_weapon, _pin(now, "self"))
    zoom = keep(_node(ed, FN_DIV))
    _connect(out(base, "BaseFOV"), _pin(zoom, "A"))
    _connect(out(now, "CurrentFOV"), _pin(zoom, "B"))
    past = keep(_node(ed, FN_GREATER))
    _connect(out(zoom), _pin(past, "A"))
    _set(past, "B", COMBAT.shoulder_zoom + SCOPE_GATE_SLACK)
    both = keep(_node(ed, FN_AND))
    _connect(scoped_out, _pin(both, "A"))
    _connect(out(past), _pin(both, "B"))
    return out(both)


def _author_scope(ed, in_exec, as_weapon, held_out, cx, cy, height):
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
    left = keep(_node(ed, FN_SUB))
    _connect(cx, _pin(left, "A"))
    _connect(cy, _pin(left, "B"))
    left_out = out(left)
    right = keep(_node(ed, FN_ADD))
    _connect(cx, _pin(right, "A"))
    _connect(cy, _pin(right, "B"))
    bar_w = keep(_node(ed, FN_FMAX))
    _connect(left_out, _pin(bar_w, "A"))
    _set(bar_w, "B", 0.0)
    bar_w_out = out(bar_w)

    base = keep(ed.add_get_member_variable_node("BaseFOV", WEAPON_COMP_CLASS_PATH))
    _connect(as_weapon, _pin(base, "self"))
    now = keep(ed.add_get_member_variable_node("CurrentFOV", WEAPON_COMP_CLASS_PATH))
    _connect(as_weapon, _pin(now, "self"))
    zoom = keep(_node(ed, FN_DIV))
    _connect(out(base, "BaseFOV"), _pin(zoom, "A"))
    _connect(out(now, "CurrentFOV"), _pin(zoom, "B"))
    travelled = keep(_node(ed, FN_SUB))
    _connect(out(zoom), _pin(travelled, "A"))
    _set(travelled, "B", COMBAT.shoulder_zoom)

    # The denominator is this weapon's own zoom, not the config's scope
    # figure: the scope and the zoom factor are separate facts about a
    # weapon, and a 6x scope
    # would otherwise be fully opaque a third of the way in.
    ads = keep(ed.add_get_member_variable_node("AdsZoom", ITEM_CLASS_PATH))
    _connect(held_out, _pin(ads, "self"))
    span = keep(_node(ed, FN_SUB))
    _connect(out(ads, "AdsZoom"), _pin(span, "A"))
    _set(span, "B", COMBAT.shoulder_zoom)

    frac = keep(_node(ed, FN_DIV))
    _connect(out(travelled), _pin(frac, "A"))
    _connect(out(span), _pin(frac, "B"))
    alpha = keep(_node(ed, FN_FCLAMP))
    _connect(out(frac), _loose_pin(alpha, "Value"))
    _set(alpha, "Min", 0.0)
    _set(alpha, "Max", 1.0)
    alpha_out = out(alpha)

    ink = keep(_node(ed, FN_MAKE_COLOR))
    for ch in ("R", "G", "B"):
        _set(ink, ch, 0.0)
    _connect(alpha_out, _pin(ink, "A"))
    ink_out = out(ink)
    tint = keep(_node(ed, FN_MAKE_COLOR))
    for ch in ("R", "G", "B"):
        _set(tint, ch, 1.0)
    _connect(alpha_out, _pin(tint, "A"))

    flow = in_exec
    for at_x in (None, right):
        r = keep(_node(ed, FN_DRAW_RECT))
        if at_x is None:
            _set(r, "ScreenX", 0.0)
        else:
            _connect(out(at_x), _pin(r, "ScreenX"))
        _set(r, "ScreenY", 0.0)
        _connect(bar_w_out, _pin(r, "ScreenW"))
        _connect(height, _pin(r, "ScreenH"))
        _connect(ink_out, _pin(r, "RectColor"))
        _connect(flow, _pin(r, "execute"))
        flow = then(r)

    glass = keep(_draw_texture(ed, SCOPE_TEX))
    _connect(left_out, _pin(glass, "ScreenX"))
    _set(glass, "ScreenY", 0.0)
    _connect(height, _pin(glass, "ScreenW"))
    _connect(height, _pin(glass, "ScreenH"))
    _connect(out(tint), _pin(glass, "TintColor"))
    _connect(flow, _pin(glass, "execute"))

    ed.add_comment_to_nodes(
        "The sniper's scope. Drawn as a square of the viewport's height with "
        "the side strips blacked out, so the hole stays a circle at any "
        "aspect ratio, and faded on how far CurrentFOV has travelled toward "
        "the weapon's AdsZoom -- the glass and the zoom are one animation.",
        made)

    return then(glass)
