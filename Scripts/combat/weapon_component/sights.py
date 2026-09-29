"""Aiming down the sights: the camera leaves the shoulder boom for the held
weapon's eye point (SightOffset), so the player looks along the gun in first
person. ads.py decides *whether* the player is down the sights (SightAiming)
and how far to zoom; this module owns only where the camera is.

Why the camera is moved rather than a second camera switched to: the camera is
what everything else already reads -- the FOV zoom, the aim trace (off the
camera manager) and the HUD -- so one camera that travels keeps all three
right, and SightBlend makes the travel an ease rather than a cut.

Why it is written every frame rather than attached to the weapon: the camera's
rotation has to stay the control rotation (the boom's). Placing it by
location only keeps the view where the mouse points. The weapon pitches with the
view (sight_pitch.py tips the upper body), so the eye point rides the gun and
stays on the sight line at any pitch.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    CAMERA_CLASS_PATH, FN_ADD_TICK_PREREQ, FN_AND, FN_BOOL_TO_FLOAT,
    FN_COMP_SET_WORLD_LOC, FN_GET_COMP, FN_GET_TRANSFORM, FN_GREATER_FF,
    FN_INTERP_FF, FN_SET_HIDDEN, FN_SOCKET_LOC, FN_TRANSFORM_LOC, FN_VLERP,
    SPRING_ARM_CLASS_PATH, SPRING_ARM_SOCKET,
)
from combat.tuning import COMBAT
from combat.weapon_component.common import _prop

# A scoped weapon is hidden once the camera is this far to its eye point. The
# eye is behind the scope's eyepiece, on its axis, so the scope's own solid
# tube fills the middle of the view -- exactly the hole the HUD's glass leaves
# clear. Real scopes are hollow; this one is a cylinder. Hidden late in the
# travel so the swap happens under a mostly opaque surround, not in the open.
SCOPE_HIDE_BLEND = 0.9


def _boom(ed, owner_out, x, y):
    """The owner's SpringArmComponent, as a pure node."""
    arm = _at(_node(ed, FN_GET_COMP), x, y)
    _connect(owner_out, _pin(arm, "self"))
    _pin(arm, "ComponentClass").set_pin_value(SPRING_ARM_CLASS_PATH)
    return arm


def _author_camera_after_boom(ed, owner_out, exec_in, x0, y0):
    """BeginPlay: tick this component after the camera boom.

    Both tick in TG_PostPhysics, in no promised order. The boom moves its end
    to follow the character and the control rotation when it ticks, and the
    camera rides along at whatever offset it had. Placed before the boom has
    moved, the camera would sit one frame's walk off the sight -- a few
    centimetres of shimmer while strafing with the sights up.
    """
    arm = _boom(ed, owner_out, x0, y0 + 160)
    after = _at(_node(ed, FN_ADD_TICK_PREREQ), x0 + 260, y0)
    _connect(_pin(arm, "ReturnValue", is_input=False),
             _pin(after, "PrerequisiteComponent"))
    _connect(exec_in, _pin(after, "execute"))
    ed.add_comment_to_nodes(
        "Tick after the camera boom, so the sight camera is placed against "
        "where the boom is this frame rather than where it was last frame.",
        [arm, after])
    return BEL.find_then_pin(after)


