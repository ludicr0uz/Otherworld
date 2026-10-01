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

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import (
    FN_ACTOR_LOC, FN_ALL_ACTORS, FN_DISTANCE, FN_GET_COMP, FN_GET_PLAYER_PAWN,
    FN_IS_VALID, FN_LESS_FF, MACRO_FOR_EACH, NODE_CAST_HEALTH,
)
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from graphics_menu.dev_guns import _branch, _call, _get, _out
from graphics_menu.loot_consts import LOOT_BEST_VAR, LOOT_TARGET_VAR
from loot.consts import LOOT_RADIUS

FN_NEQ_OO = "/Script/Engine.KismetMathLibrary.NotEqual_ObjectObject"
FN_COMP_LOC = "/Script/Engine.SceneComponent.K2_GetComponentLocation"
CHARACTER_CLASS_PATH = "/Script/Engine.Character"
MESH_CLASS_PATH = "/Script/Engine.SkeletalMeshComponent"


def put(ed, var, value, in_execs, x, y, made):
    """Set one of the HUD's own variables from a pin (or, with None, clear an
    object reference). Returns the then pin."""
    n = _at(ed.add_set_member_variable_node(var), x, y)
    made.append(n)
    if value is not None:
        _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return BEL.find_then_pin(n)


def author_find_body(ed, in_execs, x0, y0, made):
    """The scan (see the module docstring). Returns the exec tails."""
    unreal.load_asset(HEALTH_BP_PATH)      # the cast node exists only for a loaded class
    flow = put(ed, LOOT_TARGET_VAR, None, in_execs, x0, y0, made)
    best = _at(ed.add_set_member_variable_node(LOOT_BEST_VAR), x0 + 260, y0)
    made.append(best)
    _set(best, LOOT_BEST_VAR, LOOT_RADIUS)
    _connect(flow, _pin(best, "execute"))

    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0 + 260, y0 + 300, made, PlayerIndex=0))
    here, no_pawn = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 500, y0 + 300, made,
                                           Object=pawn)),
                            [BEL.find_then_pin(best)], x0 + 760, y0, made)
    everyone = _at(_node(ed, FN_ALL_ACTORS), x0 + 1020, y0)
    made.append(everyone)
    _pin(everyone, "ActorClass").set_pin_value(CHARACTER_CLASS_PATH)
    _connect(here, _pin(everyone, "execute"))
    loop = _at(ed.add_macro_node(MACRO_FOR_EACH), x0 + 1300, y0)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    made.append(loop)
    _connect(_pin(everyone, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(everyone), _loose_pin(loop, "Exec"))
    who = _loose_pin(loop, "ArrayElement", is_input=False)

    health = _call(ed, FN_GET_COMP, x0 + 1600, y0 + 300, made, self=who)
    _pin(health, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 1860, y0)
    made.append(cast)
    _connect(_out(health), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    comp = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    dead, _alive = _branch(ed, _get(ed, "Dead", x0 + 1860, y0 + 300, made,
                                    HEALTH_CLASS_PATH, comp),
                           [BEL.find_then_pin(cast)], x0 + 2140, y0, made)
    other, _self = _branch(ed, _out(_call(ed, FN_NEQ_OO, x0 + 2380, y0 + 440, made,
                                          A=who, B=pawn)),
                           [dead], x0 + 2640, y0, made)
    mesh = _call(ed, FN_GET_COMP, x0 + 2640, y0 + 300, made, self=who)
    _pin(mesh, "ComponentClass").set_pin_value(MESH_CLASS_PATH)
    shaped, _no_mesh = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 2900, y0 + 300, made,
                                              Object=_out(mesh))),
                               [other], x0 + 3160, y0, made)

    at = _call(ed, FN_COMP_LOC, x0 + 3160, y0 + 300, made, self=_out(mesh))
    me = _call(ed, FN_ACTOR_LOC, x0 + 3160, y0 + 440, made, self=pawn)
    far = _call(ed, FN_DISTANCE, x0 + 3420, y0 + 300, made, V1=_out(at), V2=_out(me))
    nearer, _further = _branch(ed, _out(_call(ed, FN_LESS_FF, x0 + 3660, y0 + 300, made,
                                              A=_out(far),
                                              B=_get(ed, LOOT_BEST_VAR, x0 + 3420,
                                                     y0 + 440, made))),
                               [shaped], x0 + 3920, y0, made)
    flow = put(ed, LOOT_BEST_VAR, _out(far), [nearer], x0 + 4180, y0, made)
    put(ed, LOOT_TARGET_VAR, comp, [flow], x0 + 4440, y0, made)
    return [_loose_pin(loop, "Completed", is_input=False), no_pawn]
