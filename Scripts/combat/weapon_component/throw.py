"""The throw: hold the throw key to see where the item in hand would land,
click the fire key to throw it. Letting the throw key up instead calls it off.
Whatever is held throws, gun, knife or food alike.

While the throw key is down the fire key is the throw's alone: Tick's fire
gate takes _author_throw_key's NOT, so the click neither fires, eats nor
slashes. The click that threw is spent (TriggerSpent) until it comes up, so
it cannot fire the automatic equipped in the thrown item's place.

The throw is a server request (task M20, combat/strike_vars.py): the arc, the
cocked arm and the wind-up are the owning machine's, and on the frame the
hand lets go it asks Server_Throw(Start, Velocity). The event is the release,
and the flight runs in the Tick's upkeep, with authority. In single player
the event is a plain call.

_author_throw, called from Tick's local arm, runs three fragments:

  _author_throw_aim      while the key is held with something in hand and
                         nothing already in the air: predict the arc and draw
                         it as dots on BP_ThrowArc (throw_arc.py), the arm
                         cocked meanwhile (throw_ready.py); on a click with
                         the arc already showing, or with the key let go,
                         wipe it, and let go the arm comes down
  _author_throw_windup   on the frame of that click: play the throw's clip;
                         a moment later, when its hand lets go, run the
                         release (throw_windup.py)
  _author_throw_ask      on that frame: the launch, the throw's sound, and
                         Server_Throw

Server_Throw (author_throw_event) is then, with authority:

  _author_throw_release  store the launch, detach the item and take it out
                         of the inventory, exactly as a drop does, and make
                         it an actor every client is sent (item_world.py)

and the upkeep, on the machine with authority:

  _author_throw_flight   every frame something is in the air: move it along
                         the same curve, tumbling, and when a trace between
                         two frames hits, set it down on the ground as a
                         dropped item (throw_flight.py)

The launch is read on the frame of the release, not of the click: the view
may have moved in the wind-up, and the item goes where it looks then.

The launch is throw_launch.py's: a throw is sent at the point the reticle
rests on, pitched to pass through it, so the arc stands under the reticle and
ends on it. Where the item's speed cannot reach that point, or it is the sky,
the throw is tipped above the view by the held item's own ThrowArcDegrees
(throw_tuning.THROW_PITCH_VAR), which the GUN SETTINGS tab can move per gun.
The speed is the item's ThrowSpeed: a melee weapon's is fast, so it flies
flat and reaches far (throw_tuning.MELEE_THROW), and it leaves the hand
squared up to the throw (throw_flight._author_square).

ThrowKeyForced and ThrowClickForced are the probe's stand-ins for the held
key and the click: no key can be injected into a headless game
(probes/probe_throw.py). Each is OR'd with its key and is false in every real
game.
"""

from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.paths import THROW_ARC_CLASS_PATH
from combat.item_world import author_into_world
from combat.strike_vars import (
    SERVER_THROW, START_PARAM, THROW_PARAMS, THROW_SPEED_SLACK, THROW_START_REACH_CM,
    VELOCITY_PARAM)
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import (
    THROW_ARC_HZ, THROW_ARC_SIM_S, THROW_DOT_CM, THROW_GRAVITY_Z, THROW_MARK_CM,
    THROW_SPEED_VAR,
)
from combat.paths import ITEM_CLASS_PATH
from combat.weapon_component.record import authority
from combat.weapon_component.shot import _author_alive
from combat.weapon_component.slot_nodes import not_, op, valid
from uebp import net
from uebp.g import _G
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.inventory import _detach_rules
from combat.weapon_component.throw_flight import (
    THROWN_VAR, THROW_LAST_VAR, THROW_START_VAR, THROW_TIME_VAR,
    THROW_VELOCITY_VAR, _author_square,
)
from combat import item_vars as IV
from combat.fx_vars import SHARP_PARAM, THROW, THROW_CLIP, THROW_FX_PARAMS
from combat.fx_vars import START_PARAM as FX_START_PARAM
from combat.weapon_component import fx
from Sound.play import _author_sound
from combat.weapon_component.throw_launch import _author_launch
from combat.weapon_component.throw_ready import (
    _author_ready_down, _author_throw_ready,
)
from combat.weapon_component.throw_windup import (
    _author_throw_clip, _author_throw_windup, _author_wound_down, _winding,
)
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_DETACH, FN_GET_OWNER, FN_GET_TRANSFORM, FN_IS_KEY_DOWN,
    FN_SET_ACTOR_LOC, FN_SET_HIDDEN)
