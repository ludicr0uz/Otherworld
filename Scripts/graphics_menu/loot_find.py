"""The HUD Tick's search for a body to search: the nearest dead Character
other than the player, within LOOT_RADIUS of the player. Every body counts,
whether it carries anything or not: the player finds out by searching it.

    LootTarget = None, LootBest = LOOT_RADIUS
    ForEach Character:
        its BP_HealthComponent (cast), Dead, not the player's pawn, a mesh
        d = |player - mesh| < LootBest  ->  LootBest = d, LootTarget = it

Measured to the mesh, not the actor: a corpse's capsule stays where it died
while the ragdoll falls and rolls, and the ragdoll is what the player walks up
to. Every Character rather than BP_ForestWanderer so the HUD names no NPC asset;
the player has a health component too, and a dead player is nearest of all to
its own body, hence the pawn test.
"""

import unreal

from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set
from uebp.graph import out
from combat.nodes import (
    FN_ACTOR_LOC, FN_ALL_ACTORS, FN_DISTANCE, FN_GET_COMP, FN_GET_PLAYER_PAWN,
    FN_IS_VALID, FN_LESS_FF, MACRO_FOR_EACH, NODE_CAST_HEALTH,
)
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.loot_consts import LOOT_BEST_VAR, LOOT_TARGET_VAR
from loot.consts import LOOT_RADIUS

FN_NEQ_OO = "/Script/Engine.KismetMathLibrary.NotEqual_ObjectObject"
FN_COMP_LOC = "/Script/Engine.SceneComponent.K2_GetComponentLocation"
CHARACTER_CLASS_PATH = "/Script/Engine.Character"
MESH_CLASS_PATH = "/Script/Engine.SkeletalMeshComponent"


def put(ed, var, value, in_execs, made):
    """Set one of the HUD's own variables from a pin (or, with None, clear an
    object reference). Returns the then pin."""
    n = ed.add_set_member_variable_node(var)
    made.append(n)
    if value is not None:
        _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return BEL.find_then_pin(n)


def author_find_body(ed, in_execs, made):
    """The scan (see the module docstring). Returns the exec tails."""
    unreal.load_asset(HEALTH_BP_PATH)      # the cast node exists only for a loaded class
    flow = put(ed, LOOT_TARGET_VAR, None, in_execs, made)
    best = ed.add_set_member_variable_node(LOOT_BEST_VAR)
    made.append(best)
    _set(best, LOOT_BEST_VAR, LOOT_RADIUS)
    _connect(flow, _pin(best, "execute"))

    pawn = out(_call(ed, FN_GET_PLAYER_PAWN, made, PlayerIndex=0))
    here, no_pawn = _branch(ed, out(_call(ed, FN_IS_VALID, made,
                                           Object=pawn)),
                            [BEL.find_then_pin(best)], made)
    everyone = _node(ed, FN_ALL_ACTORS)
    made.append(everyone)
    _pin(everyone, "ActorClass").set_pin_value(CHARACTER_CLASS_PATH)
    _connect(here, _pin(everyone, "execute"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(_pin(everyone, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(everyone), _loose_pin(loop, "Exec"))
    who = _loose_pin(loop, "ArrayElement", is_input=False)

    health = _call(ed, FN_GET_COMP, made, self=who)
    _pin(health, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = _palette(ed, NODE_CAST_HEALTH)
    made.append(cast)
    _connect(out(health), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    comp = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    dead, _alive = _branch(ed, _get(ed, "Dead", made,
                                    HEALTH_CLASS_PATH, comp),
                           [BEL.find_then_pin(cast)], made)
    other, _self = _branch(ed, out(_call(ed, FN_NEQ_OO, made, A=who, B=pawn)), [dead], made)
    mesh = _call(ed, FN_GET_COMP, made, self=who)
    _pin(mesh, "ComponentClass").set_pin_value(MESH_CLASS_PATH)
    shaped, _no_mesh = _branch(ed, out(_call(ed, FN_IS_VALID, made,
                                              Object=out(mesh))),
                               [other], made)

    at = _call(ed, FN_COMP_LOC, made, self=out(mesh))
    me = _call(ed, FN_ACTOR_LOC, made, self=pawn)
    far = _call(ed, FN_DISTANCE, made, V1=out(at), V2=out(me))
    nearer, _further = _branch(ed, out(_call(ed, FN_LESS_FF, made,
                                              A=out(far),
                                              B=_get(ed, LOOT_BEST_VAR, made))),
                               [shaped], made)
    flow = put(ed, LOOT_BEST_VAR, out(far), [nearer], made)
    put(ed, LOOT_TARGET_VAR, comp, [flow], made)
    return [_loose_pin(loop, "Completed", is_input=False), no_pawn]
