"""A thrown item on a client: a stand-in that flies from the release (task R2).

The server's item is the one that counts: it flies there, strikes once
(throw_strike.py) and comes to rest. No client watches that actor fly. Its
copy is hidden until it rests (item_world.author_world_view) and its movement
is not sent before then, so nothing that delays or closes its channel can
touch what is seen in the air. What a client sees is a stand-in: a local
actor of the item's class, never replicated, that this component carries
along the same curve by the same graph (throw_flight._author_throw_flight
flies ThrowFlyer, which is the item itself with authority).

    the launch    ThrowLaunch(Class, Start, Velocity, Time, Lit, Hot), a
                  plain event Fx_Throw's body calls on a client: spawn the
                  stand-in at Start, burning or hot as the item is, squared
                  up as the release squares the item, and store the launch.
                  Time is the server's clock at the release. The stand-in's
                  own start is this machine's clock, set back by what the
                  server's has run since (GetServerWorldTimeSeconds, read
                  once): it starts where the server's item is now, a late
                  message shortens the flight and does not shift it, and a
                  correction of the clock in mid-air moves nothing.
      the thrower predicts: the frame its hand lets go it calls Fx_Throw
                  itself, with its own reading of the server's clock, and
                  hides the item in its hand. The server's launch then only
                  names that stand-in (ThrowStamp = Time: author_named): no
                  second one, and no jump back to the server's timing.
      refused     Client_ThrowRefused, reliable, to the owning client, from
                  every refusal of Server_Throw: the stand-in is destroyed
                  and the hand shown again.
    the flight    throw_flight.py, every machine. A client's ends where its
                  own curve runs into something (ThrowStopped): it waits
                  there for the server's word.
    the end       Multicast_ThrowEnd(Time, At, Turn, Parent, Bone, Off),
                  reliable, from the server as the item comes to rest: where
                  it lies and how it is turned, and for a blade left in a
                  body the mesh and bone it rides and where on that bone.
                  The stand-in is moved there over THROW_SETTLE_S from
                  wherever it had got to (onto the bone as this machine
                  poses it, each frame), and then gives way.
    the hand-off  the replicated item of the same ThrowStamp, once it has
                  come to rest on this machine too: shown, and the stand-in
                  destroyed, on one frame. Until then that copy keeps itself
                  hidden (its Released, item_world.py).

A stand-in nothing ends (its thrower left relevancy with the word) is
destroyed THROW_ORPHAN_S after its launch, and one no replicated item
follows THROW_END_WAIT_S after its end.

Single player has none of it: with authority ThrowLaunch and the end do
nothing, and the item itself flies.
"""

from combat import item_vars as IV
from combat.heat_tuning import HOT_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.strike_vars import (
    AT_PARAM, BONE_PARAM, CLASS_PARAM, END_PARAMS, HOT_PARAM, LAUNCH_PARAMS, LIT_PARAM,
    OFF_PARAM, PARENT_PARAM, START_PARAM, THROW_END, THROW_LAUNCH, THROW_REFUSED,
    TIME_PARAM, TURN_PARAM, VELOCITY_PARAM)
from combat.throw_tuning import THROW_END_WAIT_S, THROW_ORPHAN_S, THROW_SETTLE_S
from combat.torch_tuning import LIT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.record import authority
from combat.weapon_component.slot_nodes import for_each, not_, op, valid
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _palette, _pin, _set, out, then
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_DESTROY, FN_HAS_AUTHORITY, FN_SET_ACTOR_LOC, FN_SET_ACTOR_ROT,
    FN_SET_HIDDEN, FN_SOCKET_TRANSFORM)
from uebp.nodes.math import (
    FN_AND, FN_CLAMP, FN_DIV_FF, FN_EQ_CC, FN_EQ_FF, FN_EQ_OO, FN_GE_FF, FN_GREATER_FF,
    FN_MAKE_TRANSFORM, FN_MAX_FF, FN_SUB_FF, FN_TRANSFORM_LOC, FN_VLERP)
from uebp.nodes.palette import NODE_SPAWN
from uebp.nodes.system import (
    FN_ALL_ACTORS, FN_GET_GAME_STATE, FN_OBJECT_CLASS, FN_SERVER_WORLD_TIME, FN_TIME_SECONDS)


def server_now(g):
    """Pure: the server's world time as this machine has it (its own, with
    authority)."""
    return out(g.call(FN_SERVER_WORLD_TIME, self=out(g.call(FN_GET_GAME_STATE))))


def _now(g):
    return out(g.call(FN_TIME_SECONDS))


