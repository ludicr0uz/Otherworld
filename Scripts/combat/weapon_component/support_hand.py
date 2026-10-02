"""Down the sights the left hand holds the gun: writes the player's anim BP
SupportHand and SupportRifle every frame (support_hand.py owns the IK they
drive, and says why the hand needs holding).

    SupportHand  = SightBlend       the IK's weight
    SupportRifle = HeldTwoHanded    which ready pose's hold: the rifle's or
                                    the pistol's

SightBlend, as the body's pitch is (sight_pitch.py): the hold eases in on the
sights key and out once the camera has left the gun, so the hand never snaps,
and at the hip, on the shoulder or with no gun in hand it writes 0 and the
pose is left alone. HeldTwoHanded is the component's own copy of
Held.TwoHanded (pose_weights.py writes it behind an IsValid Branch), so
nothing here reads off Held; every gun whose ready pose is the rifle's is
two-handed (weapon_specs.py).

The anim instance is cast to the player's own anim BP class, so a wearer with
another anim BP simply fails the cast.
"""

import unreal

from combat.graph import BEL, _at, _connect, _node, _palette, _pin
from combat.nodes import FN_ANIM_INSTANCE
from combat.skin import player_skin
from combat.support_hand import SUPPORT_HAND_VAR, SUPPORT_RIFLE_VAR
from combat.weapon_component.pose_weights import HELD_TWO_HANDED
from combat.weapon_component.sight_pitch import _anim_class_path


def _author_support_hand(ed, exec_ins, x0, y0):
    """Set the anim instance's SupportHand and SupportRifle. Returns the exec
    pins to carry on from. After SightBlend and HeldTwoHanded are written."""
    anim_class = _anim_class_path(player_skin())
    # A cast node exists in the palette only for a class that is loaded.
    if not unreal.load_class(None, anim_class):
        raise RuntimeError(f"{anim_class} did not load -- nothing to cast to")
    made = []

    def keep(n):
        made.append(n)
        return n

    mesh = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0, y0 + 160))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 260, y0 + 160))
    _connect(_pin(mesh, "OwnerMesh", is_input=False), _pin(anim, "self"))
    cast = keep(_at(_palette(ed, "Utilities|Casting|CastTo"
                                 + anim_class.rsplit(".", 1)[1][:-2]), x0 + 520, y0))
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in exec_ins:
        _connect(e, _pin(cast, "execute"))
    as_anim = next(p for p in BEL.list_output_pins(cast)
                   if str(unreal.BlueprintGraphPinLibrary.get_pin_name(p))
                   .startswith("As"))

    tail = BEL.find_then_pin(cast)
    for i, (var, source) in enumerate(((SUPPORT_HAND_VAR, "SightBlend"),
                                       (SUPPORT_RIFLE_VAR, HELD_TWO_HANDED))):
        value = keep(_at(ed.add_get_member_variable_node(source),
                         x0 + 780 + i * 300, y0 + 300))
        put = keep(_at(ed.add_set_member_variable_node(var, anim_class),
                       x0 + 1040 + i * 300, y0))
        _connect(as_anim, _pin(put, "self"))
        _connect(_pin(value, source, is_input=False), _pin(put, var))
        _connect(tail, _pin(put, "execute"))
        tail = BEL.find_then_pin(put)

    ed.add_comment_to_nodes(
        f"Down the sights the left hand holds the gun: {SUPPORT_HAND_VAR} = "
        f"SightBlend and {SUPPORT_RIFLE_VAR} = {HELD_TWO_HANDED}, onto the "
        "player's anim BP, whose Two Bone IK they drive (Scripts/combat/"
        "support_hand.py). 0 at the hip and on the shoulder.", made)
    return (tail, _pin(cast, "CastFailed", is_input=False))
