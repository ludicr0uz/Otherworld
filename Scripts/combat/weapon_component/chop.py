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
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
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


def _get(ed, name, x, y):
    return _pin(_at(ed.add_get_member_variable_node(name), x, y), name, is_input=False)


def _store(ed, var, exec_in, x, y, pin=None, literal=None):
    """var = a pin's value, or a literal; returns the exec pin after the Set."""
    s = _at(ed.add_set_member_variable_node(var), x, y)
    if pin is not None:
        _connect(pin, _pin(s, var))
    else:
        _set(s, var, literal)
    _connect(exec_in, _pin(s, "execute"))
    return BEL.find_then_pin(s)


def _author_chop(ed, brk, exec_in, x0, y0):
    """The blow struck something with no health: if an item that Chops is in
    hand and it is a tree, chip it, count it, and leave wood on the count.
    ``brk`` is the sweep's broken hit. Returns the stage's exits."""
    held = _get(ed, "Held", x0, y0 + 200)
    valid = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 200)
    _connect(held, _pin(valid, "Object"))
    armed = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(out(valid), _pin(armed, "Condition"))
    _connect(exec_in, _pin(armed, "execute"))
    chops, chops_n = _prop(ed, CHOPS_VAR, held, x0 + 480, y0 + 200)
    bites = _at(ed.add_branch_node(), x0 + 760, y0)
    _connect(chops, _pin(bites, "Condition"))
    _connect(BEL.find_then_pin(armed), _pin(bites, "execute"))

    struck = _loose_pin(brk, "HitComponent", is_input=False)
    which = _loose_pin(brk, "HitItem", is_input=False)
    cut = _loose_pin(brk, "ImpactPoint", is_input=False)
    tree = _at(_palette(ed, NODE_CAST_INSTANCED), x0 + 1040, y0)
    _connect(struck, _pin(tree, "Object"))
    _connect(BEL.find_then_pin(bites), _pin(tree, "execute"))

    # --- chips off the cut, as a bullet throws them ----------------------------
    face = _at(_node(ed, FN_ROT_FROM_X), x0 + 1040, y0 + 300)
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False), _pin(face, "X"))
    where = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 1300, y0 + 300)
    _connect(cut, _pin(where, "Location"))
    _connect(out(face), _pin(where, "Rotation"))
    _cls, chipped = _author_surface_impact(ed, where, BEL.find_then_pin(tree),
                                           x0 + 1300, y0)

    # --- the count, on this tree ----------------------------------------------
    same_comp = _at(_node(ed, FN_EQ_OBJECTS), x0 + 1900, y0 + 300)
    _connect(_get(ed, CHOP_TREE_VAR, x0 + 1660, y0 + 300), _pin(same_comp, "A"))
    _connect(struck, _pin(same_comp, "B"))
    same_item = _at(_node(ed, FN_EQ_II), x0 + 1900, y0 + 460)
    _connect(_get(ed, CHOP_ITEM_VAR, x0 + 1660, y0 + 460), _pin(same_item, "A"))
    _connect(which, _pin(same_item, "B"))
    same = _at(_node(ed, FN_AND), x0 + 2140, y0 + 380)
    _connect(out(same_comp), _pin(same, "A"))
    _connect(out(same_item), _pin(same, "B"))
    more = _at(_node(ed, FN_ADD_II), x0 + 1900, y0 + 620)
    _connect(_get(ed, CHOP_COUNT_VAR, x0 + 1660, y0 + 620), _pin(more, "A"))
    _set(more, "B", 1)
    count = _at(_node(ed, FN_SELECT_II), x0 + 2380, y0 + 460)
    _connect(out(more), _pin(count, "A"))
    _set(count, "B", 1)
    _connect(out(same), _pin(count, "bPickA"))
    # The count first: it is the one write that reads ChopTree and ChopItem.
    step = _store(ed, CHOP_COUNT_VAR, BEL.find_then_pin(chipped), x0 + 2640, y0,
                  pin=out(count))
    step = _store(ed, CHOP_TREE_VAR, step, x0 + 2900, y0, pin=struck)
    step = _store(ed, CHOP_ITEM_VAR, step, x0 + 3160, y0, pin=which)

    enough = _at(_node(ed, FN_GE_II), x0 + 3420, y0 + 300)
    _connect(_get(ed, CHOP_COUNT_VAR, x0 + 3160, y0 + 300), _pin(enough, "A"))
    _set(enough, "B", CHOPS_PER_WOOD)
    felled = _at(ed.add_branch_node(), x0 + 3660, y0)
    _connect(out(enough), _pin(felled, "Condition"))
    _connect(step, _pin(felled, "execute"))
    step = _store(ed, CHOP_COUNT_VAR, BEL.find_then_pin(felled), x0 + 3920, y0,
                  literal=0)

    # --- where it lands: beside the trunk, on the player's side ---------------
    back = _at(_node(ed, FN_SUB_VV), x0 + 3660, y0 + 500)
    _connect(_loose_pin(brk, "TraceStart", is_input=False), _pin(back, "A"))
    _connect(cut, _pin(back, "B"))
    parts = _at(_node(ed, FN_BREAK_VECTOR), x0 + 3900, y0 + 500)
    _connect(out(back), _pin(parts, "InVec"))
    flat = _at(_node(ed, FN_MAKE_VECTOR), x0 + 4140, y0 + 500)
    _connect(out(parts, "X"), _pin(flat, "X"))
    _connect(out(parts, "Y"), _pin(flat, "Y"))
    towards = _at(_node(ed, FN_NORMAL), x0 + 4380, y0 + 500)
    _connect(out(flat), _pin(towards, "A"))
    turn = _at(_node(ed, FN_RANDOM_FLOAT), x0 + 3900, y0 + 700)
    _set(turn, "Min", WOOD_SIDE_DEG[0])
    _set(turn, "Max", WOOD_SIDE_DEG[1])
    left = _at(_node(ed, FN_RANDOM_BOOL), x0 + 3900, y0 + 860)
    side = _at(_node(ed, FN_SELECT_FF), x0 + 4140, y0 + 860)
    _set(side, "A", 1.0)
    _set(side, "B", -1.0)
    _connect(out(left), _pin(side, "bPickA"))
    angle = _at(_node(ed, FN_MUL_FF), x0 + 4380, y0 + 760)
    _connect(out(turn), _pin(angle, "A"))
    _connect(out(side), _pin(angle, "B"))
    aside = _at(_node(ed, FN_ROTATE_ABOUT), x0 + 4620, y0 + 600)
    _connect(out(towards), _pin(aside, "InVect"))
    _connect(out(angle), _pin(aside, "AngleDeg"))
    _connect(_vec(ed, 0.0, 0.0, 1.0, x0 + 4380, y0 + 920), _pin(aside, "Axis"))
    # Multiply_VectorFloat's B is promoted to a vector: drive it with one.
    reach = _at(_node(ed, FN_MUL_VF), x0 + 4860, y0 + 600)
    _connect(out(aside), _pin(reach, "A"))
    r = WOOD_OUT_CM
    _connect(_vec(ed, r, r, r, x0 + 4620, y0 + 800), _pin(reach, "B"))
    spot = _at(_node(ed, FN_ADD_VV), x0 + 5100, y0 + 500)
    _connect(cut, _pin(spot, "A"))
    _connect(out(reach), _pin(spot, "B"))
    step = _store(ed, WOOD_SPOT_VAR, step, x0 + 5340, y0, pin=out(spot))

    # --- down onto the ground, and the wood itself ----------------------------
    spot_out = _get(ed, WOOD_SPOT_VAR, x0 + 5340, y0 + 300)
    below = _at(_node(ed, FN_ADD_VV), x0 + 5580, y0 + 400)
    _connect(spot_out, _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -WOOD_GROUND_CM, x0 + 5340, y0 + 520), _pin(below, "B"))
    floor = _at(_node(ed, FN_TRACE), x0 + 5820, y0)
    _connect(spot_out, _pin(floor, "Start"))
    _connect(out(below), _pin(floor, "End"))
    _trace_defaults(floor)
    _connect(step, _pin(floor, "execute"))
    ground = _at(_palette(ed, NODE_BREAK_HIT), x0 + 6100, y0 + 300)
    _connect(out(floor, "OutHit"), _loose_pin(ground, "Hit"))
    lift = _at(_node(ed, FN_ADD_VV), x0 + 6360, y0 + 300)
    _connect(_loose_pin(ground, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, WOOD_LIFT_CM, x0 + 6100, y0 + 620), _pin(lift, "B"))
    # No ground under it (the map's edge): it stays at the height of the cut.
    rests = _at(_node(ed, FN_SELECT_VECTOR), x0 + 6620, y0 + 300)
    _connect(out(lift), _pin(rests, "A"))
    _connect(spot_out, _pin(rests, "B"))
    _connect(out(floor), _pin(rests, "bPickA"))
    lie = _at(_node(ed, FN_RANDOM_FLOAT), x0 + 6360, y0 + 620)
    _set(lie, "Min", 0.0)
    _set(lie, "Max", 360.0)
    yaw = _at(_node(ed, FN_MAKE_ROT), x0 + 6620, y0 + 620)
    _connect(out(lie), _pin(yaw, "Yaw"))
    _set(yaw, "Pitch", WOOD_LIE_PITCH_DEG)
    at = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 6880, y0 + 300)
    _connect(out(rests), _pin(at, "Location"))
    _connect(out(yaw), _pin(at, "Rotation"))
    cls = _at(ed.add_get_member_variable_node(WOOD_CLASS_VAR), x0 + 6880, y0 + 180)
    wood = _at(_palette(ed, NODE_SPAWN), x0 + 7160, y0)
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
