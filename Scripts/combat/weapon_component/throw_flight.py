"""The thrown item's flight: every frame something is in the air, carry it
one frame along the curve the arc was drawn from, tumbling end over end, and
set it down where the segment it just flew hits something.

The flight is kinematic, not simulated physics: every item's parts are
NoCollision (weapon_items.build_parts), and a physics body would bounce off
somewhere the arc never promised. Position at time t is start + v t + g t^2/2
under THROW_GRAVITY_Z, the same gravity the prediction runs under, so the item
follows the dots and comes down on the disc at their end.

What it strikes on the way is throw_strike.py's: a blade (an item with a
ThrowDamage) wounds a body before it falls at its foot, and lodges in a tree
instead of falling, a pick-up still.

The tumble (_author_spin) is a turn about the level axis across the throw,
top first, at the item's own ThrowSpinDegS a second. It is added frame by
frame to whatever way the item lay as it left the hand, and it stops where
the item lands: the item rests as it came down, as a dropped one rests as it
was held. It moves nothing: the path is the arc's.

A melee weapon (the item's ThrowEdgeOn) leaves the hand squared up to the
throw (_author_square, run by the release): its blade's plane is the plane it
flies in, so that same tumble is a throwing axe's forward spin, the blade
going over the handle edge first, and not whatever wobble the hand's pose at
the release would have made of it.

Owns the variables the release (throw.py) stores the launch in.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from combat.nodes import (
    FN_ADD_VV, FN_GREATER_FF, FN_IS_VALID, FN_MAKE_VECTOR, FN_MUL_FF, FN_MUL_VF,
    FN_NORMAL, FN_ROT_FROM_X, FN_SET_ACTOR_LOC, FN_SET_ACTOR_ROT, FN_SUB_FF,
    FN_TIME_SECONDS, FN_TRACE, NODE_BREAK_HIT,
)
from combat.paths import ITEM_CLASS_PATH
from combat.throw_tuning import (
    THROW_BOUNCE_BACK, THROW_EDGE_ON_VAR, THROW_GRAVITY_Z, THROW_LAND_LIFT,
    THROW_MAX_FLIGHT_S, THROW_SPIN_VAR,
)
from combat.weapon_component.common import _prop, _trace_defaults
from combat.weapon_component.throw_strike import THROW_PAST_VAR, _author_throw_strike

THROWN_VAR = "Thrown"                 # the item in the air, or None
THROW_START_VAR = "ThrowStart"
THROW_VELOCITY_VAR = "ThrowVelocity"
THROW_TIME_VAR = "ThrowTime"          # world time at release
THROW_LAST_VAR = "ThrowLast"          # where the flight was last frame
FLIGHT_GROUND_CM = 5000.0             # how far down a wall-stopped item looks for ground

FN_CROSS = "/Script/Engine.KismetMathLibrary.Cross_VectorVector"
FN_AXIS_ANGLE = "/Script/Engine.KismetMathLibrary.RotatorFromAxisAndAngle"
FN_DELTA_SECONDS = "/Script/Engine.GameplayStatics.GetWorldDeltaSeconds"
FN_ADD_WORLD_ROT = "/Script/Engine.Actor.K2_AddActorWorldRotation"


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _author_square(ed, held, exec_in, x0, y0):
    """The release, for an item thrown edge on (a melee weapon): turn it so
    its X runs along the throw and its Y level across it. Returns the exit
    exec pins.

    Every melee model is built blade up with its edge towards +X, so squared
    up its blade lies in the vertical plane of the throw, and the tumble,
    which turns about the across axis, spins it forward in that plane.
    MakeRotFromX has no roll: Y stays level. Reads the launch the release has
    just stored, and Held: run it after the one and where the other is valid.
    """
    edge_on, _n = _prop(ed, THROW_EDGE_ON_VAR, held, x0, y0 + 160)
    gate = _at(ed.add_branch_node(), x0 + 260, y0)
    _connect(edge_on, _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))
    vel = _at(ed.add_get_member_variable_node(THROW_VELOCITY_VAR), x0 + 260, y0 + 300)
    along = _at(_node(ed, FN_ROT_FROM_X), x0 + 520, y0 + 300)
    _connect(_out(vel, THROW_VELOCITY_VAR), _pin(along, "X"))
    turn = _at(_node(ed, FN_SET_ACTOR_ROT), x0 + 780, y0)
    _connect(held, _pin(turn, "self"))
    _connect(_out(along), _pin(turn, "NewRotation"))
    _connect(BEL.find_then_pin(gate), _pin(turn, "execute"))
    ed.add_comment_to_nodes(
        "A melee weapon leaves the hand squared up to the throw: its blade in "
        "the plane it flies in, edge first.", [gate, along, turn])
    return BEL.find_then_pin(turn), BEL.find_else_pin(gate)


def _author_spin(ed, thrown, exec_in, x0, y0):
    """This frame's share of the tumble, added to the item in the air.
    Returns the exec pin after it.

    The axis is the level one across the throw. Velocity x up points to the
    thrower's left, and a turn about the left axis by a negative angle takes
    the item's top forward, so the angle goes in negated. The rate is the
    flying item's own ThrowSpinDegS. The launch is capped
    short of straight up (THROW_MAX_PITCH_DEG), so the cross is never zero.
    """
    vel = _at(ed.add_get_member_variable_node(THROW_VELOCITY_VAR), x0, y0)
    across = _at(_node(ed, FN_CROSS), x0 + 240, y0)
    _connect(_out(vel, THROW_VELOCITY_VAR), _pin(across, "A"))
    _connect(_vec(ed, 0.0, 0.0, 1.0, x0, y0 + 140), _pin(across, "B"))
    axis = _at(_node(ed, FN_NORMAL), x0 + 480, y0)
    _connect(_out(across), _pin(axis, "A"))
    dt = _at(_node(ed, FN_DELTA_SECONDS), x0 + 240, y0 + 300)
    angle = _at(_node(ed, FN_MUL_FF), x0 + 480, y0 + 300)
    _connect(_out(dt), _pin(angle, "A"))
    rate, _rate_n = _prop(ed, THROW_SPIN_VAR, thrown, x0 + 240, y0 + 440)
    _connect(rate, _pin(angle, "B"))
    back = _at(_node(ed, FN_MUL_FF), x0 + 600, y0 + 300)
    _connect(_out(angle), _pin(back, "A"))
    _set(back, "B", -1.0)
    turn = _at(_node(ed, FN_AXIS_ANGLE), x0 + 720, y0)
    _connect(_out(axis), _pin(turn, "Axis"))
    _connect(_out(back), _pin(turn, "Angle"))
    spin = _at(_node(ed, FN_ADD_WORLD_ROT), x0 + 980, y0 - 200)
    _connect(thrown, _pin(spin, "self"))
    _connect(_out(turn), _pin(spin, "DeltaRotation"))
    _connect(exec_in, _pin(spin, "execute"))
    ed.add_comment_to_nodes(
        f"The tumble: the item's {THROW_SPIN_VAR} degrees a second about the "
        "level axis across the throw, top first.", [across, turn, spin])
    return BEL.find_then_pin(spin)


def _author_throw_flight(ed, exec_ins, x0, y0):
    """Every frame something is in the air: carry it one frame along the
    curve, and set it down where the segment it just flew hits something.
    Returns the exit exec pins."""
    thrown_get = _at(ed.add_get_member_variable_node(THROWN_VAR), x0, y0 + 200)
    thrown = _out(thrown_get, THROWN_VAR)
    flying = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 200)
    _connect(thrown, _pin(flying, "Object"))
    gate = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_out(flying), _pin(gate, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(gate, "execute"))

    # t, and start + v t + (0, 0, g t^2 / 2)
    now = _at(_node(ed, FN_TIME_SECONDS), x0, y0 + 500)
    since = _at(ed.add_get_member_variable_node(THROW_TIME_VAR), x0, y0 + 620)
    t = _at(_node(ed, FN_SUB_FF), x0 + 240, y0 + 500)
    _connect(_out(now), _pin(t, "A"))
    _connect(_out(since, THROW_TIME_VAR), _pin(t, "B"))
    t_out = _out(t)
    tt = _at(_node(ed, FN_MUL_FF), x0 + 480, y0 + 620)
    _connect(t_out, _pin(tt, "A"))
    _connect(t_out, _pin(tt, "B"))
    fall = _at(_node(ed, FN_MUL_FF), x0 + 720, y0 + 620)
    _connect(_out(tt), _pin(fall, "A"))
    _set(fall, "B", 0.5 * THROW_GRAVITY_Z)
    drop = _at(_node(ed, FN_MAKE_VECTOR), x0 + 960, y0 + 620)
    _set(drop, "X", 0.0)
    _set(drop, "Y", 0.0)
    _connect(_out(fall), _pin(drop, "Z"))
    ts = _at(_node(ed, FN_MAKE_VECTOR), x0 + 480, y0 + 800)
    for axis in ("X", "Y", "Z"):
        _connect(t_out, _pin(ts, axis))
    vel = _at(ed.add_get_member_variable_node(THROW_VELOCITY_VAR), x0 + 480, y0 + 960)
    vt = _at(_node(ed, FN_MUL_VF), x0 + 720, y0 + 800)
    _connect(_out(vel, THROW_VELOCITY_VAR), _pin(vt, "A"))
    _connect(_out(ts), _pin(vt, "B"))
    origin = _at(ed.add_get_member_variable_node(THROW_START_VAR), x0 + 720, y0 + 960)
    moved = _at(_node(ed, FN_ADD_VV), x0 + 960, y0 + 800)
    _connect(_out(origin, THROW_START_VAR), _pin(moved, "A"))
    _connect(_out(vt), _pin(moved, "B"))
    pos = _at(_node(ed, FN_ADD_VV), x0 + 1200, y0 + 700)
    _connect(_out(moved), _pin(pos, "A"))
    _connect(_out(drop), _pin(pos, "B"))
    pos_out = _out(pos)

    last = _at(ed.add_get_member_variable_node(THROW_LAST_VAR), x0 + 1200, y0 + 400)
    seg = _at(_node(ed, FN_TRACE), x0 + 1460, y0)
    _connect(_out(last, THROW_LAST_VAR), _pin(seg, "Start"))
    _connect(pos_out, _pin(seg, "End"))
    _trace_defaults(seg)
    _connect(BEL.find_then_pin(gate), _pin(seg, "execute"))
    struck = _at(ed.add_branch_node(), x0 + 1740, y0)
    _connect(_out(seg), _pin(struck, "Condition"))
    _connect(BEL.find_then_pin(seg), _pin(struck, "execute"))

    # --- still flying: move on, and give up on a throw into nothing ----------
    fly = _at(_node(ed, FN_SET_ACTOR_LOC), x0 + 2000, y0 + 300)
    _connect(thrown, _pin(fly, "self"))
    _connect(pos_out, _pin(fly, "NewLocation"))
    _connect(BEL.find_else_pin(struck), _pin(fly, "execute"))
    step = _at(ed.add_set_member_variable_node(THROW_LAST_VAR), x0 + 2260, y0 + 300)
    _connect(pos_out, _pin(step, THROW_LAST_VAR))
    _connect(_author_spin(ed, thrown, BEL.find_then_pin(fly), x0 + 2000, y0 + 1100),
             _pin(step, "execute"))
    late = _at(_node(ed, FN_GREATER_FF), x0 + 2260, y0 + 500)
    _connect(t_out, _pin(late, "A"))
    _set(late, "B", THROW_MAX_FLIGHT_S)
    lost = _at(ed.add_branch_node(), x0 + 2520, y0 + 300)
    _connect(_out(late), _pin(lost, "Condition"))
    _connect(BEL.find_then_pin(step), _pin(lost, "execute"))

    # --- struck: back off what it hit, then down onto the ground -------------
    # A floor gives the same floor back; a wall or a wanderer drops it at
    # their foot rather than leaving it stuck to their side.
    hit = _at(_palette(ed, NODE_BREAK_HIT), x0 + 2000, y0 - 600)
    _connect(_out(seg, "OutHit"), _loose_pin(hit, "Hit"))
    push = _at(_node(ed, FN_MUL_VF), x0 + 2260, y0 - 500)
    _connect(_loose_pin(hit, "ImpactNormal", is_input=False), _pin(push, "A"))
    b = THROW_BOUNCE_BACK
    _connect(_vec(ed, b, b, b, x0 + 2000, y0 - 300), _pin(push, "B"))
    back = _at(_node(ed, FN_ADD_VV), x0 + 2520, y0 - 600)
    _connect(_loose_pin(hit, "Location", is_input=False), _pin(back, "A"))
    _connect(_out(push), _pin(back, "B"))
    below = _at(_node(ed, FN_ADD_VV), x0 + 2780, y0 - 500)
    _connect(_out(back), _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -FLIGHT_GROUND_CM, x0 + 2520, y0 - 380), _pin(below, "B"))
    floor = _at(_node(ed, FN_TRACE), x0 + 3040, y0 - 200)
    _connect(_out(back), _pin(floor, "Start"))
    _connect(_out(below), _pin(floor, "End"))
    _trace_defaults(floor)
    # First what a blade does to what it struck (throw_strike.py): one that
    # lodged in a tree stays there, and skips the way down.
    falls, lodged = _author_throw_strike(ed, thrown, hit, BEL.find_then_pin(struck),
                                         x0 + 2000, y0 - 2600)
    for pin in falls:
        _connect(pin, _pin(floor, "execute"))
    # ...and the way down passes by a body it wounded, which would catch it.
    past = _at(ed.add_get_member_variable_node(THROW_PAST_VAR), x0 + 2780, y0 - 60)
    _connect(_out(past, THROW_PAST_VAR), _pin(floor, "ActorsToIgnore"))
    grounded = _at(ed.add_branch_node(), x0 + 3300, y0 - 200)
    _connect(_out(floor), _pin(grounded, "Condition"))
    _connect(BEL.find_then_pin(floor), _pin(grounded, "execute"))
    ground = _at(_palette(ed, NODE_BREAK_HIT), x0 + 3300, y0 - 600)
    _connect(_out(floor, "OutHit"), _loose_pin(ground, "Hit"))
    lift = _at(_node(ed, FN_ADD_VV), x0 + 3560, y0 - 500)
    _connect(_loose_pin(ground, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, THROW_LAND_LIFT, x0 + 3300, y0 - 380), _pin(lift, "B"))
    rest = _at(_node(ed, FN_SET_ACTOR_LOC), x0 + 3820, y0 - 300)
    _connect(thrown, _pin(rest, "self"))
    _connect(_out(lift), _pin(rest, "NewLocation"))
    _connect(BEL.find_then_pin(grounded), _pin(rest, "execute"))
    hang = _at(_node(ed, FN_SET_ACTOR_LOC), x0 + 3820, y0 - 60)
    _connect(thrown, _pin(hang, "self"))
    _connect(_out(back), _pin(hang, "NewLocation"))
    _connect(BEL.find_else_pin(grounded), _pin(hang, "execute"))

    # --- landed: an ordinary dropped item, which E picks up ------------------
    flag = _at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH), x0 + 4100, y0)
    _connect(thrown, _pin(flag, "self"))
    _set(flag, "Dropped", "true")
    for pin in (BEL.find_then_pin(rest), BEL.find_then_pin(hang),
                BEL.find_then_pin(lost)) + lodged:
        _connect(pin, _pin(flag, "execute"))
    done = _at(ed.add_set_member_variable_node(THROWN_VAR), x0 + 4360, y0)
    _connect(BEL.find_then_pin(flag), _pin(done, "execute"))

    ed.add_comment_to_nodes(
        "The thrown item's flight: start + v t + g t^2 / 2, the curve the arc "
        "was drawn from, tumbling as it goes. A trace from last frame's point to this one sets it "
        "down, after what a blade does to what it struck; then it is an "
        "ordinary Dropped item, for E to pick up.",
        [gate, seg, struck, fly, lost, floor, flag, done])
    return (BEL.find_then_pin(done), BEL.find_else_pin(gate), BEL.find_else_pin(lost))
