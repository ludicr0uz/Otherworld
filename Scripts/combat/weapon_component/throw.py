"""The throw: hold the throw key to see where the item in hand would land,
click the fire key to throw it. Letting the throw key up instead calls it off.
Whatever is held throws, gun, knife or food alike.

While the throw key is down the fire key is the throw's alone: Tick's fire
gate takes _author_throw_key's NOT, so the click neither fires, eats nor
slashes. The click that threw is spent (TriggerSpent) until it comes up, so
it cannot fire the automatic equipped in the thrown item's place.

_author_throw, called from Tick, runs four fragments one after another:

  _author_throw_aim      while the key is held with something in hand and
                         nothing already in the air: predict the arc and draw
                         it as dots on BP_ThrowArc (throw_arc.py); on a click
                         with the arc already showing, or with the key let
                         go, wipe it
  _author_throw_windup   on the frame of that click: play the throw's clip;
                         a moment later, when its hand lets go, run the
                         release (throw_windup.py)
  _author_throw_release  on that frame: store the launch, detach the item
                         and take it out of the inventory, exactly as a drop
                         does
  _author_throw_flight   every frame something is in the air: move it along
                         the same curve, tumbling, and when a trace between
                         two frames hits, set it down on the ground as a
                         dropped item (throw_flight.py)

The launch is read on the frame of the release, not of the click: the view
may have moved in the wind-up, and the item goes where it looks then.

The arc's tip above the view is the held item's own ThrowArcDegrees
(throw_tuning.THROW_PITCH_VAR), so the GUN TUNING tab can move it per gun, and
its speed the item's ThrowSpeed: a melee weapon's are flat and fast
(throw_tuning.MELEE_THROW), and it leaves the hand squared up to the throw
(throw_flight._author_square).

ThrowKeyForced and ThrowClickForced are the probe's stand-ins for the held
key and the click: no key can be injected into a headless game
(probes/probe_throw.py). Each is OR'd with its key and is false in every real
game.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ADD_VV, FN_AND, FN_ARR_REMOVE, FN_BREAK_ROT,
    FN_CLAMP, FN_DETACH, FN_FORWARD, FN_GET_CONTROL_ROT, FN_GET_TRANSFORM,
    FN_IS_KEY_DOWN, FN_IS_VALID, FN_MAKE_ROT, FN_MAKE_TRANSFORM, FN_MAKE_VECTOR,
    FN_MUL_VF,
    FN_NORMALIZE_AXIS, FN_NOT, FN_OR, FN_SET_ACTOR_LOC, FN_SET_HIDDEN,
    FN_TIME_SECONDS, MACRO_FOR_EACH, NODE_BREAK_HIT, NODE_SPAWN,
)
from combat.paths import THROW_ARC_CLASS_PATH
from combat.throw_arc import ARC_COMPONENT
from combat.throw_tuning import (
    THROW_ARC_HZ, THROW_ARC_SIM_S, THROW_DOT_CM, THROW_GRAVITY_Z, THROW_MARK_CM,
    THROW_MAX_PITCH_DEG, THROW_PITCH_VAR, THROW_SPEED_VAR, THROW_START_FORWARD,
    THROW_START_UP,
)
from combat.weapon_component.common import _prop
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.inventory import _detach_rules
from combat.weapon_component.throw_flight import (
    THROWN_VAR, THROW_LAST_VAR, THROW_START_VAR, THROW_TIME_VAR,
    THROW_VELOCITY_VAR, _author_square, _author_throw_flight,
)
from combat.weapon_component.throw_windup import (
    _author_throw_windup, _author_wound_down, _winding,
)

THROW_AIMING_VAR = "ThrowAiming"      # the arc was drawn last frame
THROW_FORCED_VAR = "ThrowKeyForced"   # a probe holding the key
THROW_CLICK_FORCED_VAR = "ThrowClickForced"   # a probe clicking the fire key
THROW_ARC_VAR = "ThrowArc"            # the BP_ThrowArc, spawned on first aim
THROW_ARC_CLASS_VAR = "ThrowArcClass"


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _author_throw_key(ed, pc_out, key_pin, x0, y0):
    """(wants, free): the throw key is down (or a probe holds it); and neither
    that nor a throw winding up, which Tick's fire gate takes. Plain reads:
    safe in a condition that is pulled with empty hands."""
    down = _at(_node(ed, FN_IS_KEY_DOWN), x0, y0)
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))
    forced = _at(ed.add_get_member_variable_node(THROW_FORCED_VAR), x0, y0 + 140)
    wants = _at(_node(ed, FN_OR), x0 + 240, y0)
    _connect(_out(down), _pin(wants, "A"))
    _connect(_out(forced, THROW_FORCED_VAR), _pin(wants, "B"))
    busy = _at(_node(ed, FN_OR), x0 + 480, y0)
    _connect(_out(wants), _pin(busy, "A"))
    _connect(_winding(ed, x0, y0 + 280), _pin(busy, "B"))
    free = _at(_node(ed, FN_NOT), x0 + 720, y0)
    _connect(_out(busy), _pin(free, "A"))
    return _out(wants), _out(free)


def _author_throw(ed, pc_out, owner_out, held, armed_out, wants, tap, exec_ins,
                  x0, y0):
    """The whole throw, in Tick's chain: aim, wind-up, release, flight.
    Returns the exit exec pins."""
    aim_exits, clicked, start, velocity = _author_throw_aim(
        ed, pc_out, owner_out, held, armed_out, wants, tap, exec_ins, x0, y0)
    let_go, called_off, waiting = _author_throw_windup(
        ed, held, clicked, aim_exits, x0 + 3160, y0 + 2000)
    thrown = _author_throw_release(ed, held, start, velocity, let_go,
                                   x0 + 3160, y0 + 1200)
    over = _author_wound_down(ed, (thrown, called_off), x0 + 6300, y0 + 1200)
    return _author_throw_flight(ed, (over, waiting), x0, y0 + 2800)


def _author_launch(ed, pc_out, owner_out, held, x0, y0):
    """(start, velocity): where a throw leaves from and how fast, as pure pins.

    Along the view, tipped up the held item's ThrowArcDegrees and capped so a
    throw straight up does not land on the thrower, at its ThrowSpeed. Starts ahead of the
    capsule along the view's yaw, so neither the arc's trace nor the flight's
    starts inside the player. Reads Held: pull these only where it is valid.
    """
    view = _at(_node(ed, FN_GET_CONTROL_ROT), x0, y0)
    _connect(pc_out, _pin(view, "self"))
    parts = _at(_node(ed, FN_BREAK_ROT), x0 + 240, y0)
    _connect(_out(view), _pin(parts, "InRot"))
    # The controller's pitch comes back 0..360; 350 is ten degrees down.
    signed = _at(_node(ed, FN_NORMALIZE_AXIS), x0 + 480, y0)
    _connect(_out(parts, "Pitch"), _pin(signed, "Angle"))
    lifted = _at(_node(ed, FN_ADD_FF), x0 + 720, y0)
    _connect(_out(signed), _pin(lifted, "A"))
    tip, _tip_n = _prop(ed, THROW_PITCH_VAR, held, x0 + 480, y0 + 140)
    _connect(tip, _pin(lifted, "B"))
    capped = _at(_node(ed, FN_CLAMP), x0 + 960, y0)
    _connect(_out(lifted), _pin(capped, "Value"))
    _set(capped, "Min", -89.0)
    _set(capped, "Max", THROW_MAX_PITCH_DEG)
    aim = _at(_node(ed, FN_MAKE_ROT), x0 + 1200, y0)
    _connect(_out(capped), _pin(aim, "Pitch"))
    _connect(_out(parts, "Yaw"), _pin(aim, "Yaw"))
    along = _at(_node(ed, FN_FORWARD), x0 + 1440, y0)
    _connect(_out(aim), _pin(along, "InRot"))
    velocity = _at(_node(ed, FN_MUL_VF), x0 + 1680, y0)
    _connect(_out(along), _pin(velocity, "A"))
    # Vector x float is a wildcard whose B is a vector: the speed, three times.
    speed, _speed_n = _prop(ed, THROW_SPEED_VAR, held, x0 + 1200, y0 + 140)
    speeds = _at(_node(ed, FN_MAKE_VECTOR), x0 + 1440, y0 + 140)
    for axis in ("X", "Y", "Z"):
        _connect(speed, _pin(speeds, axis))
    _connect(_out(speeds), _pin(velocity, "B"))

    flat = _at(_node(ed, FN_MAKE_ROT), x0 + 1200, y0 + 300)
    _connect(_out(parts, "Yaw"), _pin(flat, "Yaw"))
    ahead_dir = _at(_node(ed, FN_FORWARD), x0 + 1440, y0 + 300)
    _connect(_out(flat), _pin(ahead_dir, "InRot"))
    ahead = _at(_node(ed, FN_MUL_VF), x0 + 1680, y0 + 300)
    _connect(_out(ahead_dir), _pin(ahead, "A"))
    f = THROW_START_FORWARD
    _connect(_vec(ed, f, f, f, x0 + 1440, y0 + 440), _pin(ahead, "B"))
    here = _at(_node(ed, FN_ACTOR_LOC), x0 + 1680, y0 + 560)
    _connect(owner_out, _pin(here, "self"))
    raised = _at(_node(ed, FN_ADD_VV), x0 + 1920, y0 + 560)
    _connect(_out(here), _pin(raised, "A"))
    _connect(_vec(ed, 0.0, 0.0, THROW_START_UP, x0 + 1680, y0 + 700), _pin(raised, "B"))
    start = _at(_node(ed, FN_ADD_VV), x0 + 2160, y0 + 300)
    _connect(_out(raised), _pin(start, "A"))
    _connect(_out(ahead), _pin(start, "B"))
    return _out(start), _out(velocity)


def _add_dot(ed, dots, location, scale, exec_in, x, y):
    """One world-space instance on the arc's Dots at location."""
    xf = _at(_node(ed, FN_MAKE_TRANSFORM), x, y + 200)
    _connect(location, _pin(xf, "Location"))
    _connect(_vec(ed, *scale, x - 240, y + 340), _pin(xf, "Scale"))
    add = _at(_node(ed, "/Script/Engine.InstancedStaticMeshComponent.AddInstance"), x + 280, y)
    _connect(dots, _pin(add, "self"))
    _connect(_out(xf), _pin(add, "InstanceTransform"))
    _set(add, "bWorldSpace", "true")
    _connect(exec_in, _pin(add, "execute"))
    return add


