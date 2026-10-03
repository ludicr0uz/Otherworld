"""The punch: the fire key with empty hands throws a fist.

Three stages, each a Branch on the component's own variables, so no stage
reads Held and none waits on a Delay (a component Tick cannot hold one):

  press   tap AND NOT IsValid(Held) AND NOT Sprinting AND NOT Blocking
          AND NOT TriggerSpent AND now >= NextPunchTime   --> PunchQueued
  swing   PunchQueued --> NextPunchTime, PunchDueTime, PunchPending,
          MM_Attack_01 (PunchAnim) into the upper-body slot
  blow    PunchPending AND now >= PunchDueTime --> a sphere in front of the
          chest; a body with BP_HealthComponent loses COMBAT.punch_damage

The press only queues, so a probe can throw a punch by writing PunchQueued
(no key can be injected into a headless game). The blow lands a moment into
the clip rather than on the press: a hit before the fist moves reads as a
shove from nowhere.

The clip plays into DefaultSlot, the ready pose's slot, which is upper body
only (anim_blueprint.py) -- the legs keep walking. With empty hands nothing
else plays there. Tuning is COMBAT.punch_* in tuning.py.

The swing and the blow are written once, for a Strike: its variables, clip and
numbers. The punch is PUNCH; the knife (knife.py) is the same two stages on a
Strike of its own, behind a press gate of its own.
"""

import dataclasses

from combat.anim_blueprint import AIM_SLOT
from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR
from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.paths import HEALTH_CLASS_PATH
from combat.tuning import COMBAT
from combat.weapon_component.common import _trace_defaults
from uebp.nodes.actor import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_ANIM_INSTANCE, FN_GET_COMP, FN_GET_OWNER,
    FN_PLAY_SLOT)
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_AND, FN_CLAMP, FN_GE_FF, FN_MUL_VF, FN_NOT, FN_SUB_FF, INF)
from uebp.nodes.palette import NODE_BREAK_HIT, NODE_CAST_HEALTH
from uebp.nodes.system import FN_SPHERE_TRACE, FN_TIME_SECONDS

PUNCH_ANIM_VAR = "PunchAnim"
PUNCH_QUEUED_VAR = "PunchQueued"
PUNCH_PENDING_VAR = "PunchPending"
NEXT_PUNCH_VAR = "NextPunchTime"
PUNCH_DUE_VAR = "PunchDueTime"
PUNCH_BLEND_S = 0.1


@dataclasses.dataclass(frozen=True)
class Strike:
    """One melee attack: the component's variables it runs on, and its numbers."""
    name: str
    anim_var: str
    queued_var: str
    pending_var: str
    next_var: str
    due_var: str
    interval_s: float
    impact_s: float
    damage: float
    reach_cm: float
    radius_cm: float
    chest_cm: float


PUNCH = Strike("punch", PUNCH_ANIM_VAR, PUNCH_QUEUED_VAR, PUNCH_PENDING_VAR,
               NEXT_PUNCH_VAR, PUNCH_DUE_VAR, COMBAT.punch_interval_s,
               COMBAT.punch_impact_s, COMBAT.punch_damage, COMBAT.punch_reach_cm,
               COMBAT.punch_radius_cm, COMBAT.punch_chest_cm)


def _and(ed, a, b):
    n = _node(ed, FN_AND)
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    return out(n)


def _get(ed, name):
    return out(ed.add_get_member_variable_node(name), name)


def _stamp(ed, var, delay, exec_in):
    """var = now + delay; returns the exec pin after the Set."""
    now = _node(ed, FN_TIME_SECONDS)
    later = _node(ed, FN_ADD_FF)
    _connect(out(now), _pin(later, "A"))
    _set(later, "B", delay)
    s = ed.add_set_member_variable_node(var)
    _connect(out(later), _pin(s, var))
    _connect(exec_in, _pin(s, "execute"))
    return then(s)


