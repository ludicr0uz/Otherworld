"""Patrolling: the once-per-life setup (centre, run speed, stroll speed) and
the step that sends a wanderer to a new point inside its circle now and then.
"""

from forest_generator.npc_agro import PATROL_ACCEPT_FRACTION, PATROL_ACCEPT_SLACK_CM
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from npc.paths import (
    CHARACTER_CLASS_PATH, MOVEMENT_CLASS_PATH, NEXT_PATROL_VAR,
    PATROL_HOME_VAR, PATROL_READY_VAR, PATROL_TARGET_VAR, RUN_SPEED_VAR,
)
from npc.tuned import tuned
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_CONTROLLER, FN_GET_PAWN
from uebp.nodes.ai import FN_RANDOM_REACHABLE, FN_SIMPLE_MOVE
from uebp.nodes.math import (
    FN_ADD_FF, FN_DISTANCE, FN_DIV_FF, FN_GE_FF, FN_LE_FF, FN_MUL_FF, FN_RANDOM_FLOAT)
from uebp.nodes.palette import NODE_CAST_CHARACTER
from uebp.nodes.system import FN_TIME_SECONDS
from uebp import props as EP


def _author_walk_speed(ed, exec_in, stroll, stock, scale=None):
    """MaxWalkSpeed = RunSpeed * TuneRunSpeed / ``stock`` [* TunePatrolSpeed]
    on the possessed Character: the run, or with ``stroll`` the patrol walk,
    or with ``scale`` that fraction of the run (the step between two swings,
    npc/strafe.py). A ``scale`` that is a string is a MONSTER_STATS column:
    the fraction is that Tune variable (a wendigo's leg, its prowl round a
    fire).

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

    pawn = keep(_node(ed, FN_GET_PAWN))
    as_char = keep(_palette(ed, NODE_CAST_CHARACTER))
    _connect(out(pawn), _pin(as_char, "Object"))
    for pin in exec_in:
        _connect(pin, _pin(as_char, "execute"))
    move = keep(ed.add_get_member_variable_node(EP.CHARACTER_MOVEMENT, CHARACTER_CLASS_PATH))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(move, "self"))
    run = keep(ed.add_get_member_variable_node(RUN_SPEED_VAR))
    want, want_out = tuned(ed, "run_speed_cms")
    keep(want)
    ratio = keep(_node(ed, FN_DIV_FF))
    _connect(want_out, _pin(ratio, "A"))
    _set(ratio, "B", stock)
    scaled = keep(_node(ed, FN_MUL_FF))
    _connect(out(run, RUN_SPEED_VAR), _pin(scaled, "A"))
    _connect(out(ratio), _pin(scaled, "B"))
    speed = out(scaled)
    if stroll:
        walk, walk_out = tuned(ed, "patrol_speed_scale")
        keep(walk)
        slowed = keep(_node(ed, FN_MUL_FF))
        _connect(speed, _pin(slowed, "A"))
        _connect(walk_out, _pin(slowed, "B"))
        speed = out(slowed)
    if scale is not None:
        eased = keep(_node(ed, FN_MUL_FF))
        _connect(speed, _pin(eased, "A"))
        if isinstance(scale, str):
            share, share_out = tuned(ed, scale)
            keep(share)
            _connect(share_out, _pin(eased, "B"))
        else:
            _set(eased, "B", scale)
        speed = out(eased)
    write = keep(ed.add_set_member_variable_node(EP.MAX_WALK_SPEED, MOVEMENT_CLASS_PATH))
    _connect(out(move, "CharacterMovement"), _pin(write, "self"))
    _connect(speed, _pin(write, "MaxWalkSpeed"))
    _connect(then(as_char), _pin(write, "execute"))
    return (made, [then(write), out(as_char, "CastFailed")], _pin(as_char, "execute"))


def _author_patrol_setup(ed, exec_in):
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

    ready = keep(ed.add_get_member_variable_node(PATROL_READY_VAR))
    first = keep(ed.add_branch_node())
    _connect(_pin(ready, PATROL_READY_VAR, is_input=False), _pin(first, "Condition"))
    _connect(exec_in, _pin(first, "execute"))

    pawn = keep(_node(ed, FN_GET_PAWN))
    where = keep(_node(ed, FN_ACTOR_LOC))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(where, "self"))
    home = keep(ed.add_set_member_variable_node(PATROL_HOME_VAR))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(home, PATROL_HOME_VAR))
    _connect(else_(first), _pin(home, "execute"))

    as_char = keep(_palette(ed, NODE_CAST_CHARACTER))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    _connect(then(home), _pin(as_char, "execute"))
    move = keep(ed.add_get_member_variable_node(EP.CHARACTER_MOVEMENT, CHARACTER_CLASS_PATH))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(move, "self"))
    speed = keep(ed.add_get_member_variable_node(EP.MAX_WALK_SPEED, MOVEMENT_CLASS_PATH))
    _connect(_pin(move, "CharacterMovement", is_input=False), _pin(speed, "self"))
    cache = keep(ed.add_set_member_variable_node(RUN_SPEED_VAR))
    _connect(_pin(speed, "MaxWalkSpeed", is_input=False), _pin(cache, RUN_SPEED_VAR))
    _connect(then(as_char), _pin(cache, "execute"))

    mark = keep(ed.add_set_member_variable_node(PATROL_READY_VAR))
    _set(mark, PATROL_READY_VAR, True)
    # A pawn that is not a Character still gets a centre and is marked ready,
    # or it would retry the setup on every heartbeat forever.
    for pin in (then(cache), _pin(as_char, "CastFailed", is_input=False)):
        _connect(pin, _pin(mark, "execute"))

    out = keep(ed.add_branch_node())
    _set(out, "Condition", True)
    _connect(then(mark), _pin(out, "execute"))
    _connect(then(first), _pin(out, "execute"))
    return made, then(out)


def _author_patrol_step(ed, exec_in, rest_in):
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

    now = keep(_node(ed, FN_TIME_SECONDS))
    now_out = out(now)
    due_at = keep(ed.add_get_member_variable_node(NEXT_PATROL_VAR))
    due = keep(_node(ed, FN_GE_FF))
    _connect(now_out, _pin(due, "A"))
    _connect(out(due_at, NEXT_PATROL_VAR), _pin(due, "B"))
    time_to = keep(ed.add_branch_node())
    _connect(out(due), _pin(time_to, "Condition"))
    for pin in exec_in:
        _connect(pin, _pin(time_to, "execute"))

    home = keep(ed.add_get_member_variable_node(PATROL_HOME_VAR))
    home_out = out(home, PATROL_HOME_VAR)
    pick = keep(_node(ed, FN_RANDOM_REACHABLE))
    _connect(home_out, _pin(pick, "Origin"))
    radius, radius_out = tuned(ed, "patrol_radius_cm")
    keep(radius)
    _connect(radius_out, _pin(pick, "Radius"))
    aim = keep(ed.add_set_member_variable_node(PATROL_TARGET_VAR))
    _connect(out(pick, "RandomLocation"), _pin(aim, PATROL_TARGET_VAR))
    _connect(then(time_to), _pin(aim, "execute"))

    wait = keep(_node(ed, FN_RANDOM_FLOAT))
    for pin, column in (("Min", "patrol_repick_min_s"), ("Max", "patrol_repick_max_s")):
        bound, bound_out = tuned(ed, column)
        keep(bound)
        _connect(bound_out, _pin(wait, pin))
    later = keep(_node(ed, FN_ADD_FF))
    _connect(now_out, _pin(later, "A"))
    _connect(out(wait), _pin(later, "B"))
    rearm = keep(ed.add_set_member_variable_node(NEXT_PATROL_VAR))
    _connect(out(later), _pin(rearm, NEXT_PATROL_VAR))
    _connect(then(aim), _pin(rearm, "execute"))

    target = keep(ed.add_get_member_variable_node(PATROL_TARGET_VAR))
    target_out = out(target, PATROL_TARGET_VAR)
    off = keep(_node(ed, FN_DISTANCE))
    _connect(target_out, _pin(off, "V1"))
    _connect(home_out, _pin(off, "V2"))
    inside = keep(_node(ed, FN_LE_FF))
    _connect(out(off), _pin(inside, "A"))
    loose = keep(_node(ed, FN_MUL_FF))
    _connect(radius_out, _pin(loose, "A"))
    _set(loose, "B", PATROL_ACCEPT_FRACTION)
    fence = keep(_node(ed, FN_ADD_FF))
    _connect(out(loose), _pin(fence, "A"))
    _set(fence, "B", PATROL_ACCEPT_SLACK_CM)
    _connect(out(fence), _pin(inside, "B"))
    sane = keep(ed.add_branch_node())
    _connect(out(inside), _pin(sane, "Condition"))
    _connect(then(rearm), _pin(sane, "execute"))

    pawn = keep(_node(ed, FN_GET_PAWN))
    me = keep(_node(ed, FN_GET_CONTROLLER))
    _connect(out(pawn), _pin(me, "self"))
    stroll = keep(_node(ed, FN_SIMPLE_MOVE))
    _connect(out(me), _pin(stroll, "Controller"))
    _connect(target_out, _pin(stroll, "Goal"))
    _connect(then(sane), _pin(stroll, "execute"))

    for pin in (then(stroll), else_(sane), else_(time_to)):
        _connect(pin, rest_in)
    return made
