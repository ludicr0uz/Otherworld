"""DrawHUD: the stamina bar, beside HP under the inventory grid of WBP_HUD
(the layout is wbp_hud.py's; this writes its fill, and blinks it when low).

Read off BP_WeaponComponent rather than off the health component: that is
where sprint lives (it is the thing that has to refuse to fire while the key
is held).

The fill changes colour while the key is down, which is the cheapest way to
answer the only question a stamina bar is ever asked mid-fight -- "is it
going down because I am sprinting, or did I stop and it is coming back?"
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from graphics_menu.hud_flash import author_flash
from graphics_menu.ui_graph import part, set_percent
from graphics_menu.umg_consts import (
    COL_ST_FILL, COL_ST_SPENT, STAMINA_BAR, ST_GROUP, WBP_HUD,
)
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.math import FN_DIV_FF, FN_SELECT_COLOR
from uebp.nodes.palette import NODE_CAST_WEAPON
from uebp.nodes.system import FN_GET_PLAYER_PAWN
from uebp.nodes.umg import FN_SET_FILL

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"


def _author_stamina(ed, in_execs):
    """StaminaBar = Stamina / MaxStamina, amber while sprinting. Returns the
    exec pins to go on from, the cast-failed one included."""
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_node(ed, FN_GET_PLAYER_PAWN))
    _set(pawn, "PlayerIndex", 0)
    comp = keep(_node(ed, FN_GET_COMP))
    _connect(out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)

    cast = keep(_palette(ed, NODE_CAST_WEAPON))
    _connect(out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    def var(name):
        n = keep(ed.add_get_member_variable_node(name, WEAPON_COMP_CLASS_PATH))
        _connect(as_weapon, _pin(n, "self"))
        return out(n, name)

    frac = keep(_node(ed, FN_DIV_FF))
    _connect(var("Stamina"), _pin(frac, "A"))
    _connect(var("MaxStamina"), _pin(frac, "B"))
    bar = part(ed, WBP_HUD, STAMINA_BAR)
    filled = set_percent(ed, bar, out(frac), [then(cast)])

    tint = keep(_node(ed, FN_SELECT_COLOR))
    _set(tint, "A", COL_ST_SPENT)
    _set(tint, "B", COL_ST_FILL)
    _connect(var("Sprinting"), _pin(tint, "bPickA"))
    fill = keep(_node(ed, FN_SET_FILL))
    _connect(bar, _pin(fill, "self"))
    _connect(out(tint), _pin(fill, "InColor"))
    _connect(filled, _pin(fill, "execute"))

    flashed = author_flash(ed, part(ed, WBP_HUD, ST_GROUP), out(frac), [then(fill)])

    ed.add_comment_to_nodes(
        "Stamina, beside HP under the inventory grid. The fill goes amber while "
        "the sprint key is held and back to blue while it refills, so a bar "
        "that is moving always says which way it is going.",
        made)
    return (flashed, out(cast, "CastFailed"))
