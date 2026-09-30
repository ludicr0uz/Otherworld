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
"""

from combat.anim_blueprint import AIM_SLOT
from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.nodes import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_ADD_FF, FN_ADD_VV, FN_AND, FN_ANIM_INSTANCE,
    FN_CLAMP, FN_GE_FF, FN_GET_COMP, FN_GET_OWNER, FN_MUL_VF, FN_NOT, FN_PLAY_SLOT, FN_SUB_FF,
    FN_TIME_SECONDS, INF, NODE_BREAK_HIT, NODE_CAST_HEALTH,
)
from combat.paths import HEALTH_CLASS_PATH
from combat.tuning import COMBAT
from combat.weapon_component.common import _trace_defaults

PUNCH_ANIM_VAR = "PunchAnim"
PUNCH_QUEUED_VAR = "PunchQueued"
PUNCH_PENDING_VAR = "PunchPending"
NEXT_PUNCH_VAR = "NextPunchTime"
PUNCH_DUE_VAR = "PunchDueTime"
PUNCH_BLEND_S = 0.1

FN_SPHERE_TRACE = "/Script/Engine.KismetSystemLibrary.SphereTraceSingle"


def _and(ed, a, b, x, y):
    n = _at(_node(ed, FN_AND), x, y)
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    return _pin(n, "ReturnValue", is_input=False)


def _get(ed, name, x, y):
    return _pin(_at(ed.add_get_member_variable_node(name), x, y), name, is_input=False)


def _stamp(ed, var, delay, exec_in, x, y):
    """var = now + delay; returns the exec pin after the Set."""
    now = _at(_node(ed, FN_TIME_SECONDS), x, y + 200)
    later = _at(_node(ed, FN_ADD_FF), x + 240, y + 200)
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(later, "A"))
    _set(later, "B", delay)
    s = _at(ed.add_set_member_variable_node(var), x + 480, y)
    _connect(_pin(later, "ReturnValue", is_input=False), _pin(s, var))
    _connect(exec_in, _pin(s, "execute"))
    return BEL.find_then_pin(s)


def _set_bool(ed, var, value, exec_in, x, y):
    s = _at(ed.add_set_member_variable_node(var), x, y)
    _set(s, var, "true" if value else "false")
    _connect(exec_in, _pin(s, "execute"))
    return BEL.find_then_pin(s)


def _author_punch(ed, tap, armed_out, steady, guarded, unspent, exec_ins, x0, y0):
    """The three stages, chained. ``exec_ins`` all run into the press gate;
    returns the exits of the blow stage, for the next block to take."""
    # --- press ---------------------------------------------------------------
    # Every term is a plain bool, so folding them is safe: nothing here reads
    # through Held, only asks IsValid of it.
    bare = _at(_node(ed, FN_NOT), x0, y0 + 300)
    _connect(armed_out, _pin(bare, "A"))
    now = _at(_node(ed, FN_TIME_SECONDS), x0, y0 + 460)
    rested = _at(_node(ed, FN_GE_FF), x0 + 240, y0 + 460)
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(rested, "A"))
    _connect(_get(ed, NEXT_PUNCH_VAR, x0, y0 + 580), _pin(rested, "B"))
    cond = _and(ed, _and(ed, tap, _pin(bare, "ReturnValue", is_input=False),
                         x0 + 240, y0 + 300),
                _and(ed, _and(ed, steady, guarded, x0 + 240, y0 + 380),
                     _and(ed, unspent, _pin(rested, "ReturnValue", is_input=False),
                          x0 + 480, y0 + 460),
                     x0 + 480, y0 + 380),
                x0 + 720, y0 + 300)
    press = _at(ed.add_branch_node(), x0 + 960, y0)
    _connect(cond, _pin(press, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(press, "execute"))
    queued = _set_bool(ed, PUNCH_QUEUED_VAR, True, BEL.find_then_pin(press),
                       x0 + 1200, y0)

    # --- swing ---------------------------------------------------------------
    swing = _at(ed.add_branch_node(), x0 + 1500, y0)
    _connect(_get(ed, PUNCH_QUEUED_VAR, x0 + 1260, y0 + 200), _pin(swing, "Condition"))
    _connect(queued, _pin(swing, "execute"))
    _connect(BEL.find_else_pin(press), _pin(swing, "execute"))
    step = _set_bool(ed, PUNCH_QUEUED_VAR, False, BEL.find_then_pin(swing),
                     x0 + 1740, y0)
    step = _stamp(ed, NEXT_PUNCH_VAR, COMBAT.punch_interval_s, step, x0 + 1980, y0)
    step = _stamp(ed, PUNCH_DUE_VAR, COMBAT.punch_impact_s, step, x0 + 2700, y0)
    step = _set_bool(ed, PUNCH_PENDING_VAR, True, step, x0 + 3420, y0)

    mesh = _get(ed, "OwnerMesh", x0 + 3420, y0 + 300)
    anim = _at(_node(ed, FN_ANIM_INSTANCE), x0 + 3660, y0 + 300)
    _connect(mesh, _pin(anim, "self"))
    play = _at(_node(ed, FN_PLAY_SLOT), x0 + 3900, y0)
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(play, "self"))
    _connect(_get(ed, PUNCH_ANIM_VAR, x0 + 3660, y0 + 440), _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", PUNCH_BLEND_S)
    _set(play, "BlendOutTime", PUNCH_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", 1)
    _connect(step, _pin(play, "execute"))

    ed.add_comment_to_nodes(
        "Empty hands: the fire key throws a punch. The press only queues it "
        "(PunchQueued), so the swing can be started without a key; the swing "
        "stamps the cooldown and when the blow lands, then plays the clip into "
        f"{AIM_SLOT}, upper body only.",
        [press, swing, play])

    # --- blow ----------------------------------------------------------------
    return _author_blow(ed, (BEL.find_then_pin(play), BEL.find_else_pin(swing)),
                        x0 + 4300, y0)


def _author_blow(ed, exec_ins, x0, y0):
    """PunchPending and due: sweep a sphere forward from the chest, and take
    COMBAT.punch_damage off the first body with a health component."""
    now = _at(_node(ed, FN_TIME_SECONDS), x0, y0 + 460)
    due = _at(_node(ed, FN_GE_FF), x0 + 240, y0 + 460)
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(due, "A"))
    _connect(_get(ed, PUNCH_DUE_VAR, x0, y0 + 580), _pin(due, "B"))
    gate = _at(ed.add_branch_node(), x0 + 720, y0)
    _connect(_and(ed, _get(ed, PUNCH_PENDING_VAR, x0 + 240, y0 + 300),
                  _pin(due, "ReturnValue", is_input=False), x0 + 480, y0 + 300),
             _pin(gate, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(gate, "execute"))
    step = _set_bool(ed, PUNCH_PENDING_VAR, False, BEL.find_then_pin(gate),
                     x0 + 960, y0)

    owner = _at(_node(ed, FN_GET_OWNER), x0 + 960, y0 + 300)
    owner_out = _pin(owner, "ReturnValue", is_input=False)
    loc = _at(_node(ed, FN_ACTOR_LOC), x0 + 1200, y0 + 300)
    _connect(owner_out, _pin(loc, "self"))
    chest = _at(_node(ed, FN_ADD_VV), x0 + 1440, y0 + 300)
    _connect(_pin(loc, "ReturnValue", is_input=False), _pin(chest, "A"))
    _connect(_vec(ed, 0.0, 0.0, COMBAT.punch_chest_cm, x0 + 1200, y0 + 440),
             _pin(chest, "B"))
    chest_out = _pin(chest, "ReturnValue", is_input=False)
    fwd = _at(_node(ed, FN_ACTOR_FORWARD), x0 + 1200, y0 + 600)
    _connect(owner_out, _pin(fwd, "self"))
    # Multiply_VectorFloat's B is promoted to a vector: drive it with one.
    reach = _at(_node(ed, FN_MUL_VF), x0 + 1440, y0 + 600)
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(reach, "A"))
    r = COMBAT.punch_reach_cm
    _connect(_vec(ed, r, r, r, x0 + 1200, y0 + 740), _pin(reach, "B"))
    end = _at(_node(ed, FN_ADD_VV), x0 + 1680, y0 + 500)
    _connect(chest_out, _pin(end, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(end, "B"))

    trace = _at(_node(ed, FN_SPHERE_TRACE), x0 + 1920, y0)
    _connect(chest_out, _pin(trace, "Start"))
    _connect(_pin(end, "ReturnValue", is_input=False), _pin(trace, "End"))
    _set(trace, "Radius", COMBAT.punch_radius_cm)
    _trace_defaults(trace)
    _connect(step, _pin(trace, "execute"))

    hit = _at(ed.add_branch_node(), x0 + 2200, y0)
    _connect(_pin(trace, "ReturnValue", is_input=False), _pin(hit, "Condition"))
    _connect(BEL.find_then_pin(trace), _pin(hit, "execute"))
    brk = _at(_palette(ed, NODE_BREAK_HIT), x0 + 2200, y0 + 300)
    _connect(_pin(trace, "OutHit", is_input=False), _loose_pin(brk, "Hit"))

    comp = _at(_node(ed, FN_GET_COMP), x0 + 2440, y0 + 300)
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 2700, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(hit), _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    get_h = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 2960, y0 + 300)
    _connect(as_health, _pin(get_h, "self"))
    sub = _at(_node(ed, FN_SUB_FF), x0 + 3200, y0 + 300)
    _connect(_pin(get_h, "Health", is_input=False), _pin(sub, "A"))
    _set(sub, "B", COMBAT.punch_damage)
    clamp = _at(_node(ed, FN_CLAMP), x0 + 3440, y0 + 300)
    _connect(_pin(sub, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = _at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 3700, y0)
    _connect(as_health, _pin(set_h, "self"))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(set_h, "Health"))
    _connect(BEL.find_then_pin(cast), _pin(set_h, "execute"))

    # The same three stamps a pellet leaves (impact.py): the health bar, the
    # kill's credit, and which way the flinch goes.
    now2 = _at(_node(ed, FN_TIME_SECONDS), x0 + 3700, y0 + 300)
    stamp = _at(ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH),
                x0 + 3960, y0)
    _connect(as_health, _pin(stamp, "self"))
    _connect(_pin(now2, "ReturnValue", is_input=False), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(BEL.find_then_pin(set_h), _pin(stamp, "execute"))
    blame = _at(ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR,
                                                HEALTH_CLASS_PATH), x0 + 4220, y0)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(BEL.find_then_pin(stamp), _pin(blame, "execute"))
    from_where = _at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR,
                                                     HEALTH_CLASS_PATH),
                     x0 + 4480, y0)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False),
             _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(BEL.find_then_pin(blame), _pin(from_where, "execute"))

    ed.add_comment_to_nodes(
        f"The blow, {COMBAT.punch_impact_s} s into the swing: a "
        f"{COMBAT.punch_radius_cm:.0f} cm sphere swept {COMBAT.punch_reach_cm:.0f} cm "
        f"forward from the chest. The first thing with a health component "
        f"loses {COMBAT.punch_damage:.0f} HP, stamped like a pellet hit.",
        [gate, trace, hit, cast, set_h, stamp, blame, from_where])

    return (BEL.find_then_pin(from_where), BEL.find_else_pin(gate),
            BEL.find_else_pin(hit), _loose_pin(cast, "CastFailed", is_input=False))
