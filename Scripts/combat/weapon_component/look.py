"""The look: what another machine's copy of a character poses by (M13).

A player reads other players by their animation, and the pose part of the
Tick runs on every copy from the component's own state (tick.py). On the
owning machine the keys write that state. On the server's copy of a client's
character, and on every other client's, something else must:

    fact                    travels as                             the copy writes
    stance                  the movement's own flags (C++):        Stance
                            GetStance(owner), Source/CLAUDE.md
    aim pitch               the engine's Pawn.RemoteViewPitch:     the anim BP's AimPitch
                            GetBaseAimRotation(owner)              (x SightBlend, as locally)
    aim mode                LookAim (0 hip, 1 shoulder, 2 sights)  Aiming, SightAiming, and
                                                                   SightBlend eased to it
    raised to fire, or not  LookLowered                            Lowered
    the hand's pose class   LookPose: the ready pose itself, the   HandPose
                            held item's AimPose, none with empty
                            hands

The last three are this module's, and nothing else is replicated: three
variables, sent to everyone but the owner (COND_SKIP_OWNER), who has the
keys. Only the owning machine knows them yet (which item is in hand and when
a shot raised the gun are still its own: M18, M19), so it reports them,
``Server_SetLook``, reliable and only on the frame one changes
(``_author_look_report``); the server keeps what it is told and the engine
sends it on. They are cosmetic: no rule reads them, a wrong one costs a pose.
When the server owns the hand and the shot, it writes them itself and the
event goes.

The pose is the asset, not a number for it: a new item's pose then needs no
table here, and a stick held out (torch.py swaps its AimPose) is covered.

HandPose is what the equip and the keep-alive play (inventory.py,
ready_pose.py): the local copy's equip writes it off Held, a remote copy's
mirror off LookPose, asking for a re-equip when it changes. What a remote
copy shows IN the hand is still its own copy's item until M18.

Single player is the same graph: the one machine is local, so the mirror
never runs, and the Server event is a local call that writes three variables
nothing reads.
"""

import unreal

from combat.aim_pitch import AIM_PITCH_VAR
from combat import item_vars as IV
from combat.carry_tuning import LOWERED_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.skin import player_skin
from combat.tuning import COMBAT
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import (
    HIP, LOOK_PARAMS, REPLICATED, SERVER_SET_LOOK, SHOULDER, SIGHTS, HandPose, LookAim,
    LookLowered, LookPose, SentAim, SentLowered, SentPose)
from combat.weapon_component.sight_pitch import _anim_class_path
from combat.weapon_component.stance import STANCE_VAR
from net.guard import author_guard
from uebp import net
from uebp.g import _G
from uebp.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_GET_BASE_AIM_ROT
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_BOOL_TO_FLOAT, FN_BREAK_ROT, FN_CLAMP_II, FN_EQ_II, FN_GE_II, FN_INTERP_FF, FN_MUL_FF,
    FN_NE_OO, FN_NEQ_BB, FN_NEQ_II, FN_NORMALIZE_AXIS, FN_OR, FN_SELECT_II)
from uebp.nodes.move import FN_GET_STANCE
from uebp.nodes.palette import NODE_CAST_PAWN
from uebp.nodes.system import FN_IS_VALID

def replicate_look(bp):
    """After every declare, which drops the flags (uebp/CLAUDE.md)."""
    for var in REPLICATED:
        net.replicate(bp, var, unreal.LifetimeCondition.COND_SKIP_OWNER)


def author_set_look(ed):
    """The Server event: keep what the owning client reports."""
    g = _G(ed)
    event = g.keep(net.server_event(ed, SERVER_SET_LOOK, LOOK_PARAMS))
    mode = g.call(FN_CLAMP_II, Value=out(event, "Aim"), Min=HIP, Max=SIGHTS)
    go, _refused = author_guard(g, SERVER_SET_LOOK, [then(event)])
    tail = g.put(LookAim, out(mode), [go])
    tail = g.put(LookLowered, out(event, "Lowered"), [tail])
    g.put(LookPose, out(event, "Pose"), [tail])
    ed.add_comment_to_nodes(
        f"{SERVER_SET_LOOK} (look.py): the owning client says how its character "
        "is posed (the aim mode, the gun lowered or raised, the hand's ready "
        "pose), and the server keeps it in three variables replicated to "
        "everyone but that owner. Cosmetic: no rule reads them.", g.made)


def _author_hand_pose(ed, exec_in):
    """In the equip, once Held is set: where this machine's player holds the
    item, HandPose = Held.AimPose, or none with empty hands. A remote copy's
    is the mirror's. Returns the exec pins to carry on from."""
    g = _G(ed, ITEM_CLASS_PATH)
    local, remote = g.branch(g.get(WV.LocalInput), [exec_in])
    held = g.get(WV.Held)
    armed, empty = g.branch(out(g.call(FN_IS_VALID, Object=held)), [local])
    took = g.put(HandPose, g.iget(held, IV.AimPose), [armed])
    none = g.put(HandPose, None, [empty])
    ed.add_comment_to_nodes(
        "HandPose (look.py): the pose the hand's item is held in, off Held "
        "where the keys are. Read behind IsValid: empty hands have none.", g.made)
    return (took, none, remote)


