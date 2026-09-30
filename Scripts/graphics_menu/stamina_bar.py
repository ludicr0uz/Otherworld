"""DrawHUD: the stamina bar, centred at the bottom of WBP_HUD under the
inventory grid (the layout is wbp_hud.py's; this writes its fill).

Read off BP_WeaponComponent rather than off the health component: that is
where sprint lives (it is the thing that has to refuse to fire while the key
is held).

The fill changes colour while the key is down, which is the cheapest way to
answer the only question a stamina bar is ever asked mid-fight -- "is it
going down because I am sprinting, or did I stop and it is coming back?"
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from graphics_menu.ui_graph import part, set_percent
from graphics_menu.umg_consts import COL_ST_FILL, COL_ST_SPENT, STAMINA_BAR, WBP_HUD

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"

FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"
FN_SET_FILL = "/Script/UMG.ProgressBar.SetFillColorAndOpacity"


def _author_stamina(ed, x0, y0, in_execs):
    """StaminaBar = Stamina / MaxStamina, amber while sprinting. Returns the
    exec pins to go on from, the cast-failed one included."""
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

    frac = keep(_at(_node(ed, FN_DIV), x0 + 1000, y0 + 320))
    _connect(var("Stamina", y0 + 260), _pin(frac, "A"))
    _connect(var("MaxStamina", y0 + 400), _pin(frac, "B"))
    bar = part(ed, WBP_HUD, STAMINA_BAR, x0 + 1000, y0 + 500)
    filled = set_percent(ed, bar, _pin(frac, "ReturnValue", is_input=False),
                         [BEL.find_then_pin(cast)], x0 + 1500, y0)

    tint = keep(_at(_node(ed, FN_SELECT_COLOR), x0 + 1500, y0 + 560))
    _set(tint, "A", COL_ST_SPENT)
    _set(tint, "B", COL_ST_FILL)
    _connect(var("Sprinting", y0 + 540), _pin(tint, "bPickA"))
    fill = keep(_at(_node(ed, FN_SET_FILL), x0 + 1800, y0))
    _connect(bar, _pin(fill, "self"))
    _connect(_pin(tint, "ReturnValue", is_input=False), _pin(fill, "InColor"))
    _connect(filled, _pin(fill, "execute"))

    ed.add_comment_to_nodes(
        "Stamina, centred under the inventory grid. The fill goes amber while "
        "the sprint key is held and back to blue while it refills, so a bar "
        "that is moving always says which way it is going.",
        made)
    return (BEL.find_then_pin(fill), _pin(cast, "CastFailed", is_input=False))
