"""The HUD's stamina bar: centred at the bottom of the screen, under the
inventory strip. Split out of build_graphics_menu.py, which calls
_author_stamina from DrawHUD and places the strip above it (SLOT_BOTTOM is
built from ST_BOTTOM + ST_H here).

It used to sit under the HP bar, top left. At the bottom it is next to the
thing a sprint is usually about -- the equipped gun and its ammunition -- and
in the eye line of anyone watching the reticle. Laid out off the viewport
size, like the strip, so it stays centred at any window size.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from graphics_menu.canvas import UI_FONT, _draw_texture

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"

FN_BREAK_V2D = "/Script/Engine.KismetMathLibrary.BreakVector2D"
FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_VIEWPORT = "/Script/UMG.WidgetLayoutLibrary.GetViewportSize"

# As wide as the inventory strip above it (five 84 px slots, four 7 px gaps;
# the verifier holds the two equal), so the pair reads as one block.
ST_W = 448.0
ST_H = 14.0
ST_BOTTOM = 22.0           # px between the bar's bottom edge and the screen's
ST_LABEL_LEFT = 40.0       # px from the "STA" label's left edge to the bar's
ST_LABEL_RISE = 4.0
ST_LABEL_SCALE = 1.1
COL_ST_FILL = "(R=0.320000,G=0.720000,B=0.880000,A=0.950000)"
COL_ST_SPENT = "(R=0.820000,G=0.560000,B=0.180000,A=0.950000)"
COL_ST_LABEL = "(R=0.620000,G=0.650000,B=0.700000,A=1.000000)"


def _author_origin(ed, x0, y0, keep):
    """The bar's top-left corner off the viewport: (W/2 - ST_W/2,
    H - ST_BOTTOM - ST_H). Returns the x and y output pins."""
    size = keep(_at(_node(ed, FN_VIEWPORT), x0, y0 + 700))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 240, y0 + 700))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))
    half = keep(_at(_node(ed, FN_MUL), x0 + 480, y0 + 700))
    _connect(_pin(wh, "X", is_input=False), _pin(half, "A"))
    _set(half, "B", 0.5)
    left = keep(_at(_node(ed, FN_SUB), x0 + 720, y0 + 700))
    _connect(_pin(half, "ReturnValue", is_input=False), _pin(left, "A"))
    _set(left, "B", ST_W / 2.0)
    top = keep(_at(_node(ed, FN_SUB), x0 + 720, y0 + 840))
    _connect(_pin(wh, "Y", is_input=False), _pin(top, "A"))
    _set(top, "B", ST_BOTTOM + ST_H)
    return (_pin(left, "ReturnValue", is_input=False),
            _pin(top, "ReturnValue", is_input=False))


def _author_stamina(ed, x0, y0, in_execs):
    """The sprint bar, centred at the bottom, under the inventory strip.

    Read off BP_WeaponComponent rather than off the health component: that is
    where sprint lives (it is the thing that has to refuse to fire while the key
    is held), and this HUD already casts to it for the inventory strip anyway.

    The fill changes colour while the key is down, which is the cheapest way to
    answer the only question a stamina bar is ever asked mid-fight -- "is it
    going down because I am sprinting, or did I stop and it is coming back?"
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 260))
    _set(pawn, "PlayerIndex", 0)
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 260))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)

    cast = keep(_at(_palette(ed, NODE_CAST_WEAPON), x0 + 500, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    def var(name, py):
        n = keep(_at(ed.add_get_member_variable_node(name, WEAPON_COMP_CLASS_PATH),
                     x0 + 760, py))
        _connect(as_weapon, _pin(n, "self"))
        return _pin(n, name, is_input=False)

    stamina = var("Stamina", y0 + 260)
    max_stamina = var("MaxStamina", y0 + 400)
    sprinting = var("Sprinting", y0 + 540)

    frac = keep(_at(_node(ed, FN_DIV), x0 + 1000, y0 + 320))
    _connect(stamina, _pin(frac, "A"))
    _connect(max_stamina, _pin(frac, "B"))
    fill_w = keep(_at(_node(ed, FN_MUL), x0 + 1200, y0 + 320))
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(fill_w, "A"))
    _set(fill_w, "B", ST_W)

    x_out, y_out = _author_origin(ed, x0 + 1400, y0, keep)

    back = keep(_draw_texture(ed, x0 + 760, y0, "T_UI_BarTrack", w=ST_W, h=ST_H))
    _connect(BEL.find_then_pin(cast), _pin(back, "execute"))

    tint = keep(_at(_node(ed, FN_SELECT_COLOR), x0 + 1000, y0 + 560))
    _set(tint, "A", COL_ST_SPENT)
    _set(tint, "B", COL_ST_FILL)
    _connect(sprinting, _pin(tint, "bPickA"))

    fill = keep(_draw_texture(ed, x0 + 1000, y0, "T_UI_Bar", w=ST_W, h=ST_H))
    _connect(_pin(fill_w, "ReturnValue", is_input=False), _pin(fill, "ScreenW"))
    _connect(_pin(tint, "ReturnValue", is_input=False), _pin(fill, "TintColor"))
    _connect(BEL.find_then_pin(back), _pin(fill, "execute"))
    for draw in (back, fill):
        _connect(x_out, _pin(draw, "ScreenX"))
        _connect(y_out, _pin(draw, "ScreenY"))

    label_x = keep(_at(_node(ed, FN_SUB), x0 + 2200, y0 + 300))
    _connect(x_out, _pin(label_x, "A"))
    _set(label_x, "B", ST_LABEL_LEFT)
    label_y = keep(_at(_node(ed, FN_SUB), x0 + 2200, y0 + 440))
    _connect(y_out, _pin(label_y, "A"))
    _set(label_y, "B", ST_LABEL_RISE)

    label = keep(_at(_node(ed, FN_DRAW_TEXT), x0 + 2440, y0))
    _set(label, "Text", "STA")
    _set(label, "TextColor", COL_ST_LABEL)
    _connect(_pin(label_x, "ReturnValue", is_input=False), _pin(label, "ScreenX"))
    _connect(_pin(label_y, "ReturnValue", is_input=False), _pin(label, "ScreenY"))
    _set(label, "Scale", ST_LABEL_SCALE)
    _set(label, "bScalePosition", "false")
    _set(label, "Font", UI_FONT)
    _connect(BEL.find_then_pin(fill), _pin(label, "execute"))

    ed.add_comment_to_nodes(
        "Stamina, centred under the inventory strip. The fill goes amber while "
        "the sprint key is held and back to blue while it refills, so a bar "
        "that is moving always says which way it is going.",
        made)
    return (BEL.find_then_pin(label), _pin(cast, "CastFailed", is_input=False))
