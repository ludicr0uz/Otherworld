"""Down the sights the left hand holds the gun: writes the player's anim BP
SupportHand and SupportPoint every frame (support_hand.py owns the IK they
drive, and says why the hand needs holding).

    SupportHand  = max(SightBlend, Seated) x (1 - ReloadHand)    the IK's weight
    Seated       = the anim BP's CarryPose, on a gun whose HandPose is in
                   CarrySeated (0 on any other)
    SupportPoint = HeldSupportPoint    where the held gun's ready pose has the
                                       left hand, in the right hand's space

SightBlend, as the body's pitch is (sight_pitch.py): the hold eases in on the
sights key and out once the camera has left the gun, so the hand never snaps,
and at the hip, on the shoulder or with no gun in hand it writes 0 and the
pose is left alone. Seated holds the hand there in a long gun's carry too, on
a gun of carry_pose_consts.CARRY_SEATED_GUNS (the shotgun: the carry's clips
lay its left palm on the top of its receiver, its fingers on the outside of
the gun), eased in and out with the carry itself. HeldSupportPoint is the component's own copy of
Held.SupportPoint (pose_weights.py writes it behind an IsValid Branch, beside
HeldTwoHanded), so nothing here reads off Held. ReloadHand rises while a
reload's clip is in the slot (reload_clip.py): the hand leaves the gun for
the magazine, and takes hold again after.

The anim instance is cast to the player's anim BP class, so a wearer with
another anim BP simply fails the cast.

A dedicated server writes neither (task A4): the hold is for the eye alone
(no shooter aims at a left hand by where it rests on a gun), the IK it
drives sits in the anim graph's shared tail, and left at its default 0 it is
skipped there (server_anim.py; verify/server_anim.py checks this gate).
"""

import unreal

from uebp.graph import BEL, _connect, _node, _palette, _pin, else_, out, then
from combat.carry_pose_consts import CARRY_POSE
from combat.skin import player_skin
from combat.support_hand import SUPPORT_HAND_VAR, SUPPORT_POINT_VAR
from combat.weapon_component.pose_weights import HELD_SUPPORT_POINT
from combat.weapon_component.reload_clip import author_hand_weight
from combat.weapon_component.look_vars import HandPose
from combat.weapon_component.sight_pitch import _anim_class_path, _anim_instance
from combat.weapon_component.slot_nodes import op
from uebp.g import _G
from uebp.nodes.array import FN_ARR_CONTAINS
from uebp.nodes.math import FN_BOOL_TO_FLOAT, FN_MAX_FF, FN_MUL_FF
from uebp.nodes.system import FN_IS_DEDICATED_SERVER
from combat.weapon_component import vars as WV


def _seated(ed, as_anim, anim_class, sight_blend, keep):
    """max(SightBlend, CarryPose x (HandPose in CarrySeated)): the weight
    before a reload's clip takes the hand. The anim BP's CarryPose is the
    carry's own eased weight (pose_weights.py), read off the cast instance."""
    g = _G(ed)
    carry = keep(ed.add_get_member_variable_node(CARRY_POSE, anim_class))
    _connect(as_anim, _pin(carry, "self"))
    seated = g.call(FN_ARR_CONTAINS, TargetArray=g.get(WV.CarrySeated),
                    ItemToFind=g.get(HandPose))
    on = out(g.call(FN_BOOL_TO_FLOAT, InBool=out(seated)))
    weight = op(g, FN_MAX_FF, sight_blend, op(g, FN_MUL_FF, out(carry, CARRY_POSE), on))
    for n in g.made:
        keep(n)
    return weight


def _author_support_hand(ed, exec_ins):
    """Set the anim instance's SupportHand and SupportPoint. Returns the exec
    pins to carry on from. After SightBlend and HeldSupportPoint are written."""
    anim_class = _anim_class_path(player_skin())
    # A cast node exists in the palette only for a class that is loaded.
    if not unreal.load_class(None, anim_class):
        raise RuntimeError(f"{anim_class} did not load -- nothing to cast to")
    made = []

    def keep(n):
        made.append(n)
        return n

    mesh = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    anim = keep(_anim_instance(ed, player_skin()))
    _connect(out(mesh, WV.OwnerMesh), _pin(anim, "self"))
    cast = keep(_palette(ed, "Utilities|Casting|CastTo" + anim_class.rsplit(".", 1)[1][:-2]))
    _connect(out(anim), _pin(cast, "Object"))
    no_screen = keep(_node(ed, FN_IS_DEDICATED_SERVER))
    server = keep(ed.add_branch_node())
    _connect(out(no_screen), _pin(server, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(server, "execute"))
    _connect(else_(server), _pin(cast, "execute"))
    as_anim = next(p for p in BEL.list_output_pins(cast)
                   if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p))
                   .startswith("As"))

    # The hold lets go for a reload's clip (reload_clip.py): the left hand
    # goes to the magazine.
    blend = keep(ed.add_get_member_variable_node("SightBlend"))
    held = out(blend, "SightBlend")
    # A skin without the carry's clips has no CarryPose to read.
    if player_skin().carry_idle:
        held = _seated(ed, as_anim, anim_class, held, keep)
    tail, weight = author_hand_weight(ed, held, then(cast), keep)
    point = keep(ed.add_get_member_variable_node(HELD_SUPPORT_POINT))
    for var, value in ((SUPPORT_HAND_VAR, weight),
                       (SUPPORT_POINT_VAR, out(point, HELD_SUPPORT_POINT))):
        put = keep(ed.add_set_member_variable_node(var, anim_class))
        _connect(as_anim, _pin(put, "self"))
        _connect(value, _pin(put, var))
        _connect(tail, _pin(put, "execute"))
        tail = then(put)

    ed.add_comment_to_nodes(
        f"Down the sights the left hand holds the gun: {SUPPORT_HAND_VAR} = "
        f"SightBlend, or the carry's weight on a gun of {WV.CarrySeated} (the shotgun), "
        f"less while a reload's clip plays, and {SUPPORT_POINT_VAR} = {HELD_SUPPORT_POINT}, onto the "
        "player's anim BP, whose Two Bone IK they drive (Scripts/combat/"
        "support_hand.py). 0 at the hip and on the shoulder, and never written "
        "on a dedicated server, which draws no hand.", made)
    return (tail, out(cast, "CastFailed"), then(server))
