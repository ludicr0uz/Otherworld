"""Down the sights the left hand holds the gun: writes the player's anim BP
SupportHand and SupportPoint every frame (support_hand.py owns the IK they
drive, and says why the hand needs holding).

    SupportHand  = SightBlend          the IK's weight
    SupportPoint = HeldSupportPoint    where the held gun's ready pose has the
                                       left hand, in the right hand's space

SightBlend, as the body's pitch is (sight_pitch.py): the hold eases in on the
sights key and out once the camera has left the gun, so the hand never snaps,
and at the hip, on the shoulder or with no gun in hand it writes 0 and the
pose is left alone. HeldSupportPoint is the component's own copy of
Held.SupportPoint (pose_weights.py writes it behind an IsValid Branch, beside
HeldTwoHanded), so nothing here reads off Held.

The anim instance is cast to the player's anim BP class, so a wearer with
another anim BP simply fails the cast.

A dedicated server writes neither (task A4): the hold is for the eye alone
(no shooter aims at a left hand by where it rests on a gun), the IK it
drives sits in the anim graph's shared tail, and left at its default 0 it is
skipped there (server_anim.py; verify/server_anim.py checks this gate).
"""

import unreal

from uebp.graph import BEL, _connect, _node, _palette, _pin, else_, out, then
from combat.skin import player_skin
from combat.support_hand import SUPPORT_HAND_VAR, SUPPORT_POINT_VAR
from combat.weapon_component.pose_weights import HELD_SUPPORT_POINT
from combat.weapon_component.sight_pitch import _anim_class_path, _anim_instance
from uebp.nodes.system import FN_IS_DEDICATED_SERVER
from combat.weapon_component import vars as WV


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

    tail = then(cast)
    for var, source in ((SUPPORT_HAND_VAR, "SightBlend"), (SUPPORT_POINT_VAR, HELD_SUPPORT_POINT)):
        value = keep(ed.add_get_member_variable_node(source))
        put = keep(ed.add_set_member_variable_node(var, anim_class))
        _connect(as_anim, _pin(put, "self"))
        _connect(out(value, source), _pin(put, var))
        _connect(tail, _pin(put, "execute"))
        tail = then(put)

    ed.add_comment_to_nodes(
        f"Down the sights the left hand holds the gun: {SUPPORT_HAND_VAR} = "
        f"SightBlend and {SUPPORT_POINT_VAR} = {HELD_SUPPORT_POINT}, onto the "
        "player's anim BP, whose Two Bone IK they drive (Scripts/combat/"
        "support_hand.py). 0 at the hip and on the shoulder, and never written "
        "on a dedicated server, which draws no hand.", made)
    return (tail, out(cast, "CastFailed"), then(server))
