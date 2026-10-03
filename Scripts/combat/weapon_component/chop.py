"""Chopping a tree: a melee blow that lands on a tree, with an item that Chops
in hand (the axe), throws chips and, every CHOPS_PER_WOOD blows, leaves a
piece of wood (BP_Wood) on the ground beside the trunk.

It hangs off the blow's failed health cast (punch._author_blow's `scenery`),
which is where a sweep that struck something with no health goes:

    IsValid(Held) --> Held.Chops --> the hit component is an instanced mesh
      --> chips (BP_BulletImpact) at the cut
      --> ChopCount = (same tree as last time) ? ChopCount + 1 : 1
          ChopTree, ChopItem = this tree
      --> ChopCount >= CHOPS_PER_WOOD: ChopCount = 0, WoodSpot = the cut, reach
          towards the player and turned to a side; trace down from it; spawn
          WoodClass on the ground there

WHAT A TREE IS. The trees are planted as instances of per-cell instanced
meshes (forest_import/trees.py) and carry no tag; nothing else in a level is an
instanced mesh with collision (the grass has none), so "the sweep struck an
InstancedStaticMeshComponent" is the test. One tree is that component plus the
hit's Item, its instance index.

Held is read behind its own IsValid Branch, and Chops behind that: the blow
lands a moment after the press, and the hands may be empty by then.

Every value is read once or stored first. ChopCount is written before ChopTree
and ChopItem, because the pure "same tree" test would answer yes once they are.
WoodSpot holds the landing point because it is built from random draws and
read twice (the trace's two ends). The spawn lays the log flat, at a random
heading (BP_Wood stands on end in its own frame). The wood itself is BP_Wood's default
`Dropped`, so the spawn is the whole handover to the pick-up. Tuning is
chop_tuning.py.
"""

from combat.chop_tuning import (
    CHOP_COUNT_VAR, CHOP_ITEM_VAR, CHOP_TREE_VAR, CHOPS_PER_WOOD, CHOPS_VAR,
    WOOD_CLASS_VAR, WOOD_GROUND_CM, WOOD_LIE_PITCH_DEG, WOOD_LIFT_CM, WOOD_OUT_CM,
    WOOD_SIDE_DEG, WOOD_SPOT_VAR,
)
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from uebp.graph import out
from combat.nodes import (
    FN_ADD_II, FN_ADD_VV, FN_AND, FN_BREAK_VECTOR, FN_EQ_II, FN_IS_VALID,
    FN_MAKE_ROT, FN_MAKE_TRANSFORM, FN_MAKE_VECTOR, FN_MUL_FF, FN_MUL_VF, FN_NORMAL,
    FN_RANDOM_FLOAT, FN_ROT_FROM_X, FN_SELECT_FF, FN_SELECT_II, FN_SELECT_VECTOR,
    FN_SUB_VV, FN_TRACE, NODE_BREAK_HIT, NODE_SPAWN,
)
from combat.weapon_component.common import _prop, _trace_defaults
from combat.weapon_component.surface_impact import _author_surface_impact

NODE_CAST_INSTANCED = "Utilities|Casting|CastToInstancedStaticMeshComponent"
FN_EQ_OBJECTS = "/Script/Engine.KismetMathLibrary.EqualEqual_ObjectObject"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_RANDOM_BOOL = "/Script/Engine.KismetMathLibrary.RandomBool"
FN_ROTATE_ABOUT = "/Script/Engine.KismetMathLibrary.RotateAngleAxis"


def _get(ed, name):
    return _pin(ed.add_get_member_variable_node(name), name, is_input=False)


def _store(ed, var, exec_in, pin=None, literal=None):
    """var = a pin's value, or a literal; returns the exec pin after the Set."""
    s = ed.add_set_member_variable_node(var)
    if pin is not None:
        _connect(pin, _pin(s, var))
    else:
        _set(s, var, literal)
    _connect(exec_in, _pin(s, "execute"))
    return BEL.find_then_pin(s)


