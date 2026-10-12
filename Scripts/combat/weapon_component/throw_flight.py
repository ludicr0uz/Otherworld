"""The thrown item's flight: every frame something is in the air, carry it
one frame along the curve the arc was drawn from, tumbling end over end, and
set it down where the segment it just flew hits something.

The flight is kinematic, not simulated physics: every item's parts are
NoCollision (weapon_items.build_parts), and a physics body would bounce off
somewhere the arc never promised. Position at time t is start + v t + g t^2/2
under THROW_GRAVITY_Z, the same gravity the prediction runs under, so the item
follows the dots and comes down on the disc at their end.

What it strikes on the way is throw_strike.py's: a blade (an item with a
ThrowDamage) wounds a body and stays in it, attached, and lodges in a tree;
either way it skips the fall, a pick-up still.

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

Every machine flies it, by this one graph (task R2): what is carried along
the curve is ThrowFlyer, which is the item itself with authority (the server,
and single player) and a client's local stand-in of it (throw_standin.py),
on this machine's own clock from a ThrowTime the launch set. What it strikes
is judged once, with authority: a client's stand-in stops where its own curve
runs into something (ThrowStopped) and waits there for the server's word,
which the landing sends (Multicast_ThrowEnd: where the item lies, and the
body and bone a blade is left in). The landing is also where the server's
item starts to send its movement: no client is sent a position in flight.

Owns the variables the release (throw.py) stores the launch in.
"""

from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.item_world import author_rests
from combat.paths import ITEM_CLASS_PATH
from combat.strike_vars import (
    AT_PARAM, BONE_PARAM, OFF_PARAM, PARENT_PARAM, THROW_END, TIME_PARAM, TURN_PARAM)
from combat.throw_tuning import (
    THROW_BOUNCE_BACK, THROW_EDGE_ON_VAR, THROW_GRAVITY_Z, THROW_LAND_LIFT,
    THROW_MAX_FLIGHT_S, THROW_SPIN_VAR,
)
from combat.weapon_component.common import _prop, _trace_defaults
from combat.weapon_component.throw_strike import THROW_PAST_VAR, _author_throw_strike
from uebp.g import _G
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_ADD_WORLD_ROT, FN_ATTACH_PARENT, FN_ATTACH_SOCKET, FN_GET_OWNER,
    FN_HAS_AUTHORITY, FN_ROOT, FN_SET_ACTOR_LOC, FN_SET_ACTOR_ROT, FN_SOCKET_TRANSFORM)
from uebp.nodes.locomotion import FN_ACTOR_ROT
from uebp.nodes.math import (
    FN_ADD_VV, FN_AND, FN_AXIS_ANGLE, FN_CROSS, FN_GREATER_FF, FN_INV_XFORM_LOC, FN_MAKE_VECTOR,
    FN_MUL_FF, FN_MUL_VF, FN_NORMAL, FN_NOT, FN_OR, FN_ROT_FROM_X, FN_SUB_FF)
from uebp.nodes.palette import NODE_BREAK_HIT
from uebp.nodes.system import FN_DELTA_SECONDS, FN_IS_VALID, FN_TIME_SECONDS, FN_TRACE
from combat import item_vars as IV
from combat.weapon_component import vars as WV

THROWN_VAR = WV.Thrown                 # the server's item in the air, or None
FLYER_VAR = WV.ThrowFlyer              # what this machine flies: it, or a stand-in
THROW_START_VAR = WV.ThrowStart
THROW_VELOCITY_VAR = WV.ThrowVelocity
THROW_TIME_VAR = WV.ThrowTime          # this machine's world time at release
THROW_LAST_VAR = WV.ThrowLast          # where the flight was last frame
FLIGHT_GROUND_CM = 5000.0             # how far down a wall-stopped item looks for ground


def _author_square(ed, held, exec_in):
    """The release, for an item thrown edge on (a melee weapon): turn it so
    its X runs along the throw and its Y level across it. Returns the exit
    exec pins.

    Every melee model is built blade up with its edge towards +X, so squared
    up its blade lies in the vertical plane of the throw, and the tumble,
    which turns about the across axis, spins it forward in that plane.
    MakeRotFromX has no roll: Y stays level. Reads the launch the release has
    just stored, and Held: run it after the one and where the other is valid.
    """
    edge_on, _n = _prop(ed, THROW_EDGE_ON_VAR, held)
    gate = ed.add_branch_node()
    _connect(edge_on, _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))
    vel = ed.add_get_member_variable_node(THROW_VELOCITY_VAR)
    along = _node(ed, FN_ROT_FROM_X)
    _connect(out(vel, THROW_VELOCITY_VAR), _pin(along, "X"))
    turn = _node(ed, FN_SET_ACTOR_ROT)
    _connect(held, _pin(turn, "self"))
    _connect(out(along), _pin(turn, "NewRotation"))
    _connect(then(gate), _pin(turn, "execute"))
    ed.add_comment_to_nodes(
        "A melee weapon leaves the hand squared up to the throw: its blade in "
        "the plane it flies in, edge first.", [gate, along, turn])
    return then(turn), else_(gate)


