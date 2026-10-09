"""The punch: the fire key with empty hands throws a fist.

Three stages, each a Branch on the component's own variables, so no stage
reads Held and none waits on a Delay (a component Tick cannot hold one):

  press   tap AND NOT IsValid(Held) AND NOT Sprinting AND NOT Blocking
          AND NOT TriggerSpent AND now >= NextPunchTime   --> PunchQueued
  swing   PunchQueued --> Server_Punch, which (empty hands, alive, not
          guarding, off cooldown) stamps NextPunchTime and PunchDueTime, sets
          PunchPending and plays the skin's punch (PunchAnim) into the upper-body
          slot
  blow    PunchPending AND now >= PunchDueTime --> a sphere in front of the
          chest; a body with BP_HealthComponent loses COMBAT.punch_damage

The swing is a server request (task M20, combat/strike_vars.py), as the shot
is: the press and the queue are where the keys are, the Server event is the
swing, and the blow runs in the Tick's upkeep, on every copy, where only the
server's ever finds a strike pending. A client of a server plays the clip and
the swing's sound and stamps its own cooldown at once, its prediction; it
sweeps nothing. In single player the event is a plain call.

What everyone sees and hears of it is fx.py's (task M21): the clip and the
swing's sound are Fx_<strike.fx>, which the Server event tells everyone
through its Multicast and the owning client plays as its prediction; the
blow landing is Multicast_<strike.hit_fx>, told from the server's sweep to
every machine with a screen, the striker's included.

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
from combat.damage import hit as take_hit, owner_instigator
from net.guard import author_guard
from uebp.graph import (
    PIN, _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat import item_vars as IV
from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH
from combat.fx_vars import LOCATION_PARAM, PUNCH as PUNCH_FX, PUNCH_HIT, SOUND_AT_PARAMS
from combat.strike_vars import SERVER_PUNCH, STRIKE_GRACE_S
from combat.tuning import COMBAT
from combat.weapon_component import fx
from combat.weapon_component.record import authority
from combat.weapon_component.shot import _author_alive
from combat.weapon_component.slot_nodes import not_, op, valid
from uebp import net
from uebp.g import _G
from combat.weapon_component.common import _trace_defaults
from uebp.nodes.actor import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_ANIM_INSTANCE, FN_GET_COMP, FN_GET_OWNER,
    FN_PLAY_SLOT)
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_AND, FN_EQ_OO, FN_GE_FF, FN_MUL_VF, FN_NOT)
from uebp.nodes.palette import NODE_BREAK_HIT, NODE_CAST_HEALTH
from uebp.nodes.system import FN_SPHERE_TRACE, FN_TIME_SECONDS
from combat.weapon_component import look_vars as LV
from combat.weapon_component import vars as WV
from Sound.play import _author_sound

PUNCH_ANIM_VAR = WV.PunchAnim
PUNCH_QUEUED_VAR = WV.PunchQueued
PUNCH_PENDING_VAR = WV.PunchPending
NEXT_PUNCH_VAR = WV.NextPunchTime
PUNCH_DUE_VAR = WV.PunchDueTime
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
    # The takes of the blow landing on a body (Sound/sound_weapons.py).
    hit_sounds_var: str = WV.PunchHitSounds
    # The Server event that is this swing, and whether it wants a Melee item
    # in hand (the knife's) or empty hands (the punch's).
    event: str = SERVER_PUNCH
    armed: bool = False
    # The cosmetics (combat/fx_vars.py): the clip with the swing's sound, and
    # the blow landing.
    fx: str = PUNCH_FX
    hit_fx: str = PUNCH_HIT
    # How far into its clip the swing starts (the wind-up skipped), so the
    # blow's time can stay where the game has it under a longer clip.
    clip_start_s: float = 0.0
    # ((ready-pose variable, clip variable), ...): the swing plays that clip
    # instead while HandPose is that ready pose (the axe's, on the knife's
    # Strike). HandPose and not Held: every machine's copy has it (look.py).
    by_pose: tuple = ()


PUNCH = Strike("punch", PUNCH_ANIM_VAR, PUNCH_QUEUED_VAR, PUNCH_PENDING_VAR,
               NEXT_PUNCH_VAR, PUNCH_DUE_VAR, COMBAT.punch_interval_s,
               COMBAT.punch_impact_s, COMBAT.punch_damage, COMBAT.punch_reach_cm,
               COMBAT.punch_radius_cm, COMBAT.punch_chest_cm,
               clip_start_s=COMBAT.punch_clip_start_s)


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


def _author_punch_blow(ed, exec_ins):
    """The punch's blow stage, in the upkeep. Returns its exits."""
    return _author_blow(ed, PUNCH, exec_ins)