def _author_chop(ed, brk, exec_in):
    """The blow struck something with no health: if an item that Chops is in
    hand and it is a tree, chip it, count it, and leave wood on the count.
    ``brk`` is the sweep's broken hit. Returns the stage's exits."""
    held = _get(ed, "Held")
    valid = _node(ed, FN_IS_VALID)
    _connect(held, _pin(valid, "Object"))
    armed = ed.add_branch_node()
    _connect(out(valid), _pin(armed, "Condition"))
    _connect(exec_in, _pin(armed, "execute"))
    chops, chops_n = _prop(ed, CHOPS_VAR, held)
    bites = ed.add_branch_node()
    _connect(chops, _pin(bites, "Condition"))
    _connect(BEL.find_then_pin(armed), _pin(bites, "execute"))

    struck = _loose_pin(brk, "HitComponent", is_input=False)
    which = _loose_pin(brk, "HitItem", is_input=False)
    cut = _loose_pin(brk, "ImpactPoint", is_input=False)
    tree = _palette(ed, NODE_CAST_INSTANCED)
    _connect(struck, _pin(tree, "Object"))
    _connect(BEL.find_then_pin(bites), _pin(tree, "execute"))

    # --- chips off the cut, as a bullet throws them ----------------------------
    face = _node(ed, FN_ROT_FROM_X)
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False), _pin(face, "X"))
    where = _node(ed, FN_MAKE_TRANSFORM)
    _connect(cut, _pin(where, "Location"))
    _connect(out(face), _pin(where, "Rotation"))
    _cls, chipped = _author_surface_impact(ed, where, BEL.find_then_pin(tree))

    # --- the count, on this tree ----------------------------------------------
    same_comp = _node(ed, FN_EQ_OBJECTS)
    _connect(_get(ed, CHOP_TREE_VAR), _pin(same_comp, "A"))
    _connect(struck, _pin(same_comp, "B"))
    same_item = _node(ed, FN_EQ_II)
    _connect(_get(ed, CHOP_ITEM_VAR), _pin(same_item, "A"))
    _connect(which, _pin(same_item, "B"))
    same = _node(ed, FN_AND)
    _connect(out(same_comp), _pin(same, "A"))
    _connect(out(same_item), _pin(same, "B"))
    more = _node(ed, FN_ADD_II)
    _connect(_get(ed, CHOP_COUNT_VAR), _pin(more, "A"))
    _set(more, "B", 1)
    count = _node(ed, FN_SELECT_II)
    _connect(out(more), _pin(count, "A"))
    _set(count, "B", 1)
    _connect(out(same), _pin(count, "bPickA"))
    # The count first: it is the one write that reads ChopTree and ChopItem.
    step = _store(ed, CHOP_COUNT_VAR, BEL.find_then_pin(chipped), pin=out(count))
    step = _store(ed, CHOP_TREE_VAR, step, pin=struck)
    step = _store(ed, CHOP_ITEM_VAR, step, pin=which)

    enough = _node(ed, FN_GE_II)
    _connect(_get(ed, CHOP_COUNT_VAR), _pin(enough, "A"))
    _set(enough, "B", CHOPS_PER_WOOD)
    felled = ed.add_branch_node()
    _connect(out(enough), _pin(felled, "Condition"))
    _connect(step, _pin(felled, "execute"))
    step = _store(ed, CHOP_COUNT_VAR, BEL.find_then_pin(felled), literal=0)

    # --- where it lands: beside the trunk, on the player's side ---------------
    back = _node(ed, FN_SUB_VV)
    _connect(_loose_pin(brk, "TraceStart", is_input=False), _pin(back, "A"))
    _connect(cut, _pin(back, "B"))
    parts = _node(ed, FN_BREAK_VECTOR)
    _connect(out(back), _pin(parts, "InVec"))
    flat = _node(ed, FN_MAKE_VECTOR)
    _connect(out(parts, "X"), _pin(flat, "X"))
    _connect(out(parts, "Y"), _pin(flat, "Y"))
    towards = _node(ed, FN_NORMAL)
    _connect(out(flat), _pin(towards, "A"))
    turn = _node(ed, FN_RANDOM_FLOAT)
    _set(turn, "Min", WOOD_SIDE_DEG[0])
    _set(turn, "Max", WOOD_SIDE_DEG[1])
    left = _node(ed, FN_RANDOM_BOOL)
    side = _node(ed, FN_SELECT_FF)
    _set(side, "A", 1.0)
    _set(side, "B", -1.0)
    _connect(out(left), _pin(side, "bPickA"))
    angle = _node(ed, FN_MUL_FF)
    _connect(out(turn), _pin(angle, "A"))
    _connect(out(side), _pin(angle, "B"))
    aside = _node(ed, FN_ROTATE_ABOUT)
    _connect(out(towards), _pin(aside, "InVect"))
    _connect(out(angle), _pin(aside, "AngleDeg"))
    _connect(_vec(ed, 0.0, 0.0, 1.0), _pin(aside, "Axis"))
    # Multiply_VectorFloat's B is promoted to a vector: drive it with one.
    reach = _node(ed, FN_MUL_VF)
    _connect(out(aside), _pin(reach, "A"))
    r = WOOD_OUT_CM
    _connect(_vec(ed, r, r, r), _pin(reach, "B"))
    spot = _node(ed, FN_ADD_VV)
    _connect(cut, _pin(spot, "A"))
    _connect(out(reach), _pin(spot, "B"))
    step = _store(ed, WOOD_SPOT_VAR, step, pin=out(spot))

    # --- down onto the ground, and the wood itself ----------------------------
    spot_out = _get(ed, WOOD_SPOT_VAR)
    below = _node(ed, FN_ADD_VV)
    _connect(spot_out, _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -WOOD_GROUND_CM), _pin(below, "B"))
    floor = _node(ed, FN_TRACE)
    _connect(spot_out, _pin(floor, "Start"))
    _connect(out(below), _pin(floor, "End"))
    _trace_defaults(floor)
    _connect(step, _pin(floor, "execute"))
    ground = _palette(ed, NODE_BREAK_HIT)
    _connect(out(floor, "OutHit"), _loose_pin(ground, "Hit"))
    lift = _node(ed, FN_ADD_VV)
    _connect(_loose_pin(ground, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, WOOD_LIFT_CM), _pin(lift, "B"))
    # No ground under it (the map's edge): it stays at the height of the cut.
    rests = _node(ed, FN_SELECT_VECTOR)
    _connect(out(lift), _pin(rests, "A"))
    _connect(spot_out, _pin(rests, "B"))
    _connect(out(floor), _pin(rests, "bPickA"))
    lie = _node(ed, FN_RANDOM_FLOAT)
    _set(lie, "Min", 0.0)
    _set(lie, "Max", 360.0)
    yaw = _node(ed, FN_MAKE_ROT)
    _connect(out(lie), _pin(yaw, "Yaw"))
    _set(yaw, "Pitch", WOOD_LIE_PITCH_DEG)
    at = _node(ed, FN_MAKE_TRANSFORM)
    _connect(out(rests), _pin(at, "Location"))
    _connect(out(yaw), _pin(at, "Rotation"))
    cls = ed.add_get_member_variable_node(WOOD_CLASS_VAR)
    wood = _palette(ed, NODE_SPAWN)
    _connect(_pin(cls, WOOD_CLASS_VAR, is_input=False), _pin(wood, "Class"))
    _connect(out(at), _pin(wood, "SpawnTransform"))
    _set(wood, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(floor), _pin(wood, "execute"))

    ed.add_comment_to_nodes(
        "A melee blow that struck something with no health. With an item that "
        "Chops in hand (the axe) and an instanced mesh under the blow (a tree), "
        f"it throws chips, and every {CHOPS_PER_WOOD} blows on the one tree "
        f"leaves a piece of wood {WOOD_OUT_CM:.0f} cm from the cut, to one side "
        "of the player, set down on the ground. The wood is Dropped by default: "
        "E picks it up.",
        [armed, chops_n, bites, tree, chipped, felled, floor, wood])
    return (BEL.find_then_pin(wood), BEL.find_else_pin(armed),
            BEL.find_else_pin(bites), _loose_pin(tree, "CastFailed", is_input=False),
            BEL.find_else_pin(felled))