def _author_spin(ed, thrown, exec_in):
    """This frame's share of the tumble, added to the item in the air.
    Returns the exec pin after it.

    The axis is the level one across the throw. Velocity x up points to the
    thrower's left, and a turn about the left axis by a negative angle takes
    the item's top forward, so the angle goes in negated. The rate is the
    flying item's own ThrowSpinDegS. The launch is capped
    short of straight up (THROW_MAX_PITCH_DEG), so the cross is never zero.
    """
    vel = ed.add_get_member_variable_node(THROW_VELOCITY_VAR)
    across = _node(ed, FN_CROSS)
    _connect(out(vel, THROW_VELOCITY_VAR), _pin(across, "A"))
    _connect(_vec(ed, 0.0, 0.0, 1.0), _pin(across, "B"))
    axis = _node(ed, FN_NORMAL)
    _connect(out(across), _pin(axis, "A"))
    dt = _node(ed, FN_DELTA_SECONDS)
    angle = _node(ed, FN_MUL_FF)
    _connect(out(dt), _pin(angle, "A"))
    rate, _rate_n = _prop(ed, THROW_SPIN_VAR, thrown)
    _connect(rate, _pin(angle, "B"))
    back = _node(ed, FN_MUL_FF)
    _connect(out(angle), _pin(back, "A"))
    _set(back, "B", -1.0)
    turn = _node(ed, FN_AXIS_ANGLE)
    _connect(out(axis), _pin(turn, "Axis"))
    _connect(out(back), _pin(turn, "Angle"))
    spin = _node(ed, FN_ADD_WORLD_ROT)
    _connect(thrown, _pin(spin, "self"))
    _connect(out(turn), _pin(spin, "DeltaRotation"))
    _connect(exec_in, _pin(spin, "execute"))
    ed.add_comment_to_nodes(
        f"The tumble: the item's {THROW_SPIN_VAR} degrees a second about the "
        "level axis across the throw, top first.", [across, turn, spin])
    return then(spin)