def _f(g, fn, a, b):
    """fn(a, b) of two floats; ``b`` a pin or a number (a literal stays on B)."""
    n = g.call(fn, A=a)
    if isinstance(b, (int, float)):
        _set(n, "B", float(b))
    else:
        _connect(b, _pin(n, "B"))
    return out(n)


def _author_gone(g, execs, refresh):
    """The stand-in is destroyed and forgotten. Returns the exec pin after."""
    flow = then(g.call(FN_DESTROY, execs, self=g.get(WV.ThrowFlyer)))
    flow = g.put(WV.ThrowFlyer, None, [flow])
    flow = g.put(WV.ThrowTwin, None, [flow])
    # An item it hid in the hand and the hand still has is shown again.
    let_go = g.get(WV.ThrowLetGo)
    kept, free = g.branch(op(g, FN_AND, valid(g, let_go),
                             op(g, FN_EQ_OO, let_go, g.get(WV.Held))), [flow])
    shown = then(g.call(FN_SET_HIDDEN, [kept], self=let_go, bNewHidden="false"))
    flow = g.put(WV.ThrowLetGo, None, [shown, free])
    if refresh:
        flow = g.put(WV.NeedsRefresh, "true", [flow])
    return flow


def author_launch_event(ed, square):
    """ThrowLaunch: a client's stand-in leaves on the server's curve.
    ``square(ed, item, exec_in)`` is the release's square-up
    (throw_flight._author_square). Before Fx_Throw, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.custom_event(ed, THROW_LAUNCH, LAUNCH_PARAMS))
    start = out(event, START_PARAM)
    client, _owner_flies_the_item = g.branch(not_(g, authority(g)), [then(event)])
    had, none = g.branch(valid(g, g.get(WV.ThrowFlyer)), [client])
    gone = then(g.call(FN_DESTROY, [had], self=g.get(WV.ThrowFlyer)))
    spawn = g.keep(_palette(ed, NODE_SPAWN))
    _connect(out(event, CLASS_PARAM), _pin(spawn, "Class"))
    _connect(out(g.call(FN_MAKE_TRANSFORM, Location=start)), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    # The item still in the thrower's hand on this machine is the one in the
    # air: its own leaving comes with the actor's channel, a frame or more
    # behind this message, and two would show until then.
    held = g.get(WV.Held)
    has, empty = g.branch(valid(g, held), [gone, none])
    thrown = op(g, FN_EQ_CC, out(g.call(FN_OBJECT_CLASS, Object=held)),
                out(event, CLASS_PARAM))
    it, other = g.branch(thrown, [has])
    let = g.put(WV.ThrowLetGo, held, [it])
    hid = then(g.call(FN_SET_HIDDEN, [let], self=held, bNewHidden="true"))
    for e in (empty, other, hid):
        _connect(e, _pin(spawn, "execute"))
    item = out(spawn)
    # In the air, so not a pick-up; burning or hot is the server's word, and
    # this copy's own Tick shows it and puts nothing out.
    flow = g.iput(item, IV.Dropped, "false", [then(spawn)])
    flow = g.iput(item, LIT_VAR, out(event, LIT_PARAM), [flow])
    flow = g.iput(item, HOT_VAR, out(event, HOT_PARAM), [flow])
    flow = g.put(WV.ThrowFlyer, item, [flow])
    flow = g.put(WV.ThrowStart, start, [flow])
    flow = g.put(WV.ThrowLast, start, [flow])
    flow = g.put(WV.ThrowVelocity, out(event, VELOCITY_PARAM), [flow])
    # This machine's clock at the release: now, less what the server's has
    # run since. Never negative: the thrower's own reading may be ahead.
    run = out(g.call(FN_MAX_FF, A=_f(g, FN_SUB_FF, server_now(g), out(event, TIME_PARAM))))
    flow = g.put(WV.ThrowTime, _f(g, FN_SUB_FF, _now(g), run), [flow])
    flow = g.put(WV.ThrowStamp, out(event, TIME_PARAM), [flow])
    flow = g.put(WV.ThrowStopped, "false", [flow])
    flow = g.put(WV.ThrowEnded, "false", [flow])
    flow = g.put(WV.ThrowTwin, None, [flow])
    square(ed, g.get(WV.ThrowFlyer), flow)
    ed.add_comment_to_nodes(
        f"{THROW_LAUNCH} (throw_standin.py), a client's: a local actor of the thrown "
        "item's class, never replicated, leaves from Start on the server's curve, "
        "burning or hot as the item is and squared up as the item was. Its start is "
        "this machine's clock set back by what the server's has run since Time, so "
        "a late launch shortens the flight. The Tick flies it (throw_flight.py). "
        "With authority this does nothing: the item itself flies.", g.made)
    return event


def author_named(g, exec_in, cast):
    """Multicast_Throw on the copy its gate turns away, the owning client,
    which predicted the launch: its stand-in is the one the server means
    (ThrowStamp = Time), and keeps its own timing. With none in the air (the
    server threw for it) the launch is flown as anyone's."""
    mine, none = g.branch(valid(g, g.get(WV.ThrowFlyer)), [exec_in])
    g.put(WV.ThrowStamp, out(cast, TIME_PARAM), [mine])
    call = g.keep(_node(g.ed, THROW_LAUNCH))
    for param, _type in LAUNCH_PARAMS:
        _connect(out(cast, param), _pin(call, param))
    _connect(none, _pin(call, "execute"))


