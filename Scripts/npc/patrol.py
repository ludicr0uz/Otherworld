"""Patrolling: the once-per-life setup (centre, run speed, stroll speed) and
the step that sends a wanderer to a new point inside its circle now and then.
"""

from forest_generator.npc_agro import PATROL_ACCEPT_FRACTION, PATROL_ACCEPT_SLACK_CM
from npc.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_DISTANCE, FN_DIV_FF, FN_GET_CONTROLLER, FN_GET_PAWN,
    FN_GE_FF, FN_LE_FF, FN_MUL_FF, FN_RANDOM_FLOAT, FN_RANDOM_REACHABLE,
    FN_SIMPLE_MOVE, FN_TIME_SECONDS, NODE_CAST_CHARACTER,
)
from npc.paths import (
    CHARACTER_CLASS_PATH, MOVEMENT_CLASS_PATH, NEXT_PATROL_VAR,
    PATROL_HOME_VAR, PATROL_READY_VAR, PATROL_TARGET_VAR, RUN_SPEED_VAR,
)
from npc.tuned import tuned


def _author_walk_speed(ed, exec_in, stroll, stock, x0, y0, scale=None):
    """MaxWalkSpeed = RunSpeed * TuneRunSpeed / ``stock`` [* TunePatrolSpeed]
    on the possessed Character: the run, or with ``stroll`` the patrol walk,
    or with ``scale`` that fraction of the run (the step between two swings,
    npc/strafe.py).

    RunSpeed is what the pawn had at setup (this creature and the level's
    per-instance gait); ``stock`` is the creature's built run speed, so the
    ratio is the tuning, and the gait survives it. Written by the Chase and
    Stroll steps on every pass, so a tuned speed lands within half a second.

    Returns ``(nodes, then_pins, entry)``: the write and the cast's failure
    pin (a pawn that is somehow not a Character still carries on), and the
    exec input, for a caller that wires in later. Always from the stored
    RunSpeed, never from the current MaxWalkSpeed: scaling what is already
    there would compound every time it ran.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 300))
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 240, y0))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_char, "execute"))
    move = keep(_at(ed.add_get_member_variable_node("CharacterMovement",
                                                    CHARACTER_CLASS_PATH),
                    x0 + 480, y0 + 300))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(move, "self"))
    run = keep(_at(ed.add_get_member_variable_node(RUN_SPEED_VAR), x0 + 480, y0 + 440))
    want, want_out = tuned(ed, "run_speed_cms", x0 + 240, y0 + 580)
    keep(want)
    ratio = keep(_at(_node(ed, FN_DIV_FF), x0 + 480, y0 + 580))
    _connect(want_out, _pin(ratio, "A"))
    _set(ratio, "B", stock)
    scaled = keep(_at(_node(ed, FN_MUL_FF), x0 + 720, y0 + 440))
    _connect(_pin(run, RUN_SPEED_VAR, is_input=False), _pin(scaled, "A"))
    _connect(_pin(ratio, "ReturnValue", is_input=False), _pin(scaled, "B"))
    speed = _pin(scaled, "ReturnValue", is_input=False)
    if stroll:
        walk, walk_out = tuned(ed, "patrol_speed_scale", x0 + 720, y0 + 580)
        keep(walk)
        slowed = keep(_at(_node(ed, FN_MUL_FF), x0 + 960, y0 + 440))
        _connect(speed, _pin(slowed, "A"))
        _connect(walk_out, _pin(slowed, "B"))
        speed = _pin(slowed, "ReturnValue", is_input=False)
    if scale is not None:
        eased = keep(_at(_node(ed, FN_MUL_FF), x0 + 960, y0 + 440))
        _connect(speed, _pin(eased, "A"))
        _set(eased, "B", scale)
        speed = _pin(eased, "ReturnValue", is_input=False)
    write = keep(_at(ed.add_set_member_variable_node("MaxWalkSpeed", MOVEMENT_CLASS_PATH),
                     x0 + 1200, y0))
    _connect(_pin(move, "CharacterMovement", is_input=False), _pin(write, "self"))
    _connect(speed, _pin(write, "MaxWalkSpeed"))
    _connect(BEL.find_then_pin(as_char), _pin(write, "execute"))
    return (made, [BEL.find_then_pin(write), _pin(as_char, "CastFailed", is_input=False)],
            _pin(as_char, "execute"))


def _author_patrol_setup(ed, exec_in, x0, y0):
    """Once per life, on the first heartbeat with a pawn:

        PatrolHome = where the pawn is      (the centre of its circle)
        RunSpeed   = its MaxWalkSpeed       (this creature, this gait)
        PatrolReady = true

    The speeds themselves are written by the Stroll and Chase steps
    (_author_walk_speed), every pass, from RunSpeed and the Tune variables.

    The centre is where it SPAWNED, so a respawned wanderer patrols about its
    new spot rather than the dead one's. The run speed is read off the pawn
    rather than recomputed, because it is per creature (the wendigo's 1.15x)
    and per instance (the level generator's gait variance), and the pawn is
    the only thing that has both. Returns ``(nodes, then_pin)``.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    ready = keep(_at(ed.add_get_member_variable_node(PATROL_READY_VAR), x0, y0 + 300))
    first = keep(_at(ed.add_branch_node(), x0 + 240, y0))
    _connect(_pin(ready, PATROL_READY_VAR, is_input=False), _pin(first, "Condition"))
    _connect(exec_in, _pin(first, "execute"))

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0 + 240, y0 + 440))
    where = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 480, y0 + 440))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(where, "self"))
    home = keep(_at(ed.add_set_member_variable_node(PATROL_HOME_VAR), x0 + 480, y0))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(home, PATROL_HOME_VAR))
    _connect(BEL.find_else_pin(first), _pin(home, "execute"))

    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 740, y0))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(home), _pin(as_char, "execute"))
    move = keep(_at(ed.add_get_member_variable_node("CharacterMovement",
                                                    CHARACTER_CLASS_PATH),
                    x0 + 980, y0 + 300))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(move, "self"))
    speed = keep(_at(ed.add_get_member_variable_node("MaxWalkSpeed", MOVEMENT_CLASS_PATH),
                     x0 + 1220, y0 + 300))
    _connect(_pin(move, "CharacterMovement", is_input=False), _pin(speed, "self"))
    cache = keep(_at(ed.add_set_member_variable_node(RUN_SPEED_VAR), x0 + 1220, y0))
    _connect(_pin(speed, "MaxWalkSpeed", is_input=False), _pin(cache, RUN_SPEED_VAR))
    _connect(BEL.find_then_pin(as_char), _pin(cache, "execute"))

    mark = keep(_at(ed.add_set_member_variable_node(PATROL_READY_VAR), x0 + 2700, y0))
    _set(mark, PATROL_READY_VAR, "true")
    # A pawn that is not a Character still gets a centre and is marked ready,
    # or it would retry the setup on every heartbeat forever.
    for pin in (BEL.find_then_pin(cache), _pin(as_char, "CastFailed", is_input=False)):
        _connect(pin, _pin(mark, "execute"))

    out = keep(_at(ed.add_branch_node(), x0 + 2960, y0))
    _set(out, "Condition", "true")
    _connect(BEL.find_then_pin(mark), _pin(out, "execute"))
    _connect(BEL.find_then_pin(first), _pin(out, "execute"))
    return made, BEL.find_then_pin(out)


