"""Between two swings: a hunting wanderer gives ground and steps round the
player, facing them, instead of standing where its last blow landed. The
numbers are forest_generator/npc_strafe.py's.

It is the head of the tree's Chase step (BT_Chase, npc/steps.py), not a step
of its own, so the tree and its task are untouched:

    BT_Chase -> [player near AND early in the swing's cooldown?]
       no  -> face the way it moves, drop the focus -> the chase (chase.py)
       yes -> [a swing since the last pick?]
                yes -> StrafeYaw = +/- random angle, StrafeDist = random
                       distance, StrafeFor = NextAttackTime
           -> focus on the player, turn with the focus, not the movement
           -> SimpleMoveToLocation(player + (pawn - player, flat and unit,
                                   turned StrafeYaw) * StrafeDist)
           -> the strafe speed

The point is measured from where the two stand on each pass, so a cooldown
long enough for several passes carries the wanderer on round the player, the
same way, rather than to one spot and a stop.

The pick is stored, not read off the random nodes each pass: they are pure,
and a second read is a second throw. NextAttackTime is the swing's own stamp
(melee.py), so the swing itself needs no new wire.

SimpleMoveToLocation, as the stroll is, because the level verifier counts
the chase's MoveToActor and MoveToLocation: one of each.
"""

from forest_generator.npc_strafe import (
    NPC_STRAFE_ENGAGE_CM, NPC_STRAFE_MAX_ANGLE_DEG, NPC_STRAFE_MAX_DISTANCE_CM,
    NPC_STRAFE_MIN_ANGLE_DEG, NPC_STRAFE_MIN_DISTANCE_CM, NPC_STRAFE_SHARE,
    NPC_STRAFE_SPEED_SCALE,
)
from npc.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ADD_VV, FN_AND, FN_CLEAR_FOCUS, FN_DISTANCE,
    FN_GET_CONTROLLER, FN_GET_PAWN, FN_GET_PLAYER_PAWN, FN_LE_FF, FN_LT_FF,
    FN_MAKE_VECTOR, FN_MUL_FF, FN_MUL_VV, FN_NE_FF, FN_NORMAL_2D,
    FN_RANDOM_BOOL, FN_RANDOM_FLOAT, FN_ROTATE_AXIS, FN_SELECT_FLOAT,
    FN_SET_FOCUS, FN_SIMPLE_MOVE, FN_SUB_VV, FN_TIME_SECONDS,
    NODE_CAST_CHARACTER,
)
from npc.paths import (
    CHARACTER_CLASS_PATH, MOVEMENT_CLASS_PATH, STRAFE_DIST_VAR, STRAFE_FOR_VAR,
    STRAFE_YAW_VAR,
)
from npc.patrol import _author_walk_speed
from npc.tuned import tuned

ORIENT_FLAG = "bOrientRotationToMovement"
DESIRED_FLAG = "bUseControllerDesiredRotation"


def declare_strafe_vars(ed):
    """All zero by default: StrafeFor 0 is NextAttackTime's own start, so
    nothing is picked until a swing has armed the cooldown."""
    for name in (STRAFE_YAW_VAR, STRAFE_DIST_VAR, STRAFE_FOR_VAR):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name("real")):
            raise RuntimeError(f"could not declare {name}")