def author_end_event(ed):
    """Multicast_ThrowEnd: the server's word of where the item came to rest.
    A client's stand-in of that throw is turned as the item lies and starts
    for there. Before the Tick, whose flight calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.multicast_event(ed, THROW_END, END_PARAMS, reliable=True))
    flyer = g.get(WV.ThrowFlyer)
    client, _server = g.branch(not_(g, authority(g)), [then(event)])
    flying, _none = g.branch(valid(g, flyer), [client])
    this, _other = g.branch(op(g, FN_EQ_FF, out(event, TIME_PARAM), g.get(WV.ThrowStamp)),
                            [flying])
    flow = g.put(WV.ThrowEndFrom, out(g.call(FN_ACTOR_LOC, self=flyer)), [this])
    flow = g.put(WV.ThrowEndAt, out(event, AT_PARAM), [flow])
    flow = g.put(WV.ThrowEndOff, out(event, OFF_PARAM), [flow])
    flow = g.put(WV.ThrowEndParent, out(event, PARENT_PARAM), [flow])
    flow = g.put(WV.ThrowEndBone, out(event, BONE_PARAM), [flow])
    flow = g.put(WV.ThrowEndTime, _now(g), [flow])
    flow = g.put(WV.ThrowEnded, "true", [flow])
    g.call(FN_SET_ACTOR_ROT, [flow], self=flyer, NewRotation=out(event, TURN_PARAM))
    ed.add_comment_to_nodes(
        f"{THROW_END} (throw_standin.py): the server's word, reliable, that the "
        "thrown item came to rest: where and how turned, and for a blade left in a "
        "body the mesh and bone it rides and where on that bone. A client's "
        "stand-in of that throw (the same Time) stops flying and is moved there by "
        "the Tick. With authority this does nothing.", g.made)
    return event


def author_refused_event(ed):
    """Client_ThrowRefused: the server would not make the throw. The owning
    client's predicted stand-in is taken back and its hand shown again.
    Before Server_Throw, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.client_event(ed, THROW_REFUSED, (), reliable=True))
    client, _server = g.branch(not_(g, authority(g)), [then(event)])
    had, none = g.branch(valid(g, g.get(WV.ThrowFlyer)), [client])
    back = g.put(WV.NeedsRefresh, "true", [_author_gone(g, [had], False), none])
    back = g.put(WV.ThrowLetGo, None, [back])
    held, _empty = g.branch(valid(g, g.get(WV.Held)), [back])
    g.call(FN_SET_HIDDEN, [held], self=g.get(WV.Held), bNewHidden="false")
    ed.add_comment_to_nodes(
        f"{THROW_REFUSED} (throw_standin.py), to the owning client: the server "
        "refused the throw it predicted. Its stand-in is destroyed, and the item "
        "is in its hand again.", g.made)
    return event


def _author_find_twin(g, execs):
    """ThrowTwin := the replicated item of this throw, once this machine has
    it: the copy (no authority here) whose ThrowStamp is this stand-in's.
    Returns the exec pins to carry on from."""
    known, unknown = g.branch(valid(g, g.get(WV.ThrowTwin)), execs)
    every = g.call(FN_ALL_ACTORS, [unknown])
    _pin(every, "ActorClass").set_pin_value(ITEM_CLASS_PATH)
    item, _i, body, done = for_each(g, out(every, "OutActors"), [then(every)])
    same = op(g, FN_EQ_FF, g.iget(item, IV.ThrowStamp), g.get(WV.ThrowStamp))
    copy = not_(g, out(g.call(FN_HAS_AUTHORITY, self=item)))
    found, _not_it = g.branch(op(g, FN_AND, same, copy), [body])
    g.put(WV.ThrowTwin, item, [found])
    return [known, done]