def _author_throw_aim(ed, pc_out, owner_out, held, armed_out, wants, tap,
                      exec_ins, x0, y0):
    """The key held: draw the arc. Returns (exits, released, start, velocity):
    exits run on to the next block; released is the exec pin of the frame the
    fire key is clicked over a shown arc, for _author_throw_windup."""
    start, velocity = _author_launch(ed, pc_out, owner_out, held, x0, y0 + 1400)

    thrown = _at(ed.add_get_member_variable_node(THROWN_VAR), x0, y0 + 480)
    flying = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 480)
    _connect(_out(thrown, THROWN_VAR), _pin(flying, "Object"))
    # One throw at a time: none in the air, none winding up.
    busy = _at(_node(ed, FN_OR), x0 + 360, y0 + 600)
    _connect(_out(flying), _pin(busy, "A"))
    _connect(_winding(ed, x0 - 120, y0 + 700), _pin(busy, "B"))
    idle = _at(_node(ed, FN_NOT), x0 + 480, y0 + 480)
    _connect(_out(busy), _pin(idle, "A"))
    ready = _at(_node(ed, FN_AND), x0 + 480, y0 + 300)
    _connect(armed_out, _pin(ready, "A"))
    _connect(_out(idle), _pin(ready, "B"))
    aimed = _at(_node(ed, FN_AND), x0 + 720, y0 + 200)
    _connect(wants, _pin(aimed, "A"))
    _connect(_out(ready), _pin(aimed, "B"))

    gate = _at(ed.add_branch_node(), x0 + 960, y0)
    _connect(_out(aimed), _pin(gate, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(gate, "execute"))

    # --- the click: the throw, if the arc was already showing ----------------
    # ThrowAiming is still last frame's here: a click on the very frame the
    # key goes down throws nothing, as no arc has been seen yet.
    click_forced = _at(ed.add_get_member_variable_node(THROW_CLICK_FORCED_VAR),
                       x0 + 480, y0 - 300)
    clicked = _at(_node(ed, FN_OR), x0 + 720, y0 - 300)
    _connect(tap, _pin(clicked, "A"))
    _connect(_out(click_forced, THROW_CLICK_FORCED_VAR), _pin(clicked, "B"))
    shown = _at(ed.add_get_member_variable_node(THROW_AIMING_VAR), x0 + 720, y0 - 160)
    lets_go = _at(_node(ed, FN_AND), x0 + 960, y0 - 300)
    _connect(_out(clicked), _pin(lets_go, "A"))
    _connect(_out(shown, THROW_AIMING_VAR), _pin(lets_go, "B"))
    click = _at(ed.add_branch_node(), x0 + 1080, y0 - 100)
    _connect(_out(lets_go), _pin(click, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(click, "execute"))

    # --- the arc actor, spawned the first time it is wanted -----------------
    arc_get = _at(ed.add_get_member_variable_node(THROW_ARC_VAR), x0 + 960, y0 - 400)
    arc = _out(arc_get, THROW_ARC_VAR)
    have = _at(_node(ed, FN_IS_VALID), x0 + 1200, y0 - 400)
    _connect(arc, _pin(have, "Object"))
    spawned = _at(ed.add_branch_node(), x0 + 1200, y0)
    _connect(_out(have), _pin(spawned, "Condition"))
    _connect(BEL.find_else_pin(click), _pin(spawned, "execute"))
    cls = _at(ed.add_get_member_variable_node(THROW_ARC_CLASS_VAR), x0 + 1200, y0 + 300)
    where = _at(_node(ed, FN_GET_TRANSFORM), x0 + 1200, y0 + 420)
    _connect(owner_out, _pin(where, "self"))
    spawn = _at(_palette(ed, NODE_SPAWN), x0 + 1460, y0 + 200)
    _connect(_out(cls, THROW_ARC_CLASS_VAR), _pin(spawn, "Class"))
    _connect(_out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_else_pin(spawned), _pin(spawn, "execute"))
    keep = _at(ed.add_set_member_variable_node(THROW_ARC_VAR), x0 + 1740, y0 + 200)
    _connect(_out(spawn), _pin(keep, THROW_ARC_VAR))
    _connect(BEL.find_then_pin(spawn), _pin(keep, "execute"))

    dots_get = _at(ed.add_get_member_variable_node(ARC_COMPONENT, THROW_ARC_CLASS_PATH),
                   x0 + 1740, y0 - 400)
    _connect(arc, _pin(dots_get, "self"))
    dots = _out(dots_get, ARC_COMPONENT)
    clear = _at(_node(ed, "/Script/Engine.InstancedStaticMeshComponent.ClearInstances"),
                x0 + 2000, y0)
    _connect(dots, _pin(clear, "self"))
    _connect(BEL.find_then_pin(spawned), _pin(clear, "execute"))
    _connect(BEL.find_then_pin(keep), _pin(clear, "execute"))

    # --- the arc: the engine's own ballistic prediction, traced -------------
    predict = _at(_node(ed, "/Script/Engine.GameplayStatics."
                            "Blueprint_PredictProjectilePath_ByTraceChannel"),
                  x0 + 2280, y0)
    _connect(start, _pin(predict, "StartPos"))
    _connect(velocity, _pin(predict, "LaunchVelocity"))
    _set(predict, "bTracePath", "true")
    _set(predict, "ProjectileRadius", 0.0)
    # Visibility, the channel the flight traces on, so both stop at the same
    # things (a wanderer's capsule blocks it: hit_zones.make_shootable).
    _set(predict, "TraceChannel", "ECC_Visibility")
    _set(predict, "bTraceComplex", "false")
    _set(predict, "DrawDebugType", "None")
    _set(predict, "SimFrequency", THROW_ARC_HZ)
    _set(predict, "MaxSimTime", THROW_ARC_SIM_S)
    _set(predict, "OverrideGravityZ", THROW_GRAVITY_Z)
    _connect(BEL.find_then_pin(clear), _pin(predict, "execute"))
    on = _at(ed.add_set_member_variable_node(THROW_AIMING_VAR), x0 + 2560, y0)
    _set(on, THROW_AIMING_VAR, "true")
    _connect(BEL.find_then_pin(predict), _pin(on, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, x0 + 2820, y0)
    _connect(_out(predict, "OutPathPositions"), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(on), _loose_pin(loop, "Exec"))
    d = THROW_DOT_CM / 100.0
    _add_dot(ed, dots, _loose_pin(loop, "ArrayElement", is_input=False), (d, d, d),
             _loose_pin(loop, "LoopBody", is_input=False), x0 + 3100, y0 - 300)
    # The disc where it comes down, if the arc comes down on anything.
    landed = _at(ed.add_branch_node(), x0 + 3100, y0 + 300)
    _connect(_out(predict), _pin(landed, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(landed, "execute"))
    hit = _at(_palette(ed, NODE_BREAK_HIT), x0 + 3100, y0 + 500)
    _connect(_out(predict, "OutHit"), _loose_pin(hit, "Hit"))
    mark = _add_dot(ed, dots, _loose_pin(hit, "Location", is_input=False),
                    tuple(c / 100.0 for c in THROW_MARK_CM),
                    BEL.find_then_pin(landed), x0 + 3400, y0 + 300)

    # --- not aiming: was it, last frame? Then the aim ends here -------------
    was_get = _at(ed.add_get_member_variable_node(THROW_AIMING_VAR), x0 + 960, y0 + 700)
    was = _at(ed.add_branch_node(), x0 + 1200, y0 + 800)
    _connect(_out(was_get, THROW_AIMING_VAR), _pin(was, "Condition"))
    _connect(BEL.find_else_pin(gate), _pin(was, "execute"))
    wipe = _at(_node(ed, "/Script/Engine.InstancedStaticMeshComponent.ClearInstances"),
               x0 + 1460, y0 + 800)
    _connect(dots, _pin(wipe, "self"))
    _connect(BEL.find_then_pin(was), _pin(wipe, "execute"))
    _connect(BEL.find_then_pin(click), _pin(wipe, "execute"))
    off = _at(ed.add_set_member_variable_node(THROW_AIMING_VAR), x0 + 1740, y0 + 800)
    _set(off, THROW_AIMING_VAR, "false")
    _connect(BEL.find_then_pin(wipe), _pin(off, "execute"))
    # Which of the two ended it? Still aimed (key down, item in hand) can only
    # be the click: that is the throw. Otherwise the key came up, or the hand
    # emptied under it (eaten, dropped), and nothing is thrown.
    release = _at(ed.add_branch_node(), x0 + 2000, y0 + 800)
    _connect(_out(aimed), _pin(release, "Condition"))
    _connect(BEL.find_then_pin(off), _pin(release, "execute"))
    # The click is spent: still down next frame, it must not fire the
    # automatic that takes the thrown item's place (consume.py's latch).
    spend = _at(ed.add_set_member_variable_node(TRIGGER_SPENT), x0 + 2260, y0 + 800)
    _set(spend, TRIGGER_SPENT, "true")
    _connect(BEL.find_then_pin(release), _pin(spend, "execute"))

    exits = (BEL.find_then_pin(mark), BEL.find_else_pin(landed),
             BEL.find_else_pin(was), BEL.find_else_pin(release))
    return exits, BEL.find_then_pin(spend), start, velocity


def _author_throw_release(ed, held, start, velocity, exec_in, x0, y0):
    """Let go: the launch is stored for the flight, the item leaves the hand
    and the inventory the way a drop's does. Returns the exit exec pin.
    Reads Held: run it only where the hand is known to hold something."""
    now = _at(_node(ed, FN_TIME_SECONDS), x0, y0 + 300)
    prev = exec_in
    for i, (var, value) in enumerate(((THROW_START_VAR, start),
                                      (THROW_LAST_VAR, start),
                                      (THROW_VELOCITY_VAR, velocity),
                                      (THROW_TIME_VAR, _out(now)),
                                      (THROWN_VAR, held))):
        n = _at(ed.add_set_member_variable_node(var), x0 + 260 * i, y0)
        _connect(value, _pin(n, var))
        _connect(prev, _pin(n, "execute"))
        prev = BEL.find_then_pin(n)

    off = _at(_node(ed, FN_DETACH), x0 + 1300, y0)
    _connect(held, _pin(off, "self"))
    _detach_rules(off)
    _connect(prev, _pin(off, "execute"))
    # Shown, as a drop does: a scoped gun thrown from the sights was hidden.
    shown = _at(_node(ed, FN_SET_HIDDEN), x0 + 1560, y0)
    _connect(held, _pin(shown, "self"))
    _set(shown, "bNewHidden", "false")
    _connect(BEL.find_then_pin(off), _pin(shown, "execute"))
    put = _at(_node(ed, FN_SET_ACTOR_LOC), x0 + 1820, y0)
    _connect(held, _pin(put, "self"))
    _connect(start, _pin(put, "NewLocation"))
    _connect(BEL.find_then_pin(shown), _pin(put, "execute"))
    squared = _author_square(ed, held, BEL.find_then_pin(put), x0 + 1820, y0 - 500)

    inv = _at(ed.add_get_member_variable_node("Inventory"), x0 + 1820, y0 + 300)
    idx = _at(ed.add_get_member_variable_node("EquippedIndex"), x0 + 1820, y0 + 420)
    remove = _at(_node(ed, FN_ARR_REMOVE), x0 + 2080, y0)
    _connect(_out(inv, "Inventory"), _pin(remove, "TargetArray"))
    _connect(_out(idx, "EquippedIndex"), _pin(remove, "IndexToRemove"))
    for pin in squared:
        _connect(pin, _pin(remove, "execute"))
    # Held set with nothing connected clears it, as in _author_drop.
    clear = _at(ed.add_set_member_variable_node("Held"), x0 + 2340, y0)
    _connect(BEL.find_then_pin(remove), _pin(clear, "execute"))
    reset = _at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 2600, y0)
    _set(reset, "EquippedIndex", 0)
    _connect(BEL.find_then_pin(clear), _pin(reset, "execute"))
    dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), x0 + 2860, y0)
    _set(dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(reset), _pin(dirty, "execute"))
    return BEL.find_then_pin(dirty)