def _author_look_report(ed, exec_ins):
    """On the owning machine, after the carry: report the look on the frame it
    changes. Returns the exec pins to carry on from."""
    g = _G(ed)
    # 0, 1 or 2: an aim, and one more for the sights (which are an aim too).
    shoulder = g.call(FN_SELECT_II, A=SHOULDER, B=HIP, bPickA=g.get(WV.Aiming))
    sights = g.call(FN_AND, A=g.get(WV.Aiming), B=g.get(WV.SightAiming))
    more = g.call(FN_SELECT_II, A=SIGHTS - SHOULDER, B=0, bPickA=out(sights))
    mode = g.call(FN_ADD_II, A=out(shoulder), B=out(more))
    changed = g.call(
        FN_OR,
        A=out(g.call(FN_NEQ_II, A=out(mode), B=g.get(SentAim))),
        B=out(g.call(FN_NEQ_BB, A=g.get(LOWERED_VAR), B=g.get(SentLowered))))
    changed = g.call(
        FN_OR, A=out(changed),
        B=out(g.call(FN_NE_OO, A=g.get(HandPose), B=g.get(SentPose))))
    new, same = g.branch(out(changed), exec_ins)
    # Stored first and sent from the stores: the mode is a pure chain.
    tail = g.put(SentAim, out(mode), [new])
    tail = g.put(SentLowered, g.get(LOWERED_VAR), [tail])
    tail = g.put(SentPose, g.get(HandPose), [tail])
    send = g.keep(_node(ed, SERVER_SET_LOOK))
    for name, _type in LOOK_PARAMS:
        _connect(g.get({"Aim": SentAim, "Lowered": SentLowered, "Pose": SentPose}[name]),
                 _pin(send, name))
    _connect(tail, _pin(send, "execute"))
    ed.add_comment_to_nodes(
        "The look, reported (look.py): on the frame the aim mode, Lowered or "
        f"the hand's pose changes, the owning machine tells the server "
        f"({SERVER_SET_LOOK}), which replicates it to the other players. In "
        "single player the call is local and nothing reads what it writes.", g.made)
    return (then(send), same)


def _author_look_mirror(ed, tick, owner_out, exec_in):
    """On a copy that is not the local player's (the server's of a client's
    character, another client's): write the state the pose reads from what
    was replicated. Returns the exec pins to carry on from."""
    anim_class = _anim_class_path(player_skin())
    if not unreal.load_class(None, anim_class):
        raise RuntimeError(f"{anim_class} did not load -- nothing to cast to")
    g = _G(ed)
    tail = g.put(STANCE_VAR, out(g.call(FN_GET_STANCE, Character=owner_out)), [exec_in])

    # --- the aim mode, and the body's share of the sights eased to it ---------
    mode = g.get(LookAim)
    tail = g.put(WV.Aiming, out(g.call(FN_GE_II, A=mode, B=SHOULDER)), [tail])
    tail = g.put(WV.SightAiming, out(g.call(FN_EQ_II, A=mode, B=SIGHTS)), [tail])
    step = g.call(FN_INTERP_FF, Current=g.get(WV.SightBlend),
                  Target=out(g.call(FN_BOOL_TO_FLOAT, InBool=g.get(WV.SightAiming))),
                  DeltaTime=out(tick, "DeltaSeconds"))
    _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
    tail = g.put(WV.SightBlend, out(step), [tail])
    tail = g.put(LOWERED_VAR, g.get(LookLowered), [tail])

    # --- the hand's pose: a change re-equips, which is what plays it ----------
    other = g.call(FN_NE_OO, A=g.get(HandPose), B=g.get(LookPose))
    new, same = g.branch(out(other), [tail])
    posed = g.put(HandPose, g.get(LookPose), [new])
    posed = g.put(WV.NeedsRefresh, "true", [posed])

    # --- the body pitches with the owner's view, as far as it is on the sights
    as_pawn = g.keep(_palette(ed, NODE_CAST_PAWN))
    _connect(owner_out, _pin(as_pawn, "Object"))
    for e in (posed, same):
        _connect(e, _pin(as_pawn, "execute"))
    view = g.call(FN_GET_BASE_AIM_ROT, self=_loose_pin(as_pawn, "AsPawn", is_input=False))
    parts = g.call(FN_BREAK_ROT, InRot=out(view))
    signed = g.call(FN_NORMALIZE_AXIS, Angle=out(parts, "Pitch"))
    pitch = g.call(FN_MUL_FF, A=out(signed), B=g.get(WV.SightBlend))
    anim = g.call(FN_ANIM_INSTANCE, self=g.get(WV.OwnerMesh))
    cast = g.keep(_palette(ed, "Utilities|Casting|CastTo" + anim_class.rsplit(".", 1)[1][:-2]))
    _connect(out(anim), _pin(cast, "Object"))
    _connect(then(as_pawn), _pin(cast, "execute"))
    as_anim = next(p for p in BEL.list_output_pins(cast)
                   if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p)).startswith("As"))
    put = g.iput(as_anim, AIM_PITCH_VAR, out(pitch), [then(cast)], anim_class)

    ed.add_comment_to_nodes(
        "The look, mirrored (look.py): this copy is not its player's own (the "
        "server's, or another client's), so the state the pose reads is "
        "written from what travelled: Stance off the movement component, "
        "Aiming / SightAiming / SightBlend off LookAim, Lowered off "
        "LookLowered, HandPose off LookPose (a change re-equips), and the anim "
        f"BP's {AIM_PITCH_VAR} off the pawn's replicated view pitch.", g.made)
    return (put, out(cast, "CastFailed"), _pin(as_pawn, "CastFailed", is_input=False))


def _author_local_carry(ed, exec_ins, author_carry):
    """The carry is the local machine's (it reads the keys' state and the
    shot's time); a remote copy's Lowered is the mirror's. ``author_carry``
    takes the local exec and returns the carry's exits. Returns the exits of
    both arms."""
    g = _G(ed)
    local, remote = g.branch(g.get(WV.LocalInput), exec_ins)
    reported = _author_look_report(ed, author_carry((local,)))
    ed.add_comment_to_nodes(
        "Whose Lowered: the carry decides it where the keys are; elsewhere the "
        "mirror already wrote it (look.py).", g.made)
    return tuple(reported) + (remote,)