def _author_play(ed, strike, anim_var, exec_in):
    """One clip into the upper-body slot, once; returns the play node."""
    mesh = _get(ed, WV.OwnerMesh)
    anim = _node(ed, FN_ANIM_INSTANCE)
    _connect(mesh, _pin(anim, "self"))
    play = _node(ed, FN_PLAY_SLOT)
    _connect(out(anim), _pin(play, "self"))
    _connect(_get(ed, anim_var), _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", PUNCH_BLEND_S)
    _set(play, "BlendOutTime", PUNCH_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", 1)
    if strike.clip_start_s:
        _set(play, "InTimeToStartMontageAt", strike.clip_start_s)
    _connect(exec_in, _pin(play, "execute"))
    return play


def _author_clip(ed, strike, exec_in):
    """The strike's clip into the upper-body slot, and the air it moves,
    heard at the player. Which clip is the ready pose in hand's
    (``strike.by_pose``: a Branch each), else the strike's own. Returns (the
    exec pin after them, the strike's own play node)."""
    played = []
    for pose_var, anim_var in strike.by_pose:
        same = _node(ed, FN_EQ_OO)
        _connect(_get(ed, LV.HandPose), _pin(same, "A"))
        _connect(_get(ed, pose_var), _pin(same, "B"))
        pick = ed.add_branch_node()
        _connect(out(same), _pin(pick, "Condition"))
        _connect(exec_in, _pin(pick, "execute"))
        played.append(then(_author_play(ed, strike, anim_var, then(pick))))
        exec_in = else_(pick)
    play = _author_play(ed, strike, strike.anim_var, exec_in)
    owner = _node(ed, FN_GET_OWNER)
    here = _node(ed, FN_ACTOR_LOC)
    _connect(out(owner), _pin(here, "self"))
    after = _author_sound(ed, WV.SwingSounds, out(here), then(play))
    # Every play runs on into the one sound: an exec input takes many links.
    sound, = PIN.list_connected_pins(then(play))
    for pin in played:
        _connect(pin, sound)
    return after, play


def _author_swing(ed, strike, exec_ins):
    """Queued, on the machine with the keys: clear the queue and ask the
    server for the swing (the strike's Server event). A client of a server
    first stamps its own cooldown and plays the clip and its sound (Fx_, its
    prediction). ``exec_ins`` all run into the swing's Branch; returns the
    exits."""
    g = _G(ed)
    queued, idle = g.branch(g.get(strike.queued_var), exec_ins)
    flow = g.put(strike.queued_var, "false", [queued])
    owns, predicts = g.branch(authority(g), [flow])
    step = _stamp(ed, strike.next_var, strike.interval_s, predicts)
    swung = fx.predict(g, strike.fx, [step])
    ask = g.keep(_node(ed, strike.event))
    for e in (owns, swung):
        _connect(e, _pin(ask, "execute"))
    ed.add_comment_to_nodes(
        f"The {strike.name}'s swing is asked of the server ({strike.event}, "
        "punch.py). A client of a server stamps its own cooldown and plays the "
        f"clip and the swing's sound at once (Fx_{strike.fx}), its prediction; "
        "with authority (single player) the event is the swing.", g.made)
    return (then(ask), idle)


def author_strike_fx(ed, strike):
    """The strike's two cosmetics (fx.py): its clip with the swing's sound,
    and its blow landing, heard where it landed. Before its Server event."""
    fx.pair(ed, strike.fx, (), lambda g, e, _ev: _author_clip(ed, strike, e), fx.UNPREDICTED)
    fx.pair(ed, strike.hit_fx, SOUND_AT_PARAMS,
            lambda g, e, ev: _author_sound(ed, strike.hit_sounds_var, out(ev, LOCATION_PARAM), e),
            fx.SCREEN)


def author_strike_event(ed, strike):
    """The strike's Server event: the swing, on the machine that owns it.
    Refused unless the hand is the strike's (a Melee item, or empty), the
    owner alive and not guarding, and the cooldown over (within
    STRIKE_GRACE_S); then the cooldown, when the blow lands, the pending
    blow, and the clip. Before the Tick, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, strike.event))
    held = g.get(WV.Held)
    go, _refused = author_guard(g, strike.event, [then(event)])
    armed, bare = g.branch(valid(g, held), [go])
    hand = [bare]
    if strike.armed:
        # Behind IsValid, as every read of Held is.
        melee, _other = g.branch(g.iget(held, IV.Melee), [armed])
        hand = [melee]
    alive = _author_alive(g, hand)
    soon = op(g, FN_ADD_FF, out(g.call(FN_TIME_SECONDS)), str(STRIKE_GRACE_S))
    cooled = op(g, FN_GE_FF, soon, g.get(strike.next_var))
    free = op(g, FN_AND, cooled, not_(g, g.get(WV.Blocking)))
    swing, _refused = g.branch(free, alive)
    step = _stamp(ed, strike.next_var, strike.interval_s, swing)
    step = _stamp(ed, strike.due_var, strike.impact_s, step)
    step = _set_bool(ed, strike.pending_var, True, step)
    fx.tell(g, strike.fx, [step])
    ed.add_comment_to_nodes(
        f"{strike.event} (punch.py): the owning client's {strike.name}. Refused "
        f"unless the hand is {'a Melee item' if strike.armed else 'empty'}, the "
        "owner alive and not guarding and the cooldown over (within "
        f"{STRIKE_GRACE_S:g} s). Then the cooldown, when the blow lands "
        f"({strike.impact_s} s on), and the clip into {AIM_SLOT}, upper body "
        "only, with one of the swing's sounds, told to everyone "
        f"(Multicast_{strike.fx}). The blow is the Tick's.",
        g.made)


def _author_blow(ed, strike, exec_ins, scenery=None, damage=None):
    """Pending and due: sweep a sphere forward from the chest, and take the
    strike's damage off the first body with a health component. Pending is
    set by the strike's Server event alone, so only the machine with
    authority ever sweeps.

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

    met = (then(cast),)
    amount = strike.damage
    if damage:
        amount, met = damage(ed, _loose_pin(brk, "HitActor", is_input=False), met[0])
    # The target takes it (damage.py), stamped as a pellet's is (impact.py):
    # the health bar, the kill's credit, and which way the flinch goes. With
    # what: the item in hand, which is nothing for a fist.
    who, _who_n = owner_instigator(ed)
    with_what = ed.add_get_member_variable_node(WV.Held)
    took, take = take_hit(ed, as_health, amount,
                          _loose_pin(brk, "ImpactNormal", is_input=False),
                          who, out(with_what, WV.Held), met)
    # What it sounds like going in, from where it went in: told to every
    # machine with a screen, the striker's included (nobody predicted it).
    landed = fx.tell(_G(ed), strike.hit_fx, [took],
                     Location=_loose_pin(brk, "ImpactPoint", is_input=False))

    ed.add_comment_to_nodes(
        f"The {strike.name}'s blow, {strike.impact_s} s into the swing: a "
        f"{strike.radius_cm:.0f} cm sphere swept {strike.reach_cm:.0f} cm "
        f"forward from the chest. The first thing with a health component "
        f"loses {strike.damage:.0f} HP, stamped like a pellet hit.",
        [gate, trace, hit, cast, take])

    failed = _loose_pin(cast, "CastFailed", is_input=False)
    missed = scenery(ed, brk, failed) if scenery else (failed,)
    return (landed, else_(gate), else_(hit)) + tuple(missed)
