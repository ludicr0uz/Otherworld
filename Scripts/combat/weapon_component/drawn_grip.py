"""What the drawn MetaHuman's fitted hands are weighed by (drawn_grip_graph.py
lays them over its fingers and copies these on its update):

    GripGun   = 3 x the place of HandPose in GripPoses (0 with none of them)
    GripRight = HandPose is one of GripPoses
    GripLeft  -> that, AND (NOT Lowered OR carried) AND NOT Searching,
                 x (1 - ReloadHand)                                    eased
    GripCarry -> carried (carry_weights' CarryPose target)              eased

HandPose is the pose the hand's item is held in, on every machine's copy
(look.py), and a fitted gun's is its own (finger_pose.clip_for), so it names
the gun: GripPoses holds the five in drawn_grip_consts.GUNS' order, and a
gun's three frames start at its place x FRAMES_PER_GUN. The right hand is on
the gun whenever the gun is in it (the gun is rigid in the hand). The left is
on it raised, down the sights and in a long gun's carry; it lets go of a
lowered pistol (held in one hand), for a reload's clip (ReloadHand, as the
support hand's IK does: support_hand.py) and over a searched body.
GripCarry chooses the left's carry frame, the anim graph's SightBlend the
sights' one.

A dedicated server writes none of them: it draws no MetaHuman.
"""

from combat.carry_pose_consts import CARRY_BLEND_SPEED, CARRY_POSE
from combat.carry_tuning import LOWERED_VAR
from combat.drawn_grip_consts import FRAMES_PER_GUN
from combat.drawn_grip_vars import GripCarry, GripGun, GripLeft, GripPoses, GripRight
from combat.weapon_component import vars as WV
from combat.weapon_component.carry_weights import carry_targets
from combat.weapon_component.look_vars import HandPose
from combat.weapon_component.slot_nodes import not_, op
from uebp.g import _G
from uebp.graph import _set, out
from uebp.nodes.array import FN_ARR_FIND
from uebp.nodes.math import (
    FN_AND, FN_BOOL_TO_FLOAT, FN_GE_II, FN_INTERP_FF, FN_INT_TO_FLOAT, FN_MAX_II, FN_MUL_FF,
    FN_MUL_II, FN_OR, FN_SUB_FF,
)
from uebp.nodes.system import FN_DELTA_SECONDS, FN_IS_DEDICATED_SERVER


def _eased(g, var, target):
    step = g.call(FN_INTERP_FF, Current=g.get(var), Target=target,
                  DeltaTime=out(g.call(FN_DELTA_SECONDS)))
    _set(step, "InterpSpeed", CARRY_BLEND_SPEED)
    return out(step)


def _author_drawn_grip(ed, exec_ins):
    """Write the four. Returns the exec pins to carry on from. After
    ReloadHand and SightBlend are written (support_hand.py)."""
    g = _G(ed)
    on_server, on_screen = g.branch(out(g.call(FN_IS_DEDICATED_SERVER)), exec_ins)
    at = out(g.call(FN_ARR_FIND, TargetArray=g.get(GripPoses), ItemToFind=g.get(HandPose)))
    found = op(g, FN_GE_II, at, 0)
    first = op(g, FN_MUL_II, op(g, FN_MAX_II, at, 0), FRAMES_PER_GUN)
    carried = carry_targets(ed)[CARRY_POSE]
    held = op(g, FN_OR, not_(g, g.get(LOWERED_VAR)), carried)
    left = op(g, FN_AND, op(g, FN_AND, found, held), not_(g, g.get(WV.Searching)))
    free = g.call(FN_SUB_FF, B=g.get(WV.ReloadHand))
    _set(free, "A", 1.0)
    left = op(g, FN_MUL_FF, out(g.call(FN_BOOL_TO_FLOAT, InBool=left)), out(free))
    tail = on_screen
    for var, value in (
            (GripGun, out(g.call(FN_INT_TO_FLOAT, InInt=first))),
            (GripRight, out(g.call(FN_BOOL_TO_FLOAT, InBool=found))),
            (GripLeft, _eased(g, GripLeft, left)),
            (GripCarry, _eased(g, GripCarry, out(g.call(FN_BOOL_TO_FLOAT, InBool=carried))))):
        tail = g.put(var, value, [tail])
    ed.add_comment_to_nodes(
        "The drawn MetaHuman's fitted hands (Scripts/combat/weapon_component/drawn_grip.py): "
        f"which gun's frames ({GripGun}), the right hand's weight, the left's (on the gun "
        f"raised, sighted or carried, not reloading) and the carry's frame. The drawn "
        "body's anim graph copies them on its update. Not on a dedicated server.", g.made)
    return (tail, on_server)