def _set_bool(ed, var, value, exec_in):
    s = ed.add_set_member_variable_node(var)
    _set(s, var, "true" if value else "false")
    _connect(exec_in, _pin(s, "execute"))
    return then(s)


def _author_punch(ed, tap, armed_out, steady, guarded, unspent, exec_ins):
    """The three stages, chained. ``exec_ins`` all run into the press gate;
    returns the exits of the blow stage, for the next block to take."""
    # --- press ---------------------------------------------------------------
    # Every term is a plain bool, so folding them is safe: nothing here reads
    # through Held, only asks IsValid of it.
    bare = _node(ed, FN_NOT)
    _connect(armed_out, _pin(bare, "A"))
    now = _node(ed, FN_TIME_SECONDS)
    rested = _node(ed, FN_GE_FF)
    _connect(out(now), _pin(rested, "A"))
    _connect(_get(ed, NEXT_PUNCH_VAR), _pin(rested, "B"))
    cond = _and(ed, _and(ed, tap, out(bare)),
                _and(ed, _and(ed, steady, guarded),
                     _and(ed, unspent, out(rested))))
    press = ed.add_branch_node()
    _connect(cond, _pin(press, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(press, "execute"))
    queued = _set_bool(ed, PUNCH_QUEUED_VAR, True, then(press))

    ed.add_comment_to_nodes(
        "Empty hands: the fire key throws a punch. The press only queues it "
        "(PunchQueued), so the swing can be started without a key.", [press])
    return _author_swing(ed, PUNCH, (queued, else_(press)))


def _author_swing(ed, strike, exec_ins, scenery=None, damage=None):
    """Queued: clear the queue, stamp the cooldown and when the blow lands,
    and play the strike's clip; then the blow stage. ``exec_ins`` all run into
    the swing's Branch; returns the exits of the blow stage. ``scenery`` and
    ``damage`` are the blow's (see _author_blow)."""
    swing = ed.add_branch_node()
    _connect(_get(ed, strike.queued_var), _pin(swing, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(swing, "execute"))
    step = _set_bool(ed, strike.queued_var, False, then(swing))
    step = _stamp(ed, strike.next_var, strike.interval_s, step)
    step = _stamp(ed, strike.due_var, strike.impact_s, step)
    step = _set_bool(ed, strike.pending_var, True, step)

    mesh = _get(ed, "OwnerMesh")
    anim = _node(ed, FN_ANIM_INSTANCE)
    _connect(mesh, _pin(anim, "self"))
    play = _node(ed, FN_PLAY_SLOT)
    _connect(out(anim), _pin(play, "self"))
    _connect(_get(ed, strike.anim_var), _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", PUNCH_BLEND_S)
    _set(play, "BlendOutTime", PUNCH_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", 1)
    _connect(step, _pin(play, "execute"))

    ed.add_comment_to_nodes(
        f"The {strike.name}'s swing: stamp the cooldown and when the blow lands, "
        f"then play the clip into {AIM_SLOT}, upper body only.",
        [swing, play])

    # --- blow ----------------------------------------------------------------
    return _author_blow(ed, strike, (then(play), else_(swing)), scenery, damage)


def _author_blow(ed, strike, exec_ins, scenery=None, damage=None):
    """Pending and due: sweep a sphere forward from the chest, and take the
    strike's damage off the first body with a health component.

    ``damage(ed, body, exec_in)``, if given, authors what this blow
    takes off the body it met, between the cast and the write, and returns
    (the amount's pin, its exits); without one it is the strike's damage, a
    literal (the knife's is hot_blow.py).

    ``scenery(ed, brk, exec_in)``, if given, authors what the blow does
    to something with no health, off the cast's failed arm, and returns its
    exits (the knife's chops a tree: chop.py)."""
    now = _node(ed, FN_TIME_SECONDS)
    due = _node(ed, FN_GE_FF)
    _connect(out(now), _pin(due, "A"))
    _connect(_get(ed, strike.due_var), _pin(due, "B"))
    gate = ed.add_branch_node()
    _connect(_and(ed, _get(ed, strike.pending_var), out(due)), _pin(gate, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(gate, "execute"))
    step = _set_bool(ed, strike.pending_var, False, then(gate))

    owner = _node(ed, FN_GET_OWNER)
    owner_out = out(owner)
    loc = _node(ed, FN_ACTOR_LOC)
    _connect(owner_out, _pin(loc, "self"))
    chest = _node(ed, FN_ADD_VV)
    _connect(out(loc), _pin(chest, "A"))
    _connect(_vec(ed, 0.0, 0.0, strike.chest_cm), _pin(chest, "B"))
    chest_out = out(chest)
    fwd = _node(ed, FN_ACTOR_FORWARD)
    _connect(owner_out, _pin(fwd, "self"))
    # Multiply_VectorFloat's B is promoted to a vector: drive it with one.
    reach = _node(ed, FN_MUL_VF)
    _connect(out(fwd), _pin(reach, "A"))
    r = strike.reach_cm
    _connect(_vec(ed, r, r, r), _pin(reach, "B"))
    end = _node(ed, FN_ADD_VV)
    _connect(chest_out, _pin(end, "A"))
    _connect(out(reach), _pin(end, "B"))

    trace = _node(ed, FN_SPHERE_TRACE)
    _connect(chest_out, _pin(trace, "Start"))
    _connect(out(end), _pin(trace, "End"))
    _set(trace, "Radius", strike.radius_cm)
    _trace_defaults(trace)
    _connect(step, _pin(trace, "execute"))

    hit = ed.add_branch_node()
    _connect(out(trace), _pin(hit, "Condition"))
    _connect(then(trace), _pin(hit, "execute"))
    brk = _palette(ed, NODE_BREAK_HIT)
    _connect(out(trace, "OutHit"), _loose_pin(brk, "Hit"))

    comp = _node(ed, FN_GET_COMP)
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = _palette(ed, NODE_CAST_HEALTH)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(then(hit), _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    get_h = ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(get_h, "self"))
    sub = _node(ed, FN_SUB_FF)
    _connect(out(get_h, "Health"), _pin(sub, "A"))
    met = (then(cast),)
    if damage:
        amount, met = damage(ed, _loose_pin(brk, "HitActor", is_input=False), met[0])
        _connect(amount, _pin(sub, "B"))
    else:
        _set(sub, "B", strike.damage)
    clamp = _node(ed, FN_CLAMP)
    _connect(out(sub), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(set_h, "self"))
    _connect(out(clamp), _pin(set_h, "Health"))
    for pin in met:
        _connect(pin, _pin(set_h, "execute"))

    # The same three stamps a pellet leaves (impact.py): the health bar, the
    # kill's credit, and which way the flinch goes.
    now2 = _node(ed, FN_TIME_SECONDS)
    stamp = ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(stamp, "self"))
    _connect(out(now2), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(then(set_h), _pin(stamp, "execute"))
    blame = ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(then(stamp), _pin(blame, "execute"))
    from_where = ed.add_set_member_variable_node(LAST_HIT_FROM_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False),
             _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(then(blame), _pin(from_where, "execute"))

    ed.add_comment_to_nodes(
        f"The {strike.name}'s blow, {strike.impact_s} s into the swing: a "
        f"{strike.radius_cm:.0f} cm sphere swept {strike.reach_cm:.0f} cm "
        f"forward from the chest. The first thing with a health component "
        f"loses {strike.damage:.0f} HP, stamped like a pellet hit.",
        [gate, trace, hit, cast, set_h, stamp, blame, from_where])

    failed = _loose_pin(cast, "CastFailed", is_input=False)
    missed = scenery(ed, brk, failed) if scenery else (failed,)
    return (then(from_where), else_(gate), else_(hit)) + tuple(missed)
