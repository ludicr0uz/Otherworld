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
from npc.graph import _log
from uebp.graph import (
    _assets, _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then)
from npc.paths import HIT_DAMAGE_VAR
from npc.tuned import tuned
from uebp.nodes.actor import FN_ACTOR_FORWARD, FN_GET_COMP
from uebp.nodes.math import FN_AND, FN_CLAMP, FN_DOT_VV, FN_GE_FF, FN_MUL_FF, FN_SUB_FF, INF
from uebp.nodes.palette import NODE_CAST_WEAPON
from combat.weapon_component import vars as WV

# Dot(player forward, unit bearing to the swinger) at the edge of the guard.
BLOCK_MIN_DOT = math.cos(math.radians(COMBAT.block_half_angle_deg))


def _author_block_check(ed, exec_in, player_out, bearing_out):
    """[player blocking AND swing from the front?] -> set HitDamage.

        exec_in --> cast player's BP_WeaponComponent
                      ok     --> [Blocking AND Dot(forward, bearing) >= cos]
                                   true  --> Stamina -= cost (floored at 0)
                                         --> HitDamage = TuneMeleeDamage * scale
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

    damage, damage_out = tuned(ed, "melee_damage")
    keep(damage)
    full = keep(ed.add_set_member_variable_node(HIT_DAMAGE_VAR))
    _connect(damage_out, _pin(full, HIT_DAMAGE_VAR))

    eas = _assets()
    if not (eas.does_asset_exist(WEAPON_COMP_BP_PATH)
            and eas.load_asset(WEAPON_COMP_BP_PATH)):
        _log(f"note: {WEAPON_COMP_BP_PATH} not found — the player cannot block")
        _connect(exec_in, _pin(full, "execute"))
        return made, [then(full)]

    comp = keep(_node(ed, FN_GET_COMP))
    _connect(player_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = keep(_palette(ed, NODE_CAST_WEAPON))
    _connect(out(comp), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    guard = keep(ed.add_get_member_variable_node(WV.Blocking, WEAPON_COMP_CLASS_PATH))
    _connect(as_wc, _pin(guard, "self"))
    facing = keep(_node(ed, FN_ACTOR_FORWARD))
    _connect(player_out, _pin(facing, "self"))
    dot = keep(_node(ed, FN_DOT_VV))
    _connect(out(facing), _pin(dot, "A"))
    _connect(bearing_out, _pin(dot, "B"))
    in_front = keep(_node(ed, FN_GE_FF))
    _connect(out(dot), _pin(in_front, "A"))
    _set(in_front, "B", round(BLOCK_MIN_DOT, 4))
    both = keep(_node(ed, FN_AND))
    _connect(out(guard, WV.Blocking), _pin(both, "A"))
    _connect(out(in_front), _pin(both, "B"))

    blocked = keep(ed.add_branch_node())
    _connect(out(both), _pin(blocked, "Condition"))
    _connect(then(cast), _pin(blocked, "execute"))

    stamina = keep(ed.add_get_member_variable_node(WV.Stamina, WEAPON_COMP_CLASS_PATH))
    _connect(as_wc, _pin(stamina, "self"))
    spent = keep(_node(ed, FN_SUB_FF))
    _connect(out(stamina, WV.Stamina), _pin(spent, "A"))
    _set(spent, "B", COMBAT.block_stamina_per_hit)
    floor = keep(_node(ed, FN_CLAMP))
    _connect(out(spent), _pin(floor, "Value"))
    _set(floor, "Min", 0.0)
    _set(floor, "Max", INF)
    pay = keep(ed.add_set_member_variable_node(WV.Stamina, WEAPON_COMP_CLASS_PATH))
    _connect(as_wc, _pin(pay, "self"))
    _connect(out(floor), _pin(pay, WV.Stamina))
    _connect(then(blocked), _pin(pay, "execute"))

    soft = keep(ed.add_set_member_variable_node(HIT_DAMAGE_VAR))
    less = keep(_node(ed, FN_MUL_FF))
    _connect(damage_out, _pin(less, "A"))
    _set(less, "B", COMBAT.block_damage_scale)
    _connect(out(less), _pin(soft, HIT_DAMAGE_VAR))
    _connect(then(pay), _pin(soft, "execute"))

    _connect(else_(blocked), _pin(full, "execute"))
    _connect(out(cast, "CastFailed"), _pin(full, "execute"))

    ed.add_comment_to_nodes(
        f"The player's guard: blocking and facing this wanderer (within "
        f"{COMBAT.block_half_angle_deg:.0f} deg), the swing does "
        f"{COMBAT.block_damage_scale:g}x its damage and costs "
        f"{COMBAT.block_stamina_per_hit:.0f} stamina. The player's own Tick "
        f"drops the guard when stamina reaches 0.",
        made)
    return made, [then(soft), then(full)]