def _author_throw_flight(ed, exec_ins):
    """Every frame something is in the air: carry it one frame along the
    curve, and set it down where the segment it just flew hits something.
    Returns the exit exec pins."""
    thrown_get = ed.add_get_member_variable_node(FLYER_VAR)
    thrown = out(thrown_get, FLYER_VAR)
    flying = _node(ed, FN_IS_VALID)
    _connect(thrown, _pin(flying, "Object"))
    # ...and still in the air: a client's stand-in whose curve ran into
    # something, or that the server's end has reached, flies no further
    # (throw_standin.py moves it from there). With authority neither is set.
    stopped = _node(ed, FN_OR)
    _connect(out(ed.add_get_member_variable_node(WV.ThrowStopped), WV.ThrowStopped),
             _pin(stopped, "A"))
    _connect(out(ed.add_get_member_variable_node(WV.ThrowEnded), WV.ThrowEnded),
             _pin(stopped, "B"))
    going = _node(ed, FN_NOT)
    _connect(out(stopped), _pin(going, "A"))
    mine = _node(ed, FN_AND)
    _connect(out(flying), _pin(mine, "A"))
    _connect(out(going), _pin(mine, "B"))
    # The strike, the fall and the rest are the server's alone (and single
    # player's): the machine that owns the thrower.
    owner = _node(ed, FN_GET_OWNER)
    owns = _node(ed, FN_HAS_AUTHORITY)
    _connect(out(owner), _pin(owns, "self"))
    gate = ed.add_branch_node()
    _connect(out(mine), _pin(gate, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(gate, "execute"))

    # t, and start + v t + (0, 0, g t^2 / 2)
    now = _node(ed, FN_TIME_SECONDS)
    since = ed.add_get_member_variable_node(THROW_TIME_VAR)
    t = _node(ed, FN_SUB_FF)
    _connect(out(now), _pin(t, "A"))
    _connect(out(since, THROW_TIME_VAR), _pin(t, "B"))
    t_out = out(t)
    tt = _node(ed, FN_MUL_FF)
    _connect(t_out, _pin(tt, "A"))
    _connect(t_out, _pin(tt, "B"))
    fall = _node(ed, FN_MUL_FF)
    _connect(out(tt), _pin(fall, "A"))
    _set(fall, "B", 0.5 * THROW_GRAVITY_Z)
    drop = _node(ed, FN_MAKE_VECTOR)
    _set(drop, "X", 0.0)
    _set(drop, "Y", 0.0)
    _connect(out(fall), _pin(drop, "Z"))
    ts = _node(ed, FN_MAKE_VECTOR)
    for axis in ("X", "Y", "Z"):
        _connect(t_out, _pin(ts, axis))
    vel = ed.add_get_member_variable_node(THROW_VELOCITY_VAR)
    vt = _node(ed, FN_MUL_VF)
    _connect(out(vel, THROW_VELOCITY_VAR), _pin(vt, "A"))
    _connect(out(ts), _pin(vt, "B"))
    origin = ed.add_get_member_variable_node(THROW_START_VAR)
    moved = _node(ed, FN_ADD_VV)
    _connect(out(origin, THROW_START_VAR), _pin(moved, "A"))
    _connect(out(vt), _pin(moved, "B"))
    pos = _node(ed, FN_ADD_VV)
    _connect(out(moved), _pin(pos, "A"))
    _connect(out(drop), _pin(pos, "B"))
    pos_out = out(pos)

    last = ed.add_get_member_variable_node(THROW_LAST_VAR)
    seg = _node(ed, FN_TRACE)
    _connect(out(last, THROW_LAST_VAR), _pin(seg, "Start"))
    _connect(pos_out, _pin(seg, "End"))
    _trace_defaults(seg)
    _connect(then(gate), _pin(seg, "execute"))
    struck = ed.add_branch_node()
    _connect(out(seg), _pin(struck, "Condition"))
    _connect(then(seg), _pin(struck, "execute"))

    # --- still flying: move on, and give up on a throw into nothing ----------
    fly = _node(ed, FN_SET_ACTOR_LOC)
    _connect(thrown, _pin(fly, "self"))
    _connect(pos_out, _pin(fly, "NewLocation"))
    _connect(else_(struck), _pin(fly, "execute"))
    step = ed.add_set_member_variable_node(THROW_LAST_VAR)
    _connect(pos_out, _pin(step, THROW_LAST_VAR))
    _connect(_author_spin(ed, thrown, then(fly)), _pin(step, "execute"))
    late = _node(ed, FN_GREATER_FF)
    _connect(t_out, _pin(late, "A"))
    _set(late, "B", THROW_MAX_FLIGHT_S)
    lost = ed.add_branch_node()
    _connect(out(late), _pin(lost, "Condition"))
    _connect(then(step), _pin(lost, "execute"))
    # ...which only the server lands: a client's stand-in waits where it is.
    lands = ed.add_branch_node()
    _connect(out(owns), _pin(lands, "Condition"))
    _connect(then(lost), _pin(lands, "execute"))
    # What the segment hit is the server's to judge: a client's stand-in is
    # put on it and flies no further.
    judge = ed.add_branch_node()
    _connect(out(owns), _pin(judge, "Condition"))
    _connect(then(struck), _pin(judge, "execute"))

    # With authority what flies is the item itself, Thrown: what is struck
    # with, set down and told of below.
    item = out(ed.add_get_member_variable_node(THROWN_VAR), THROWN_VAR)

    # --- struck: back off what it hit, then down onto the ground -------------
    # A floor gives the same floor back; a wall or a wanderer drops it at
    # their foot rather than leaving it stuck to their side.
    hit = _palette(ed, NODE_BREAK_HIT)
    _connect(out(seg, "OutHit"), _loose_pin(hit, "Hit"))
    push = _node(ed, FN_MUL_VF)
    _connect(_loose_pin(hit, "ImpactNormal", is_input=False), _pin(push, "A"))
    b = THROW_BOUNCE_BACK
    _connect(_vec(ed, b, b, b), _pin(push, "B"))
    back = _node(ed, FN_ADD_VV)
    _connect(_loose_pin(hit, "Location", is_input=False), _pin(back, "A"))
    _connect(out(push), _pin(back, "B"))
    below = _node(ed, FN_ADD_VV)
    _connect(out(back), _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -FLIGHT_GROUND_CM), _pin(below, "B"))
    floor = _node(ed, FN_TRACE)
    _connect(out(back), _pin(floor, "Start"))
    _connect(out(below), _pin(floor, "End"))
    _trace_defaults(floor)
    # First what a blade does to what it struck (throw_strike.py): one that
    # lodged in a tree or a body stays there, and skips the way down.
    falls, lodged = _author_throw_strike(ed, item, hit, then(judge))
    for pin in falls:
        _connect(pin, _pin(floor, "execute"))
    # ...and the way down passes by a body it wounded, which would catch it.
    past = ed.add_get_member_variable_node(THROW_PAST_VAR)
    _connect(out(past, THROW_PAST_VAR), _pin(floor, "ActorsToIgnore"))
    grounded = ed.add_branch_node()
    _connect(out(floor), _pin(grounded, "Condition"))
    _connect(then(floor), _pin(grounded, "execute"))
    ground = _palette(ed, NODE_BREAK_HIT)
    _connect(out(floor, "OutHit"), _loose_pin(ground, "Hit"))
    lift = _node(ed, FN_ADD_VV)
    _connect(_loose_pin(ground, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, THROW_LAND_LIFT), _pin(lift, "B"))
    rest = _node(ed, FN_SET_ACTOR_LOC)
    _connect(item, _pin(rest, "self"))
    _connect(out(lift), _pin(rest, "NewLocation"))
    _connect(then(grounded), _pin(rest, "execute"))
    hang = _node(ed, FN_SET_ACTOR_LOC)
    _connect(item, _pin(hang, "self"))
    _connect(out(back), _pin(hang, "NewLocation"))
    _connect(else_(grounded), _pin(hang, "execute"))

    # --- landed: an ordinary dropped item, which E picks up ------------------
    flag = ed.add_set_member_variable_node(IV.Dropped, ITEM_CLASS_PATH)
    _connect(item, _pin(flag, "self"))
    _set(flag, IV.Dropped, True)
    for pin in (then(rest), then(hang), then(lands)) + lodged:
        _connect(pin, _pin(flag, "execute"))
    # At rest its movement is sent (item_world.py), and every client is told
    # where it lies, for its stand-in to end there (throw_standin.py).
    told = _author_end_tell(ed, item, author_rests(ed, item, [then(flag)]))
    done = ed.add_set_member_variable_node(THROWN_VAR)
    _connect(told, _pin(done, "execute"))
    landed = ed.add_set_member_variable_node(FLYER_VAR)
    _connect(then(done), _pin(landed, "execute"))

    # --- a client's stand-in, stopped by what its own curve ran into ---------
    stuck = _node(ed, FN_SET_ACTOR_LOC)
    _connect(thrown, _pin(stuck, "self"))
    _connect(_loose_pin(hit, "Location", is_input=False), _pin(stuck, "NewLocation"))
    _connect(else_(judge), _pin(stuck, "execute"))
    halt = ed.add_set_member_variable_node(WV.ThrowStopped)
    _set(halt, WV.ThrowStopped, True)
    for pin in (then(stuck), else_(lands)):
        _connect(pin, _pin(halt, "execute"))

    ed.add_comment_to_nodes(
        "The thrown item's flight, on every machine (the item itself with "
        "authority, a client's stand-in of it): start + v t + g t^2 / 2, the curve "
        "the arc was drawn from, tumbling as it goes. A trace from last frame's "
        "point to this one ends it. With authority that sets the item down, after "
        "what a blade does to what it struck; then it is an ordinary Dropped item, "
        "for E to pick up, and every client is told where it lies. A client's "
        "stand-in stops there and waits for that word.",
        [gate, seg, struck, judge, fly, lost, lands, floor, flag, done, landed, stuck, halt])
    return (then(landed), else_(gate), else_(lost), then(halt))