def _author_sight_camera(ed, tick, owner_out, held, armed_out, exec_ins,
                         x0, y0):
    """Ease the camera between the boom's end and the weapon's eye point.

        SightBlend = FInterpTo(SightBlend, SightAiming ? 1 : 0, dt, ads_interp_speed)
        shoulder   = CameraBoom.GetSocketLocation(SpringEndpoint)
        if IsValid(Held):
            eye = TransformLocation(Held.GetTransform(), Held.SightOffset)
            Camera.SetWorldLocation(VLerp(shoulder, eye, SightBlend))
        else:
            Camera.SetWorldLocation(shoulder)

    The same interpolation speed as the zoom, so the camera arrives at the
    sight as the FOV arrives at the weapon's zoom, and the sniper's glass
    (which fades on the zoom) closes around the view as it gets there.

    Written every frame, both ways. At SightBlend 0 the write puts the camera
    exactly where the boom already holds it (the template's camera has no
    offset of its own, which camera.aim_camera asserts), so there is no
    "restore" path to forget; and with empty hands -- a weapon dropped while
    down the sights -- it snaps home rather than reading SightOffset off a
    null Held.

    Only the location is written. The rotation stays the boom's, which is the
    control rotation, so the view goes where the mouse points. sight_pitch.py
    turns the upper body by the same pitch, and the eye point turns with the
    gun, so the eye stays on the sight line looking up or down.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    wanted = keep(_at(ed.add_get_member_variable_node("SightAiming"), x0, y0 + 300))
    as_float = keep(_at(_node(ed, FN_BOOL_TO_FLOAT), x0 + 240, y0 + 300))
    _connect(_pin(wanted, "SightAiming", is_input=False), _pin(as_float, "InBool"))
    have = keep(_at(ed.add_get_member_variable_node("SightBlend"), x0, y0 + 420))
    step = keep(_at(_node(ed, FN_INTERP_FF), x0 + 480, y0 + 300))
    _connect(_pin(have, "SightBlend", is_input=False), _pin(step, "Current"))
    _connect(_pin(as_float, "ReturnValue", is_input=False), _pin(step, "Target"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "DeltaTime"))
    _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
    blend = keep(_at(ed.add_set_member_variable_node("SightBlend"), x0 + 740, y0))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(blend, "SightBlend"))
    for e in exec_ins:
        _connect(e, _pin(blend, "execute"))

    arm = keep(_boom(ed, owner_out, x0 + 740, y0 + 420))
    shoulder = keep(_at(_node(ed, FN_SOCKET_LOC), x0 + 1000, y0 + 420))
    _connect(_pin(arm, "ReturnValue", is_input=False), _pin(shoulder, "self"))
    _set(shoulder, "InSocketName", SPRING_ARM_SOCKET)
    shoulder_out = _pin(shoulder, "ReturnValue", is_input=False)

    cam = keep(_at(_node(ed, FN_GET_COMP), x0 + 1000, y0 + 560))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    cam_out = _pin(cam, "ReturnValue", is_input=False)

    armed = keep(_at(ed.add_branch_node(), x0 + 1000, y0))
    _connect(armed_out, _pin(armed, "Condition"))
    _connect(BEL.find_then_pin(blend), _pin(armed, "execute"))

    # True arm: Held is valid, so its transform and SightOffset can be read.
    xform = keep(_at(_node(ed, FN_GET_TRANSFORM), x0 + 1260, y0 + 700))
    _connect(held, _pin(xform, "self"))
    off_pin, off_n = _prop(ed, "SightOffset", held, x0 + 1260, y0 + 840)
    keep(off_n)
    eye = keep(_at(_node(ed, FN_TRANSFORM_LOC), x0 + 1520, y0 + 700))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(eye, "T"))
    _connect(off_pin, _pin(eye, "Location"))
    mix = keep(_at(_node(ed, FN_VLERP), x0 + 1780, y0 + 420))
    _connect(shoulder_out, _pin(mix, "A"))
    _connect(_pin(eye, "ReturnValue", is_input=False), _pin(mix, "B"))
    _connect(_loose_pin(blend, "Output_Get", is_input=False), _pin(mix, "Alpha"))
    to_sight = keep(_at(_node(ed, FN_COMP_SET_WORLD_LOC), x0 + 2040, y0))
    _connect(cam_out, _pin(to_sight, "self"))
    _connect(_pin(mix, "ReturnValue", is_input=False), _pin(to_sight, "NewLocation"))
    _connect(BEL.find_then_pin(armed), _pin(to_sight, "execute"))

    # ...and a scoped weapon gets out of its own scope's way. Written every
    # frame on Held, which is the one weapon the equip sequence shows, so the
    # frame the sights come down (or Held changes) it is visible again.
    scoped, scoped_n = _prop(ed, "Scoped", held, x0 + 2040, y0 + 700)
    keep(scoped_n)
    far_in = keep(_at(_node(ed, FN_GREATER_FF), x0 + 2040, y0 + 840))
    _connect(_loose_pin(blend, "Output_Get", is_input=False), _pin(far_in, "A"))
    _set(far_in, "B", SCOPE_HIDE_BLEND)
    behind_glass = keep(_at(_node(ed, FN_AND), x0 + 2300, y0 + 760))
    _connect(scoped, _pin(behind_glass, "A"))
    _connect(_pin(far_in, "ReturnValue", is_input=False), _pin(behind_glass, "B"))
    tuck = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 2560, y0))
    _connect(held, _pin(tuck, "self"))
    _connect(_pin(behind_glass, "ReturnValue", is_input=False),
             _pin(tuck, "bNewHidden"))
    _connect(BEL.find_then_pin(to_sight), _pin(tuck, "execute"))

    # False arm: nothing to look down, so the camera goes home.
    home = keep(_at(_node(ed, FN_COMP_SET_WORLD_LOC), x0 + 2040, y0 + 240))
    _connect(cam_out, _pin(home, "self"))
    _connect(shoulder_out, _pin(home, "NewLocation"))
    _connect(BEL.find_else_pin(armed), _pin(home, "execute"))

    ed.add_comment_to_nodes(
        "Down the sights: the camera eases (SightBlend, at the zoom's own "
        f"{COMBAT.ads_interp_speed:g}) from the boom's end to the held "
        "weapon's SightOffset, by location only -- the rotation stays the "
        "boom's, i.e. the mouse's. Written every frame both ways, so at "
        "SightBlend 0 it is exactly where the boom holds it and there is no "
        "restore path; with empty hands it goes straight home. A scoped "
        f"weapon hides past SightBlend {SCOPE_HIDE_BLEND:g}, out of its own "
        "scope's way.",
        made)
    return (BEL.find_then_pin(tuck), BEL.find_then_pin(home))