from uebp.nodes.array import FN_ARR_REMOVE
from uebp.nodes.math import (
    FN_AND, FN_CLAMP_VSIZE, FN_DISTANCE, FN_LE_FF, FN_MAKE_TRANSFORM, FN_MUL_FF, FN_NOT,
    FN_OR)
from uebp.nodes.palette import MACRO_FOR_EACH, NODE_BREAK_HIT, NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID, FN_TIME_SECONDS
from combat.weapon_component import vars as WV

THROW_AIMING_VAR = "ThrowAiming"      # the arc was drawn last frame
THROW_FORCED_VAR = "ThrowKeyForced"   # a probe holding the key
THROW_CLICK_FORCED_VAR = "ThrowClickForced"   # a probe clicking the fire key
THROW_ARC_VAR = "ThrowArc"            # the BP_ThrowArc, spawned on first aim
THROW_ARC_CLASS_VAR = "ThrowArcClass"


def _author_throw_key(ed, pc_out, key_pin):
    """(wants, free): the throw key is down (or a probe holds it); and neither
    that nor a throw winding up, which Tick's fire gate takes. Plain reads:
    safe in a condition that is pulled with empty hands."""
    down = _node(ed, FN_IS_KEY_DOWN)
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))
    forced = ed.add_get_member_variable_node(THROW_FORCED_VAR)
    wants = _node(ed, FN_OR)
    _connect(out(down), _pin(wants, "A"))
    _connect(out(forced, THROW_FORCED_VAR), _pin(wants, "B"))
    busy = _node(ed, FN_OR)
    _connect(out(wants), _pin(busy, "A"))
    _connect(_winding(ed), _pin(busy, "B"))
    free = _node(ed, FN_NOT)
    _connect(out(busy), _pin(free, "A"))
    return out(wants), out(free)


def _author_throw(ed, pc_out, owner_out, held, armed_out, wants, tap, exec_ins):
    """The throw where the keys are, in Tick's chain: aim, wind-up, and the
    ask on the frame the hand lets go. Returns the exit exec pins."""
    aim_exits, clicked, start, velocity = _author_throw_aim(
        ed, pc_out, owner_out, held, armed_out, wants, tap, exec_ins)
    let_go, called_off, waiting = _author_throw_windup(ed, held, clicked, aim_exits)
    asked = _author_throw_ask(ed, held, start, velocity, let_go)
    over = _author_wound_down(ed, (asked, called_off))
    return (over, waiting)


def _add_dot(ed, dots, location, scale, exec_in):
    """One world-space instance on the arc's Dots at location."""
    xf = _node(ed, FN_MAKE_TRANSFORM)
    _connect(location, _pin(xf, "Location"))
    _connect(_vec(ed, *scale), _pin(xf, "Scale"))
    add = _node(ed, "/Script/Engine.InstancedStaticMeshComponent.AddInstance")
    _connect(dots, _pin(add, "self"))
    _connect(out(xf), _pin(add, "InstanceTransform"))
    _set(add, "bWorldSpace", True)
    _connect(exec_in, _pin(add, "execute"))
    return add