def _author_end_tell(ed, item, exec_in):
    """With authority, the item at rest: Multicast_ThrowEnd says where it
    lies and how it is turned, and for one left in a body (its root has an
    attach parent) the component and bone it rides and where it is on that
    bone, which a client finds again on its own pose of the body. Returns the
    exec pin after."""
    g = _G(ed, ITEM_CLASS_PATH)
    root = out(g.call(FN_ROOT, self=item))
    parent = out(g.call(FN_ATTACH_PARENT, self=root))
    bone = out(g.call(FN_ATTACH_SOCKET, self=root))
    at = out(g.call(FN_ACTOR_LOC, self=item))
    borne, lying = g.branch(out(g.call(FN_IS_VALID, Object=parent)), [exec_in])
    exits = []
    for arm, held in ((borne, True), (lying, False)):
        tell = g.keep(_node(ed, THROW_END))
        _connect(g.get(WV.ThrowStamp), _pin(tell, TIME_PARAM))
        _connect(at, _pin(tell, AT_PARAM))
        _connect(out(g.call(FN_ACTOR_ROT, self=item)), _pin(tell, TURN_PARAM))
        if held:
            on = g.call(FN_SOCKET_TRANSFORM, self=parent, InSocketName=bone)
            _connect(parent, _pin(tell, PARENT_PARAM))
            _connect(bone, _pin(tell, BONE_PARAM))
            _connect(out(g.call(FN_INV_XFORM_LOC, T=out(on), Location=at)),
                     _pin(tell, OFF_PARAM))
        else:
            _connect(_vec(ed, 0.0, 0.0, 0.0), _pin(tell, OFF_PARAM))
        _connect(arm, _pin(tell, "execute"))
        exits.append(then(tell))
    join = g.put(WV.ThrowStopped, "false", exits)
    ed.add_comment_to_nodes(
        f"{THROW_END} is told (throw_standin.py): the thrown item lies here, turned "
        "so, and when a blade is left in a body, on which bone of which mesh and "
        "where on it.", g.made)
    return join

