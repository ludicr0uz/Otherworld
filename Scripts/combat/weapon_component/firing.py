"""Pulling the trigger: the round and the cooldown, the shot's one draw
inside the accuracy cloud, and one trace per pellet around it. What a pellet
that connects does is impact.py.
"""

from combat.game_state import DEBUG_MODE_VAR
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from combat.paths import GAME_MODE_CLASS_PATH, ITEM_CLASS_PATH
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.weapon_component.common import _prop, _trace_defaults
from combat.weapon_component.impact import _author_impact
from combat.weapon_component.tracer import _author_tracer
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_DEG2RAD, FN_MUL_VF, FN_NORMAL, FN_RAND_CONE, FN_SUB_II,
    FN_SUB_VV)
from uebp.nodes.palette import MACRO_FOR_LOOP, NODE_BREAK_HIT, NODE_CAST_GAME_MODE
from uebp.nodes.system import FN_GET_GAME_MODE, FN_PLAY_SOUND, FN_TIME_SECONDS, FN_TRACE

# The shot's direction, drawn once per trigger pull inside AimSpread.
SHOT_DIRECTION_VAR = "ShotDirection"


def _author_fire(ed, held, muzzle, exec_in):
    """One trigger pull: the fire sound, then one trace per pellet from the muzzle.

    All the aiming was done in _author_resolve_aim; what is left here is the
    spread, in two layers. The shot draws ONE direction inside the accuracy
    cloud (AimSpread, around the muzzle-to-AimPoint line) into ShotDirection;
    then each pellet jitters that inside the weapon's own PelletSpreadDegrees
    and traces the weapon's own range. A single-round gun has no pattern, so
    its round flies down the draw -- the same code path as the eight-pellet
    shotgun, which is why the pistol needed no second implementation.

    Ammunition is spent here rather than in the gate that allowed the shot: the
    gate decides, this does. Both the round and the cooldown are written before
    a single pellet is traced, so nothing downstream can leave the weapon
    having fired for free.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # --- what the shot costs -------------------------------------------------
    # Unconditional, on every weapon. Loaded is only ever *read* behind
    # UsesAmmo, so letting a weapon without ammunition count into the negatives costs
    # nothing and saves a branch on the one path that runs eight traces.
    was = keep(ed.add_get_member_variable_node("Loaded", ITEM_CLASS_PATH))
    _connect(held, _pin(was, "self"))
    spent = keep(_node(ed, FN_SUB_II))
    _connect(out(was, "Loaded"), _pin(spent, "A"))
    _set(spent, "B", 1)
    burn = keep(ed.add_set_member_variable_node("Loaded", ITEM_CLASS_PATH))
    _connect(held, _pin(burn, "self"))
    _connect(out(spent), _pin(burn, "Loaded"))
    _connect(exec_in, _pin(burn, "execute"))

    now = keep(_node(ed, FN_TIME_SECONDS))
    every, every_n = _prop(ed, "FireInterval", held)
    keep(every_n)
    again = keep(_node(ed, FN_ADD_FF))
    _connect(out(now), _pin(again, "A"))
    _connect(every, _pin(again, "B"))
    cool = keep(ed.add_set_member_variable_node("NextFireTime", ITEM_CLASS_PATH))
    _connect(held, _pin(cool, "self"))
    _connect(out(again), _pin(cool, "NextFireTime"))
    _connect(then(burn), _pin(cool, "execute"))

    # --- is anyone watching the tracers? -------------------------------------
    # Read once per shot and cached on this component, rather than read per
    # pellet: the pellet loop needs a plain bool it can branch on, and a
    # GetGameMode plus a cast eight times over for one flag is eight times the
    # work for the same answer.
    mode = keep(_node(ed, FN_GET_GAME_MODE))
    as_mode = keep(_palette(ed, NODE_CAST_GAME_MODE))
    _connect(out(mode), _pin(as_mode, "Object"))
    _connect(then(cool), _pin(as_mode, "execute"))
    flag = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_MODE_CLASS_PATH))
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(flag, "self"))
    note = keep(ed.add_set_member_variable_node(DEBUG_MODE_VAR))
    _connect(out(flag, DEBUG_MODE_VAR), _pin(note, DEBUG_MODE_VAR))
    _connect(then(as_mode), _pin(note, "execute"))
    # A GameMode of the wrong class cannot say; not drawing is the safe answer,
    # and the component's own default is already false.
    after_cost = [then(note), out(as_mode, "CastFailed")]

    aim_get = keep(ed.add_get_member_variable_node("AimPoint"))
    delta = keep(_node(ed, FN_SUB_VV))
    _connect(out(aim_get, "AimPoint"), _pin(delta, "A"))
    _connect(muzzle, _pin(delta, "B"))
    direction_n = keep(_node(ed, FN_NORMAL))
    _connect(out(delta), _pin(direction_n, "A"))
    direction = out(direction_n)

    snd_pin, snd_n = _prop(ed, "FireSound", held)
    keep(snd_n)
    play = keep(_node(ed, FN_PLAY_SOUND))
    _connect(snd_pin, _pin(play, "Sound"))
    _connect(muzzle, _pin(play, "Location"))
    for tail in after_cost:
        _connect(tail, _pin(play, "execute"))

    pel_pin, pel_n = _prop(ed, "PelletCount", held)
    keep(pel_n)
    last = keep(_node(ed, FN_SUB_II))
    _connect(pel_pin, _pin(last, "A"))
    _set(last, "B", 1)

    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    keep(loop)
    _loose_pin(loop, "FirstIndex").set_pin_value("0")
    _connect(out(last), _loose_pin(loop, "LastIndex"))
    _connect(_author_shot_direction(ed, direction, then(play), keep), _loose_pin(loop, "execute"))

    # Each pellet: the weapon's own pattern around the shot's direction. Zero
    # on a single-round gun, so its one pellet flies exactly down the draw.
    pattern, pattern_n = _prop(ed, "PelletSpreadDegrees", held)
    keep(pattern_n)
    rad = keep(_node(ed, FN_DEG2RAD))
    _connect(pattern, _pin(rad, "A"))
    shot_get = keep(ed.add_get_member_variable_node(SHOT_DIRECTION_VAR))
    cone = keep(_node(ed, FN_RAND_CONE))
    _connect(out(shot_get, SHOT_DIRECTION_VAR), _pin(cone, "ConeDir"))
    _connect(out(rad), _pin(cone, "ConeHalfAngleInRadians"))
    rng_pin, rng_n = _prop(ed, "WeaponRange", held)
    keep(rng_n)
    reach = keep(_node(ed, FN_MUL_VF))
    _connect(out(cone), _pin(reach, "A"))
    _connect(rng_pin, _pin(reach, "B"))
    end = keep(_node(ed, FN_ADD_VV))
    _connect(muzzle, _pin(end, "A"))
    _connect(out(reach), _pin(end, "B"))

    trace = keep(_node(ed, FN_TRACE))
    _connect(muzzle, _pin(trace, "Start"))
    _connect(out(end), _pin(trace, "End"))
    _trace_defaults(trace)
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(trace, "execute"))

    brk = keep(_palette(ed, NODE_BREAK_HIT))
    _connect(out(trace, "OutHit"), _loose_pin(brk, "Hit"))

    # The tracer, in debug mode only (tracer.py). It starts at the barrel, so
    # what you see is the line the pellet took and not a line from the camera
    # -- which is what makes it worth having while tuning the aim solve, and
    # what makes it wrong to leave switched on in the game.
    drawn, after_tracer = _author_tracer(ed, trace, brk)
    made.extend(drawn)

    hit = keep(ed.add_branch_node())
    _connect(out(trace), _pin(hit, "Condition"))
    # Both arms of the tracer branch carry on: whether a line was drawn has
    # nothing to do with whether the pellet connected.
    for tail in after_tracer:
        _connect(tail, _pin(hit, "execute"))

    ed.add_comment_to_nodes(
        "Fire: one round and one cooldown stamp first, then origin at the "
        "muzzle, direction muzzle -> AimPoint drawn once inside AimSpread, "
        "then each pellet inside the weapon's own pattern. "
        "The tracer leaves the barrel and ends where the pellet stopped "
        "-- when DebugMode is on, which is the only time it is drawn at all.",
        made)

    _author_impact(ed, brk, held, then(hit))
    # The direction goes back too, so the shot's noise cone is the pellets' line.
    return _loose_pin(loop, "Completed", is_input=False), direction


def _author_shot_direction(ed, direction, exec_in, keep):
    """ShotDirection = a random direction within AimSpread of `direction`.

    Stored, because RandomUnitVectorInCone is pure: read per pellet it would
    be a new draw per pellet and the shotgun's pattern would lose its centre.
    Down the sights AimSpread is zero, and VRandCone returns the direction
    itself for a zero cone, so the shot goes exactly where the reticle is.
    Returns the exec pin to carry on from.
    """
    cloud = keep(ed.add_get_member_variable_node(AIM_SPREAD_VAR))
    rad = keep(_node(ed, FN_DEG2RAD))
    _connect(out(cloud, AIM_SPREAD_VAR), _pin(rad, "A"))
    draw = keep(_node(ed, FN_RAND_CONE))
    _connect(direction, _pin(draw, "ConeDir"))
    _connect(out(rad), _pin(draw, "ConeHalfAngleInRadians"))
    hold = keep(ed.add_set_member_variable_node(SHOT_DIRECTION_VAR))
    _connect(out(draw), _pin(hold, SHOT_DIRECTION_VAR))
    _connect(exec_in, _pin(hold, "execute"))
    return then(hold)