def _author_throw_aim(ed, pc_out, owner_out, held, armed_out, wants, tap,
                      exec_ins):
    """The key held: draw the arc. Returns (exits, released, start, velocity):
    exits run on to the next block; released is the exec pin of the frame the
    fire key is clicked over a shown arc, for _author_throw_windup."""
    start, velocity = _author_launch(ed, pc_out, owner_out, held)

    thrown = ed.add_get_member_variable_node(THROWN_VAR)
    flying = _node(ed, FN_IS_VALID)
    _connect(out(thrown, THROWN_VAR), _pin(flying, "Object"))
    # One throw at a time: none in the air, none winding up.
    busy = _node(ed, FN_OR)
    _connect(out(flying), _pin(busy, "A"))
    _connect(_winding(ed), _pin(busy, "B"))
    idle = _node(ed, FN_NOT)
    _connect(out(busy), _pin(idle, "A"))
    ready = _node(ed, FN_AND)
    _connect(armed_out, _pin(ready, "A"))
    _connect(out(idle), _pin(ready, "B"))
    aimed = _node(ed, FN_AND)
    _connect(wants, _pin(aimed, "A"))
    _connect(out(ready), _pin(aimed, "B"))

    gate = ed.add_branch_node()
    _connect(out(aimed), _pin(gate, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(gate, "execute"))

    # --- the click: the throw, if the arc was already showing ----------------
    # ThrowAiming is still last frame's here: a click on the very frame the
    # key goes down throws nothing, as no arc has been seen yet.
    click_forced = ed.add_get_member_variable_node(THROW_CLICK_FORCED_VAR)
    clicked = _node(ed, FN_OR)
    _connect(tap, _pin(clicked, "A"))
    _connect(out(click_forced, THROW_CLICK_FORCED_VAR), _pin(clicked, "B"))
    shown = ed.add_get_member_variable_node(THROW_AIMING_VAR)
    lets_go = _node(ed, FN_AND)
    _connect(out(clicked), _pin(lets_go, "A"))
    _connect(out(shown, THROW_AIMING_VAR), _pin(lets_go, "B"))
    click = ed.add_branch_node()
    _connect(out(lets_go), _pin(click, "Condition"))
    _connect(then(gate), _pin(click, "execute"))

    # --- the arc actor, spawned the first time it is wanted -----------------
    arc_get = ed.add_get_member_variable_node(THROW_ARC_VAR)
    arc = out(arc_get, THROW_ARC_VAR)
    have = _node(ed, FN_IS_VALID)
    _connect(arc, _pin(have, "Object"))
    spawned = ed.add_branch_node()
    _connect(out(have), _pin(spawned, "Condition"))
    _connect(else_(click), _pin(spawned, "execute"))
    cls = ed.add_get_member_variable_node(THROW_ARC_CLASS_VAR)
    where = _node(ed, FN_GET_TRANSFORM)
    _connect(owner_out, _pin(where, "self"))
    spawn = _palette(ed, NODE_SPAWN)
    _connect(out(cls, THROW_ARC_CLASS_VAR), _pin(spawn, "Class"))
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(else_(spawned), _pin(spawn, "execute"))
    keep = ed.add_set_member_variable_node(THROW_ARC_VAR)
    _connect(out(spawn), _pin(keep, THROW_ARC_VAR))
    _connect(then(spawn), _pin(keep, "execute"))

    dots_get = ed.add_get_member_variable_node(ARC_COMPONENT, THROW_ARC_CLASS_PATH)
    _connect(arc, _pin(dots_get, "self"))
    dots = out(dots_get, ARC_COMPONENT)
    clear = _node(ed, "/Script/Engine.InstancedStaticMeshComponent.ClearInstances")
    _connect(dots, _pin(clear, "self"))
    _connect(then(spawned), _pin(clear, "execute"))
    _connect(then(keep), _pin(clear, "execute"))

    # --- the arc: the engine's own ballistic prediction, traced -------------
    predict = _node(ed, "/Script/Engine.GameplayStatics."
                            "Blueprint_PredictProjectilePath_ByTraceChannel")
    _connect(start, _pin(predict, "StartPos"))
    _connect(velocity, _pin(predict, "LaunchVelocity"))
    _set(predict, "bTracePath", True)
    _set(predict, "ProjectileRadius", 0.0)
    # Visibility, the channel the flight traces on, so both stop at the same
    # things (a wanderer's capsule blocks it: hit_zones.make_shootable).
    _set(predict, "TraceChannel", "ECC_Visibility")
    _set(predict, "bTraceComplex", False)
    _set(predict, "DrawDebugType", "None")
    _set(predict, "SimFrequency", THROW_ARC_HZ)
    _set(predict, "MaxSimTime", THROW_ARC_SIM_S)
    _set(predict, "OverrideGravityZ", THROW_GRAVITY_Z)
    _connect(then(clear), _pin(predict, "execute"))
    on = ed.add_set_member_variable_node(THROW_AIMING_VAR)
    _set(on, THROW_AIMING_VAR, True)
    _connect(then(predict), _pin(on, "execute"))
    # The arm is cocked for as long as the arc shows (throw_ready.py).
    posed = _author_throw_ready(ed, held, then(on))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    loop
    _connect(out(predict, "OutPathPositions"), _loose_pin(loop, "Array"))
    for pin in posed:
        _connect(pin, _loose_pin(loop, "Exec"))
    d = THROW_DOT_CM / 100.0
    _add_dot(ed, dots, _loose_pin(loop, "ArrayElement", is_input=False), (d, d, d),
             _loose_pin(loop, "LoopBody", is_input=False))
    # The disc where it comes down, if the arc comes down on anything.
    landed = ed.add_branch_node()
    _connect(out(predict), _pin(landed, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(landed, "execute"))
    hit = _palette(ed, NODE_BREAK_HIT)
    _connect(out(predict, "OutHit"), _loose_pin(hit, "Hit"))
    mark = _add_dot(ed, dots, _loose_pin(hit, "Location", is_input=False),
                    tuple(c / 100.0 for c in THROW_MARK_CM),
                    then(landed))

    # --- not aiming: was it, last frame? Then the aim ends here -------------
    was_get = ed.add_get_member_variable_node(THROW_AIMING_VAR)
    was = ed.add_branch_node()
    _connect(out(was_get, THROW_AIMING_VAR), _pin(was, "Condition"))
    _connect(else_(gate), _pin(was, "execute"))
    wipe = _node(ed, "/Script/Engine.InstancedStaticMeshComponent.ClearInstances")
    _connect(dots, _pin(wipe, "self"))
    _connect(then(was), _pin(wipe, "execute"))
    _connect(then(click), _pin(wipe, "execute"))
    off = ed.add_set_member_variable_node(THROW_AIMING_VAR)
    _set(off, THROW_AIMING_VAR, False)
    _connect(then(wipe), _pin(off, "execute"))
    # Which of the two ended it? Still aimed (key down, item in hand) can only
    # be the click: that is the throw. Otherwise the key came up, or the hand
    # emptied under it (eaten, dropped), and nothing is thrown.
    release = ed.add_branch_node()
    _connect(out(aimed), _pin(release, "Condition"))
    _connect(then(off), _pin(release, "execute"))
    # The click is spent: still down next frame, it must not fire the
    # automatic that takes the thrown item's place (consume.py's latch).
    spend = ed.add_set_member_variable_node(TRIGGER_SPENT)
    _set(spend, TRIGGER_SPENT, True)
    _connect(then(release), _pin(spend, "execute"))

    # Called off: the cocked arm comes down.
    lowered = _author_ready_down(ed, else_(release))

    exits = (then(mark), else_(landed), else_(was), lowered)
    return exits, then(spend), start, velocity


def _author_throw_ask(ed, held, start, velocity, exec_in):
    """The hand lets go, on the machine with the keys: the launch is stored
    (it is a pure chain off the view), the air the item goes through is heard,
    and the throw is asked of the server. Returns the exit exec pin. Reads
    Held: run it only where the hand is known to hold something."""
    g = _G(ed, ITEM_CLASS_PATH)
    flow = g.put(THROW_START_VAR, start, [exec_in])
    flow = g.put(THROW_VELOCITY_VAR, velocity, [flow])
    # Heard from where it left the hand, by whoever threw it, at once (a
    # blade cuts the air, anything else pushes it aside): a client of a
    # server's prediction; with authority the event tells everyone.
    owns, predicts = g.branch(authority(g), [flow])
    heard = fx.predict(g, THROW, [predicts], **{FX_START_PARAM: g.get(THROW_START_VAR),
                                              SHARP_PARAM: g.iget(held, IV.Melee)})
    ask = g.keep(_node(ed, SERVER_THROW))
    _connect(g.get(THROW_START_VAR), _pin(ask, START_PARAM))
    _connect(g.get(THROW_VELOCITY_VAR), _pin(ask, VELOCITY_PARAM))
    for pin in (owns, heard):
        _connect(pin, _pin(ask, "execute"))
    ed.add_comment_to_nodes(
        f"The throw is asked of the server ({SERVER_THROW}, throw.py), with where "
        "it leaves from and how fast, read on this frame. A client of a server "
        "plays its sound at once, its prediction. With authority (single player) "
        "the event is the throw.",
        g.made)
    return then(ask)


def _author_throw_sound(g, exec_in, event):
    """The body of Fx_Throw: the air the item goes through, from where it
    left the hand (Start): a blade (Sharp) cuts it, anything else pushes it
    aside."""
    sharp_in, blunt_in = g.branch(out(event, SHARP_PARAM), [exec_in])
    _author_sound(g.ed, WV.ThrowSharpSounds, out(event, FX_START_PARAM), sharp_in)
    _author_sound(g.ed, WV.ThrowSounds, out(event, FX_START_PARAM), blunt_in)


def author_throw_fx(ed):
    """The throw's cosmetic pairs (fx.py): its sound, which the thrower
    predicts, and its clip, which the thrower's wind-up plays in both modes
    (throw_windup.py), so only the others owe it. Before the Tick and the
    throw's event."""
    fx.pair(ed, THROW, THROW_FX_PARAMS, _author_throw_sound, fx.UNPREDICTED)
    fx.pair(ed, THROW_CLIP, (), lambda g, e, _ev: _author_throw_clip(ed, e), fx.OTHERS)


def author_throw_event(ed):
    """Server_Throw(Start, Velocity): the release, on the machine that owns
    the item. Refused unless there is an item in a living hand, nothing of
    this player's already in the air, and Start within THROW_START_REACH_CM of
    this machine's copy of the thrower; the speed is capped at the item's own
    ThrowSpeed. Before the Tick, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_THROW, THROW_PARAMS))
    start = out(event, START_PARAM)
    held = g.get(WV.Held)
    armed, _empty = g.branch(valid(g, held), [then(event)])
    alive = _author_alive(g, [armed])
    idle = not_(g, valid(g, g.get(THROWN_VAR)))
    here = g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))
    near = op(g, FN_LE_FF, out(g.call(FN_DISTANCE, V1=start, V2=out(here))),
              str(THROW_START_REACH_CM))
    go, _refused = g.branch(op(g, FN_AND, idle, near), alive)
    top = op(g, FN_MUL_FF, g.iget(held, THROW_SPEED_VAR), str(THROW_SPEED_SLACK))
    capped = g.call(FN_CLAMP_VSIZE, A=out(event, VELOCITY_PARAM), Max=top)
    ed.add_comment_to_nodes(
        f"{SERVER_THROW} (throw.py): the owning client's throw, on the frame its "
        "hand lets go. Refused unless there is an item in a living hand, nothing "
        f"of this player's in the air and the start within {THROW_START_REACH_CM:g} "
        "cm of this machine's copy of them; the speed is capped at the item's "
        "own. Everyone is told of the throw (its sound at Start, and the clip "
        "on the other players' copies). Then the release: the item leaves the "
        "hand and the inventory, replicates to everyone, and the Tick flies it.",
        g.made)
    told = fx.tell(g, THROW, [go], **{FX_START_PARAM: start, SHARP_PARAM: g.iget(held, IV.Melee)})
    told = fx.tell(g, THROW_CLIP, [told])
    _author_throw_release(ed, held, start, out(capped), told)


def _author_throw_release(ed, held, start, velocity, exec_in):
    """Let go, with authority: the launch is stored for the flight, the item
    leaves the hand and the inventory the way a drop's does, and from here on
    it is an actor every client sees (InWorld, replicated). Returns the exit
    exec pin. Reads Held: run it only where the hand is known to hold
    something."""
    now = _node(ed, FN_TIME_SECONDS)
    prev = exec_in
    for var, value in ((THROW_START_VAR, start),
                       (THROW_LAST_VAR, start),
                       (THROW_VELOCITY_VAR, velocity),
                       (THROW_TIME_VAR, out(now)),
                       (THROWN_VAR, held)):
        n = ed.add_set_member_variable_node(var)
        _connect(value, _pin(n, var))
        _connect(prev, _pin(n, "execute"))
        prev = then(n)

    off = _node(ed, FN_DETACH)
    _connect(held, _pin(off, "self"))
    _detach_rules(off)
    _connect(prev, _pin(off, "execute"))
    # Shown, as a drop does: a scoped gun thrown from the sights was hidden.
    shown = _node(ed, FN_SET_HIDDEN)
    _connect(held, _pin(shown, "self"))
    _set(shown, "bNewHidden", False)
    _connect(then(off), _pin(shown, "execute"))
    put = _node(ed, FN_SET_ACTOR_LOC)
    _connect(held, _pin(put, "self"))
    _connect(start, _pin(put, "NewLocation"))
    _connect(then(shown), _pin(put, "execute"))
    squared = _author_square(ed, held, then(put))
    # The server's item is now the world's: every client is sent it.
    loosed = author_into_world(ed, held, squared)

    inv = ed.add_get_member_variable_node(WV.Inventory)
    idx = ed.add_get_member_variable_node(WV.EquippedIndex)
    remove = _node(ed, FN_ARR_REMOVE)
    _connect(out(inv, WV.Inventory), _pin(remove, "TargetArray"))
    _connect(out(idx, WV.EquippedIndex), _pin(remove, "IndexToRemove"))
    _connect(loosed, _pin(remove, "execute"))
    # Held set with nothing connected clears it, as in _author_drop.
    clear = ed.add_set_member_variable_node(WV.Held)
    _connect(then(remove), _pin(clear, "execute"))
    reset = ed.add_set_member_variable_node(WV.EquippedIndex)
    _set(reset, WV.EquippedIndex, 0)
    _connect(then(clear), _pin(reset, "execute"))
    dirty = ed.add_set_member_variable_node(WV.NeedsRefresh)
    _set(dirty, WV.NeedsRefresh, True)
    _connect(then(reset), _pin(dirty, "execute"))
    return then(dirty)