def _author_settle(g, execs):
    """The stand-in is moved from where the end found it to where the server
    says the item lies, over THROW_SETTLE_S. Returns (the settled float pin,
    the exec pins after the move)."""
    flyer = g.get(WV.ThrowFlyer)
    since = _f(g, FN_SUB_FF, _now(g), g.get(WV.ThrowEndTime))
    part = g.call(FN_CLAMP, Value=_f(g, FN_DIV_FF, since, THROW_SETTLE_S))
    _set(part, "Min", 0.0)
    _set(part, "Max", 1.0)
    part = out(part)
    parent = g.get(WV.ThrowEndParent)
    borne, lying = g.branch(valid(g, parent), execs)
    # In a body: where that bone is on this machine, this frame.
    bone = g.call(FN_SOCKET_TRANSFORM, self=parent, InSocketName=g.get(WV.ThrowEndBone))
    on_bone = out(g.call(FN_TRANSFORM_LOC, T=out(bone), Location=g.get(WV.ThrowEndOff)))
    rides = g.call(FN_SET_ACTOR_LOC, [borne], self=flyer, NewLocation=out(
        g.call(FN_VLERP, A=g.get(WV.ThrowEndFrom), B=on_bone, Alpha=part)))
    rests = g.call(FN_SET_ACTOR_LOC, [lying], self=flyer, NewLocation=out(
        g.call(FN_VLERP, A=g.get(WV.ThrowEndFrom), B=g.get(WV.ThrowEndAt), Alpha=part)))
    return part, [then(rides), then(rests)]


def _author_standin_upkeep(ed, exec_ins):
    """In the Tick, on a client with a stand-in: find the replicated item it
    stands in for, move it to where the server says the throw ended, and give
    way to that item once it lies there. Returns the exit exec pins."""
    g = _G(ed, ITEM_CLASS_PATH)
    mine = op(g, FN_AND, valid(g, g.get(WV.ThrowFlyer)), not_(g, authority(g)))
    standing, none = g.branch(mine, exec_ins)
    # The item the thrower's own hand let go (its prediction) stays hidden
    # while it is still the hand's: the sights write Held's every frame.
    let_go = g.get(WV.ThrowLetGo)
    still, not_held = g.branch(valid(g, let_go), [standing])
    in_hand, other = g.branch(op(g, FN_EQ_OO, let_go, g.get(WV.Held)), [still])
    tucked = then(g.call(FN_SET_HIDDEN, [in_hand], self=let_go, bNewHidden="true"))
    ended, flying = g.branch(g.get(WV.ThrowEnded),
                             _author_find_twin(g, [not_held, other, tucked]))

    part, moved = _author_settle(g, [ended])
    settled, moving = g.branch(_f(g, FN_GE_FF, part, 1.0), moved)
    twin = g.get(WV.ThrowTwin)
    here, absent = g.branch(valid(g, twin), [settled])
    lies = op(g, FN_AND, g.iget(twin, IV.InWorld), g.iget(twin, IV.Dropped))
    rests, not_yet = g.branch(lies, [here])
    # The hand-off, on one frame: the item shown, the stand-in destroyed.
    flow = g.iput(twin, IV.Released, "true", [rests])
    shown = g.call(FN_SET_HIDDEN, [flow], self=twin, bNewHidden="false")
    given = _author_gone(g, [then(shown)], False)
    # No replicated item followed the end: the stand-in does not lie for ever.
    waited = _f(g, FN_GREATER_FF, _f(g, FN_SUB_FF, _now(g), g.get(WV.ThrowEndTime)),
                THROW_END_WAIT_S)
    alone, waiting = g.branch(waited, [absent, not_yet])
    dropped = _author_gone(g, [alone], False)

    # Nothing ended it: the word was lost with its thrower.
    old = _f(g, FN_GREATER_FF, _f(g, FN_SUB_FF, _now(g), g.get(WV.ThrowTime)), THROW_ORPHAN_S)
    orphan, young = g.branch(old, [flying])
    lost = _author_gone(g, [orphan], True)
    ed.add_comment_to_nodes(
        "A client's stand-in for a thrown item (throw_standin.py): once the "
        f"server's end has come it is moved there over {THROW_SETTLE_S:g} s, and "
        "gives way to the replicated item of the same ThrowStamp on the frame that "
        "item, lying there on this machine too, is shown. One nothing ends, or no "
        "item follows, is destroyed.", g.made)
    return [none, moving, given, waiting, dropped, young, lost]