def _author_facing(ed, exec_in, focus):
    """Which way the body turns while it walks: at ``focus`` (the player's
    pin), or with ``focus`` None the way it is going, as a chase and a stroll
    do. Returns ``(nodes, then_pin)``.

    The two movement flags are written on the pawn at run time, both ways,
    rather than on the character Blueprint: with orient-to-movement on, the
    focus turns only the controller, so a wanderer backing off would show the
    player its back.
    """
    pawn = _node(ed, FN_GET_PAWN)
    as_char = _palette(ed, NODE_CAST_CHARACTER)
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_char, "execute"))
    move = ed.add_get_member_variable_node("CharacterMovement", CHARACTER_CLASS_PATH)
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(move, "self"))
    made, last = [pawn, as_char, move], BEL.find_then_pin(as_char)
    for flag, on in ((ORIENT_FLAG, focus is None), (DESIRED_FLAG, focus is not None)):
        write = ed.add_set_member_variable_node(flag, MOVEMENT_CLASS_PATH)
        _connect(_pin(move, "CharacterMovement", is_input=False), _pin(write, "self"))
        _set(write, flag, "true" if on else "false")
        _connect(last, _pin(write, "execute"))
        made.append(write)
        last = BEL.find_then_pin(write)
    look = _node(ed, FN_CLEAR_FOCUS if focus is None else FN_SET_FOCUS)
    if focus is not None:
        _connect(focus, _pin(look, "NewFocus"))
    # A pawn that is not a Character has no such flags, and still carries on.
    for pin in (last, _pin(as_char, "CastFailed", is_input=False)):
        _connect(pin, _pin(look, "execute"))
    return made + [look], BEL.find_then_pin(look)