def _author_patrol_step(ed, exec_in, rest_in, x0, y0):
    """Every so often, stroll to a random reachable point inside the circle.

        [now >= NextPatrolTime?]
          yes -> PatrolTarget = GetRandomReachablePointInRadius(Home, radius)
              -> NextPatrolTime = now + random(repick_min, repick_max)
              -> [PatrolTarget inside the circle?]  yes -> SimpleMoveToLocation
          every exit -> rest_in (the heartbeat's Delay)

    The query is PURE and re-runs once per output read, so only RandomLocation
    is read, and straight into PatrolTarget; the move and the guard read the
    stored variable. Its ReturnValue is deliberately not read -- that would be
    a second, different random query. The guard stands in for it: on failure
    the query hands back the centre (harmless) or, with no navigation system,
    the zero vector, which is the player's spawn -- see
    PATROL_ACCEPT_FRACTION in npc_agro.py.

    The re-pick interval includes the walk, so the pause at each point is
    whatever the walk left over; a far point may be abandoned half way for
    the next one, which reads as a change of mind rather than a bug.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0, y0 + 300))
    now_out = _pin(now, "ReturnValue", is_input=False)
    due_at = keep(_at(ed.add_get_member_variable_node(NEXT_PATROL_VAR), x0, y0 + 440))
    due = keep(_at(_node(ed, FN_GE_FF), x0 + 240, y0 + 300))
    _connect(now_out, _pin(due, "A"))
    _connect(_pin(due_at, NEXT_PATROL_VAR, is_input=False), _pin(due, "B"))
    time_to = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(due, "ReturnValue", is_input=False), _pin(time_to, "Condition"))
    for pin in exec_in:
        _connect(pin, _pin(time_to, "execute"))

    home = keep(_at(ed.add_get_member_variable_node(PATROL_HOME_VAR), x0 + 480, y0 + 300))
    home_out = _pin(home, PATROL_HOME_VAR, is_input=False)
    pick = keep(_at(_node(ed, FN_RANDOM_REACHABLE), x0 + 720, y0 + 300))
    _connect(home_out, _pin(pick, "Origin"))
    radius, radius_out = tuned(ed, "patrol_radius_cm", x0 + 480, y0 + 580)
    keep(radius)
    _connect(radius_out, _pin(pick, "Radius"))
    aim = keep(_at(ed.add_set_member_variable_node(PATROL_TARGET_VAR), x0 + 960, y0))
    _connect(_pin(pick, "RandomLocation", is_input=False), _pin(aim, PATROL_TARGET_VAR))
    _connect(BEL.find_then_pin(time_to), _pin(aim, "execute"))

    wait = keep(_at(_node(ed, FN_RANDOM_FLOAT), x0 + 960, y0 + 300))
    for pin, column, dy in (("Min", "patrol_repick_min_s", 440),
                            ("Max", "patrol_repick_max_s", 580)):
        bound, bound_out = tuned(ed, column, x0 + 720, y0 + dy)
        keep(bound)
        _connect(bound_out, _pin(wait, pin))
    later = keep(_at(_node(ed, FN_ADD_FF), x0 + 1200, y0 + 300))
    _connect(now_out, _pin(later, "A"))
    _connect(_pin(wait, "ReturnValue", is_input=False), _pin(later, "B"))
    rearm = keep(_at(ed.add_set_member_variable_node(NEXT_PATROL_VAR), x0 + 1200, y0))
    _connect(_pin(later, "ReturnValue", is_input=False), _pin(rearm, NEXT_PATROL_VAR))
    _connect(BEL.find_then_pin(aim), _pin(rearm, "execute"))

    target = keep(_at(ed.add_get_member_variable_node(PATROL_TARGET_VAR),
                      x0 + 1440, y0 + 300))
    target_out = _pin(target, PATROL_TARGET_VAR, is_input=False)
    off = keep(_at(_node(ed, FN_DISTANCE), x0 + 1680, y0 + 300))
    _connect(target_out, _pin(off, "V1"))
    _connect(home_out, _pin(off, "V2"))
    inside = keep(_at(_node(ed, FN_LE_FF), x0 + 1920, y0 + 300))
    _connect(_pin(off, "ReturnValue", is_input=False), _pin(inside, "A"))
    loose = keep(_at(_node(ed, FN_MUL_FF), x0 + 1440, y0 + 580))
    _connect(radius_out, _pin(loose, "A"))
    _set(loose, "B", PATROL_ACCEPT_FRACTION)
    fence = keep(_at(_node(ed, FN_ADD_FF), x0 + 1680, y0 + 580))
    _connect(_pin(loose, "ReturnValue", is_input=False), _pin(fence, "A"))
    _set(fence, "B", PATROL_ACCEPT_SLACK_CM)
    _connect(_pin(fence, "ReturnValue", is_input=False), _pin(inside, "B"))
    sane = keep(_at(ed.add_branch_node(), x0 + 1920, y0))
    _connect(_pin(inside, "ReturnValue", is_input=False), _pin(sane, "Condition"))
    _connect(BEL.find_then_pin(rearm), _pin(sane, "execute"))

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0 + 1920, y0 + 440))
    me = keep(_at(_node(ed, FN_GET_CONTROLLER), x0 + 2160, y0 + 440))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(me, "self"))
    stroll = keep(_at(_node(ed, FN_SIMPLE_MOVE), x0 + 2400, y0))
    _connect(_pin(me, "ReturnValue", is_input=False), _pin(stroll, "Controller"))
    _connect(target_out, _pin(stroll, "Goal"))
    _connect(BEL.find_then_pin(sane), _pin(stroll, "execute"))

    for pin in (BEL.find_then_pin(stroll), BEL.find_else_pin(sane),
                BEL.find_else_pin(time_to)):
        _connect(pin, rest_in)
    return made
