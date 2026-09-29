"""The player's guard, as the swing sees it: how much of this hit lands, and
what taking it on the guard costs the player's stamina.

The stance is the player's (combat/weapon_component/block.py writes Blocking on
BP_WeaponComponent every frame). It is resolved here because the swing is the
one place the damage and the direction it comes from exist together -- the
melee writes Health straight onto the player's component, and there is no
damage event on the player's side to intercept.
"""

import math

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import COMBAT
from forest_generator.npc_placement import NPC_MELEE_DAMAGE
from npc.graph import (
    _asset_sub, _at, BEL, _connect, _log, _loose_pin, _node, _palette, _pin,
    _set,
)
from npc.nodes import (
    FN_AND, FN_CLAMP, FN_DOT_VV, FN_FORWARD, FN_GET_COMP, FN_GE_FF, FN_SUB_FF,
    NODE_CAST_WEAPON,
)
from npc.paths import HIT_DAMAGE_VAR, INF

# The damage literals the two arms write. The unblocked one is the plain
# NPC_MELEE_DAMAGE, which the level verifier also looks for.
BLOCKED_DAMAGE = NPC_MELEE_DAMAGE * COMBAT.block_damage_scale
# Dot(player forward, unit bearing to the swinger) at the edge of the guard.
BLOCK_MIN_DOT = math.cos(math.radians(COMBAT.block_half_angle_deg))


def _author_block_check(ed, exec_in, player_out, bearing_out, x0, y0):
    """[player blocking AND swing from the front?] -> set HitDamage.

        exec_in --> cast player's BP_WeaponComponent
                      ok     --> [Blocking AND Dot(forward, bearing) >= cos]
                                   true  --> Stamina -= cost (floored at 0)
                                         --> HitDamage = damage * scale
                                   false --> HitDamage = damage
                      failed ----------------> HitDamage = damage

    ``bearing_out`` is the unit vector from the player to this wanderer, the
    same one the melee stores as LastHitFrom. HitDamage is a controller
    variable rather than a SelectFloat into the Health write because the
    cast-failed arm has no component to read Blocking off.

    Returns ``(nodes, tails)``: the exec pins that have set HitDamage. When
    BP_WeaponComponent does not exist, every hit is unblocked.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    full = keep(_at(ed.add_set_member_variable_node(HIT_DAMAGE_VAR), x0 + 1440, y0 + 300))
    _set(full, HIT_DAMAGE_VAR, NPC_MELEE_DAMAGE)

    eas = _asset_sub()
    if not (eas.does_asset_exist(WEAPON_COMP_BP_PATH)
            and eas.load_asset(WEAPON_COMP_BP_PATH)):
        _log(f"note: {WEAPON_COMP_BP_PATH} not found — the player cannot block")
        _connect(exec_in, _pin(full, "execute"))
        return made, [BEL.find_then_pin(full)]

    comp = keep(_at(_node(ed, FN_GET_COMP), x0, y0 + 240))
    _connect(player_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = keep(_at(_palette(ed, NODE_CAST_WEAPON), x0 + 240, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    guard = keep(_at(ed.add_get_member_variable_node("Blocking", WEAPON_COMP_CLASS_PATH),
                     x0 + 480, y0 + 240))
    _connect(as_wc, _pin(guard, "self"))
    facing = keep(_at(_node(ed, FN_FORWARD), x0 + 240, y0 + 400))
    _connect(player_out, _pin(facing, "self"))
    dot = keep(_at(_node(ed, FN_DOT_VV), x0 + 480, y0 + 400))
    _connect(_pin(facing, "ReturnValue", is_input=False), _pin(dot, "A"))
    _connect(bearing_out, _pin(dot, "B"))
    in_front = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 400))
    _connect(_pin(dot, "ReturnValue", is_input=False), _pin(in_front, "A"))
    _set(in_front, "B", round(BLOCK_MIN_DOT, 4))
    both = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 240))
    _connect(_pin(guard, "Blocking", is_input=False), _pin(both, "A"))
    _connect(_pin(in_front, "ReturnValue", is_input=False), _pin(both, "B"))

    blocked = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(both, "ReturnValue", is_input=False), _pin(blocked, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(blocked, "execute"))

    stamina = keep(_at(ed.add_get_member_variable_node("Stamina", WEAPON_COMP_CLASS_PATH),
                       x0 + 720, y0 - 240))
    _connect(as_wc, _pin(stamina, "self"))
    spent = keep(_at(_node(ed, FN_SUB_FF), x0 + 960, y0 - 240))
    _connect(_pin(stamina, "Stamina", is_input=False), _pin(spent, "A"))
    _set(spent, "B", COMBAT.block_stamina_per_hit)
    floor = keep(_at(_node(ed, FN_CLAMP), x0 + 1200, y0 - 240))
    _connect(_pin(spent, "ReturnValue", is_input=False), _pin(floor, "Value"))
    _set(floor, "Min", 0.0)
    _set(floor, "Max", INF)
    pay = keep(_at(ed.add_set_member_variable_node("Stamina", WEAPON_COMP_CLASS_PATH),
                   x0 + 960, y0))
    _connect(as_wc, _pin(pay, "self"))
    _connect(_pin(floor, "ReturnValue", is_input=False), _pin(pay, "Stamina"))
    _connect(BEL.find_then_pin(blocked), _pin(pay, "execute"))

    soft = keep(_at(ed.add_set_member_variable_node(HIT_DAMAGE_VAR), x0 + 1440, y0))
    _set(soft, HIT_DAMAGE_VAR, BLOCKED_DAMAGE)
    _connect(BEL.find_then_pin(pay), _pin(soft, "execute"))

    _connect(BEL.find_else_pin(blocked), _pin(full, "execute"))
    _connect(_pin(cast, "CastFailed", is_input=False), _pin(full, "execute"))

    ed.add_comment_to_nodes(
        f"The player's guard: blocking and facing this wanderer (within "
        f"{COMBAT.block_half_angle_deg:.0f} deg), the swing does "
        f"{BLOCKED_DAMAGE:.1f} instead of {NPC_MELEE_DAMAGE:.0f} and costs "
        f"{COMBAT.block_stamina_per_hit:.0f} stamina. The player's own Tick "
        f"drops the guard when stamina reaches 0.",
        made)
    return made, [BEL.find_then_pin(soft), BEL.find_then_pin(full)]