def _author_strafe(ed, exec_in, stock):
    """The head of the Chase step. ``exec_in`` is the step's exec pin and
    ``stock`` the creature's built run speed (patrol._author_walk_speed).

    Returns ``(nodes, to_chase, tails)``: the nodes made, the exec pin the
    chase hangs off, and the exec pins a pass that strafed instead ends on.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    # --- is the player close, and the last swing recent? ---------------------
    self_pawn = keep(_node(ed, FN_GET_PAWN))
    self_loc = keep(_node(ed, FN_ACTOR_LOC))
    _connect(out(self_pawn), _pin(self_loc, "self"))
    player = keep(_node(ed, FN_GET_PLAYER_PAWN))
    _set(player, "PlayerIndex", 0)
    player_loc = keep(_node(ed, FN_ACTOR_LOC))
    _connect(out(player), _pin(player_loc, "self"))
    gap = keep(_node(ed, FN_DISTANCE))
    _connect(out(self_loc), _pin(gap, "V1"))
    _connect(out(player_loc), _pin(gap, "V2"))
    near = keep(_node(ed, FN_LE_FF))
    _connect(out(gap), _pin(near, "A"))
    _set(near, "B", NPC_STRAFE_ENGAGE_CM)

    # Early is "the cooldown still has more than the run back in to go":
    # now + TuneMeleeInterval * (1 - share) < NextAttackTime.
    now = keep(_node(ed, FN_TIME_SECONDS))
    interval, interval_out = tuned(ed, "melee_interval_s")
    keep(interval)
    back_in = keep(_node(ed, FN_MUL_FF))
    _connect(interval_out, _pin(back_in, "A"))
    _set(back_in, "B", 1.0 - NPC_STRAFE_SHARE)
    by = keep(_node(ed, FN_ADD_FF))
    _connect(out(now), _pin(by, "A"))
    _connect(out(back_in), _pin(by, "B"))
    next_at = keep(ed.add_get_member_variable_node("NextAttackTime"))
    next_out = out(next_at, "NextAttackTime")
    early = keep(_node(ed, FN_LT_FF))
    _connect(out(by), _pin(early, "A"))
    _connect(next_out, _pin(early, "B"))
    both = keep(_node(ed, FN_AND))
    _connect(out(near), _pin(both, "A"))
    _connect(out(early), _pin(both, "B"))
    off = keep(ed.add_branch_node())
    _connect(out(both), _pin(off, "Condition"))
    _connect(exec_in, _pin(off, "execute"))

    # --- no: the chase, facing the way it runs -------------------------------
    ahead, to_chase = _author_facing(ed, [BEL.find_else_pin(off)], None)
    made.extend(ahead)

    # --- yes: one pick per swing ---------------------------------------------
    picked_for = keep(ed.add_get_member_variable_node(STRAFE_FOR_VAR))
    fresh = keep(_node(ed, FN_NE_FF))
    _connect(out(picked_for, STRAFE_FOR_VAR), _pin(fresh, "A"))
    _connect(next_out, _pin(fresh, "B"))
    pick = keep(ed.add_branch_node())
    _connect(out(fresh), _pin(pick, "Condition"))
    _connect(BEL.find_then_pin(off), _pin(pick, "execute"))

    angle = keep(_node(ed, FN_RANDOM_FLOAT))
    _set(angle, "Min", NPC_STRAFE_MIN_ANGLE_DEG)
    _set(angle, "Max", NPC_STRAFE_MAX_ANGLE_DEG)
    coin = keep(_node(ed, FN_RANDOM_BOOL))
    side = keep(_node(ed, FN_SELECT_FLOAT))
    _set(side, "A", 1.0)
    _set(side, "B", -1.0)
    _connect(out(coin), _pin(side, "bPickA"))
    yaw = keep(_node(ed, FN_MUL_FF))
    _connect(out(angle), _pin(yaw, "A"))
    _connect(out(side), _pin(yaw, "B"))
    set_yaw = keep(ed.add_set_member_variable_node(STRAFE_YAW_VAR))
    _connect(out(yaw), _pin(set_yaw, STRAFE_YAW_VAR))
    _connect(BEL.find_then_pin(pick), _pin(set_yaw, "execute"))

    far = keep(_node(ed, FN_RANDOM_FLOAT))
    _set(far, "Min", NPC_STRAFE_MIN_DISTANCE_CM)
    _set(far, "Max", NPC_STRAFE_MAX_DISTANCE_CM)
    set_dist = keep(ed.add_set_member_variable_node(STRAFE_DIST_VAR))
    _connect(out(far), _pin(set_dist, STRAFE_DIST_VAR))
    _connect(BEL.find_then_pin(set_yaw), _pin(set_dist, "execute"))
    set_for = keep(ed.add_set_member_variable_node(STRAFE_FOR_VAR))
    _connect(next_out, _pin(set_for, STRAFE_FOR_VAR))
    _connect(BEL.find_then_pin(set_dist), _pin(set_for, "execute"))

    # --- eyes on the player, whichever way the feet go -----------------------
    watch, watching = _author_facing(
        ed, [BEL.find_then_pin(set_for), BEL.find_else_pin(pick)], out(player))
    made.extend(watch)

    # --- the point: round the player from here, and out ----------------------
    away = keep(_node(ed, FN_SUB_VV))
    _connect(out(self_loc), _pin(away, "A"))
    _connect(out(player_loc), _pin(away, "B"))
    flat = keep(_node(ed, FN_NORMAL_2D))
    _connect(out(away), _pin(flat, "A"))
    up = keep(_node(ed, FN_MAKE_VECTOR))
    _set(up, "Z", 1.0)
    held_yaw = keep(ed.add_get_member_variable_node(STRAFE_YAW_VAR))
    turned = keep(_node(ed, FN_ROTATE_AXIS))
    _connect(out(flat), _pin(turned, "InVect"))
    _connect(out(held_yaw, STRAFE_YAW_VAR), _pin(turned, "AngleDeg"))
    _connect(out(up), _pin(turned, "Axis"))
    # Vector x float is a wildcard node; a vector of three of the same is not.
    held_dist = keep(ed.add_get_member_variable_node(STRAFE_DIST_VAR))
    reach = keep(_node(ed, FN_MAKE_VECTOR))
    for axis in ("X", "Y", "Z"):
        _connect(out(held_dist, STRAFE_DIST_VAR), _pin(reach, axis))
    offset = keep(_node(ed, FN_MUL_VV))
    _connect(out(turned), _pin(offset, "A"))
    _connect(out(reach), _pin(offset, "B"))
    point = keep(_node(ed, FN_ADD_VV))
    _connect(out(player_loc), _pin(point, "A"))
    _connect(out(offset), _pin(point, "B"))

    me = keep(_node(ed, FN_GET_CONTROLLER))
    _connect(out(self_pawn), _pin(me, "self"))
    step = keep(_node(ed, FN_SIMPLE_MOVE))
    _connect(out(me), _pin(step, "Controller"))
    _connect(out(point), _pin(step, "Goal"))
    _connect(watching, _pin(step, "execute"))

    eased, tails, _entry = _author_walk_speed(
        ed, [BEL.find_then_pin(step)], False, stock,
        scale=NPC_STRAFE_SPEED_SCALE)
    return made + eased, to_chase, tails
