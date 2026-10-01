"""Down the sights, the body pitches with the view: writes the player's anim BP
AimPitch every frame, which tips the upper body and so the gun (aim_pitch.py
owns the bones and the axis).

    AimPitch = NormalizeAxis(ControlRotation.Pitch) * SightBlend

SightBlend, not SightAiming: the pitch eases in on the sights key and out once
the camera has left the gun (sights.py holds the blend up until then), so the
gun never snaps and the view never follows the body levelling. At SightBlend 0 --
the hip and the shoulder aim -- it writes 0 and the body stands as it did.
NormalizeAxis because the control rotation stores looking down as 270..360.

The anim instance is cast to the player's own anim BP class, so a wearer with
another anim BP simply fails the cast and keeps the level pose.
"""

import unreal

from combat.aim_pitch import AIM_PITCH_VAR
from combat.graph import BEL, _at, _connect, _node, _palette, _pin
from combat.nodes import (
    FN_ANIM_INSTANCE, FN_BREAK_ROT, FN_GET_CONTROL_ROT, FN_MUL_FF,
    FN_NORMALIZE_AXIS,
)
from combat.skin import player_skin


def _anim_class_path(skin):
    name = skin.anim_bp.rsplit("/", 1)[1]
    return f"{skin.anim_bp}.{name}_C"


def _author_sight_pitch(ed, pc_out, exec_ins, x0, y0):
    """Set the anim instance's AimPitch. Returns the exec pins to carry on from."""
    skin = player_skin()
    anim_class = _anim_class_path(skin)
    # A cast node exists in the palette only for a class that is loaded.
    if not unreal.load_class(None, anim_class):
        raise RuntimeError(f"{anim_class} did not load -- nothing to cast to")
    made = []

    def keep(n):
        made.append(n)
        return n

    view = keep(_at(_node(ed, FN_GET_CONTROL_ROT), x0, y0 + 300))
    _connect(pc_out, _pin(view, "self"))
    parts = keep(_at(_node(ed, FN_BREAK_ROT), x0 + 260, y0 + 300))
    _connect(_pin(view, "ReturnValue", is_input=False), _pin(parts, "InRot"))
    signed = keep(_at(_node(ed, FN_NORMALIZE_AXIS), x0 + 520, y0 + 300))
    _connect(_pin(parts, "Pitch", is_input=False), _pin(signed, "Angle"))
    blend = keep(_at(ed.add_get_member_variable_node("SightBlend"), x0 + 520, y0 + 440))
    scaled = keep(_at(_node(ed, FN_MUL_FF), x0 + 780, y0 + 300))
    _connect(_pin(signed, "ReturnValue", is_input=False), _pin(scaled, "A"))
    _connect(_pin(blend, "SightBlend", is_input=False), _pin(scaled, "B"))

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

    put = keep(_at(ed.add_set_member_variable_node(AIM_PITCH_VAR, anim_class),
                   x0 + 1040, y0))
    _connect(as_anim, _pin(put, "self"))
    _connect(_pin(scaled, "ReturnValue", is_input=False), _pin(put, AIM_PITCH_VAR))
    _connect(BEL.find_then_pin(cast), _pin(put, "execute"))

    ed.add_comment_to_nodes(
        f"Down the sights the body pitches with the view: {AIM_PITCH_VAR} = "
        "the control pitch (signed) x SightBlend, onto the player's anim BP, "
        "which tips the upper body and the gun by it (Scripts/combat/"
        "aim_pitch.py). 0 at the hip and on the shoulder.", made)
    return (BEL.find_then_pin(put), _pin(cast, "CastFailed", is_input=False))
