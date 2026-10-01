"""Aiming down the sights: the camera leaves the shoulder boom for the held
weapon's eye point (SightOffset) and turns onto its sight line (towards
SightAim, the front sight's tip), so the player looks through the gun's own
sights in first person. ads.py decides *whether* the player is down the
sights (SightAiming) and how far to zoom; this module owns only where the
camera is and which way it looks; seat.py decides *when* it may go (SightSeat:
only once the gun is up, so the view stays on the target while the gun rises
to it).

Why the camera is moved rather than a second camera switched to: the camera is
what everything else already reads -- the FOV zoom, the aim trace (off the
camera manager) and the HUD -- so one camera that travels keeps all three
right, and SightSeat makes the travel an ease rather than a cut.

Why the camera takes the gun's sight line and not the control rotation: the
eye and the front sight's tip are two points of the gun, so a view from one
through the other has the tip in the middle of the screen whatever the arms
are doing -- the idle's breathing, a walk, a stance. The shot goes to the
middle of the screen (aim.py traces from the camera), so the sights are on the
point of impact by construction. With the control rotation instead, the gun
sat up to 2 degrees off the view in the pistol's pose and the sights pointed
beside the shot.

The mouse still aims: it turns the control rotation, the body follows its yaw
(camera.face_the_camera) and its pitch (sight_pitch.py tips the upper body),
the gun rides the body and the camera rides the gun.

An item with no sight line (the knife: both points at its origin) keeps the
boom's rotation; the look is weighted by whether the line has any length.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    CAMERA_CLASS_PATH, FN_ADD_TICK_PREREQ, FN_AND, FN_BOOL_TO_FLOAT,
    FN_COMP_SET_WORLD_LOC, FN_GET_COMP, FN_GET_TRANSFORM, FN_GREATER_FF,
    FN_COMP_SET_WORLD_ROT, FN_INTERP_FF, FN_MUL_FF, FN_OR, FN_RLERP, FN_ROT_FROM_X,
    FN_SET_HIDDEN, FN_SET_OWNER_NO_SEE, FN_SOCKET_LOC, FN_SOCKET_ROT,
    FN_SUB_VV, FN_TRANSFORM_LOC, FN_VLERP, FN_VSIZE,
    SPRING_ARM_CLASS_PATH, SPRING_ARM_SOCKET,
)
from combat.seat_tuning import SEAT_HOLD, SEAT_VAR, SIGHT_SEAT_DEG
from combat.tuning import COMBAT
from combat.weapon_component.common import _prop
from combat.weapon_component.seat import _author_sight_seat, _author_unseat

# A scoped weapon is hidden once the camera is this far to its eye point
# (SightSeat). The
# eye is behind the scope's eyepiece, on its axis, so the scope's own solid
# tube fills the middle of the view -- exactly the hole the HUD's glass leaves
# clear. Real scopes are hollow; this one is a cylinder. Hidden late in the
# travel so the swap happens under a mostly opaque surround, not in the open.
# The player's own body goes with it (OwnerNoSee on OwnerMesh): the eye point
# sits among the arms and head that hold the gun, and their hold and recoil
# animation swung through the glass. OwnerNoSee rather than hidden, so the
# body is still drawn for its shadow and for any other view.
SCOPE_HIDE_BLEND = 0.9

# A sight line shorter than this (cm) is no sight line: the item's SightOffset
# and SightAim were never set (the knife, food), and the view stays the boom's.
SIGHT_LINE_MIN_CM = 1.0


def _author_sight_line(ed, keep, held, xform, eye_out, x, y):
    """The held weapon's sight line in the world, as a pure chain:

        line = TransformLocation(Held, Held.SightAim) - eye

    Returns (the line, whether it is one: longer than SIGHT_LINE_MIN_CM).
    """
    aim_pin, aim_n = _prop(ed, "SightAim", held, x, y + 140)
    keep(aim_n)
    front = keep(_at(_node(ed, FN_TRANSFORM_LOC), x + 260, y))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(front, "T"))
    _connect(aim_pin, _pin(front, "Location"))
    line = keep(_at(_node(ed, FN_SUB_VV), x + 520, y))
    _connect(_pin(front, "ReturnValue", is_input=False), _pin(line, "A"))
    _connect(eye_out, _pin(line, "B"))
    length = keep(_at(_node(ed, FN_VSIZE), x + 780, y + 140))
    _connect(_pin(line, "ReturnValue", is_input=False), _pin(length, "A"))
    has_line = keep(_at(_node(ed, FN_GREATER_FF), x + 1040, y + 140))
    _connect(_pin(length, "ReturnValue", is_input=False), _pin(has_line, "A"))
    _set(has_line, "B", SIGHT_LINE_MIN_CM)
    return (_pin(line, "ReturnValue", is_input=False),
            _pin(has_line, "ReturnValue", is_input=False))


def _author_sight_look(ed, keep, line_out, has_line_out, boom_rot, seat_out,
                       x, y):
    """The camera's rotation down the sights, as a pure chain:

        RLerp(boom's, MakeRotFromX(line), SightSeat x (|line| > 1 cm), shortest)

    MakeRotFromX has no roll, so a canted gun does not tip the horizon.
    """
    look = keep(_at(_node(ed, FN_ROT_FROM_X), x + 780, y))
    _connect(line_out, _pin(look, "X"))
    weight = keep(_at(_node(ed, FN_BOOL_TO_FLOAT), x + 1300, y + 140))
    _connect(has_line_out, _pin(weight, "InBool"))
    alpha = keep(_at(_node(ed, FN_MUL_FF), x + 1560, y + 140))
    _connect(seat_out, _pin(alpha, "A"))
    _connect(_pin(weight, "ReturnValue", is_input=False), _pin(alpha, "B"))
    turn = keep(_at(_node(ed, FN_RLERP), x + 1820, y))
    _connect(boom_rot, _pin(turn, "A"))
    _connect(_pin(look, "ReturnValue", is_input=False), _pin(turn, "B"))
    _connect(_pin(alpha, "ReturnValue", is_input=False), _pin(turn, "Alpha"))
    _set(turn, "bShortestPath", "true")
    return _pin(turn, "ReturnValue", is_input=False)


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

        SightBlend = FInterpTo(SightBlend,
                               SightAiming OR SightSeat > SEAT_HOLD ? 1 : 0,
                               dt, ads_interp_speed)
        shoulder   = CameraBoom.GetSocketLocation(SpringEndpoint)
        if IsValid(Held):
            eye = TransformLocation(Held.GetTransform(), Held.SightOffset)
            SightSeated, SightSeat = ...                  (seat.py)
            Camera.SetWorldLocation(VLerp(shoulder, eye, SightSeat))
            Camera.SetWorldRotation(RLerp(boom's, look down the sight line,
                                          SightSeat))     (_author_sight_look)
        else:
            SightSeated, SightSeat = false, 0
            Camera.SetWorldLocation(shoulder)
            Camera.SetWorldRotation(boom's)

    SightBlend is the body's share of the sights (the pitch, the sway, the
    steady hand): it starts on the key and lasts until the camera has left
    the gun. SightSeat is the camera's, and starts only when the gun is up: the view stays where the player is looking, on
    the boom, while the gun rises, and then travels onto the sights. Both
    ease at the zoom's speed, and ads.py holds the zoom at the shoulder's
    until the camera is seated, so the sniper's glass (which fades on the
    zoom) closes around the view as it gets there.

    Written every frame, both ways. At SightSeat 0 the write puts the camera
    exactly where and as the boom already holds it (the template's camera has
    no offset or turn of its own, which camera.aim_camera asserts), so there
    is no "restore" path to forget; and with empty hands -- a weapon dropped
    while down the sights -- it snaps home rather than reading SightOffset off
    a null Held.

    The boom's rotation is its SpringEndpoint socket's, which is the control
    rotation. Down the sights the camera leaves it for the gun's sight line
    (the module docstring says why); sight_pitch.py turns the upper body by
    the view's pitch, so the gun, and the view with it, go where the mouse
    points.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # The body holds the aim until the camera has left the gun (last frame's
    # SightSeat): letting go, a view still easing home would otherwise follow
    # the gun as the upper body's pitch came off it.
    wanted = keep(_at(ed.add_get_member_variable_node("SightAiming"), x0, y0 + 300))
    seat_was = keep(_at(ed.add_get_member_variable_node(SEAT_VAR), x0 - 260, y0 + 420))
    on_gun = keep(_at(_node(ed, FN_GREATER_FF), x0, y0 + 540))
    _connect(_pin(seat_was, SEAT_VAR, is_input=False), _pin(on_gun, "A"))
    _set(on_gun, "B", SEAT_HOLD)
    either = keep(_at(_node(ed, FN_OR), x0 + 120, y0 + 420))
    _connect(_pin(wanted, "SightAiming", is_input=False), _pin(either, "A"))
    _connect(_pin(on_gun, "ReturnValue", is_input=False), _pin(either, "B"))
    as_float = keep(_at(_node(ed, FN_BOOL_TO_FLOAT), x0 + 240, y0 + 300))
    _connect(_pin(either, "ReturnValue", is_input=False), _pin(as_float, "InBool"))
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
    boom_rot = keep(_at(_node(ed, FN_SOCKET_ROT), x0 + 1000, y0 + 1000))
    _connect(_pin(arm, "ReturnValue", is_input=False), _pin(boom_rot, "self"))
    _set(boom_rot, "InSocketName", SPRING_ARM_SOCKET)
    boom_rot_out = _pin(boom_rot, "ReturnValue", is_input=False)

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
    line_out, has_line_out = _author_sight_line(
        ed, keep, held, xform, _pin(eye, "ReturnValue", is_input=False),
        x0 + 1260, y0 + 1000)
    seated, seat_out = _author_sight_seat(
        ed, tick, keep, line_out, has_line_out, boom_rot_out,
        BEL.find_then_pin(armed), x0 + 1260, y0 - 900)
    mix = keep(_at(_node(ed, FN_VLERP), x0 + 1780, y0 + 420))
    _connect(shoulder_out, _pin(mix, "A"))
    _connect(_pin(eye, "ReturnValue", is_input=False), _pin(mix, "B"))
    _connect(seat_out, _pin(mix, "Alpha"))
    to_sight = keep(_at(_node(ed, FN_COMP_SET_WORLD_LOC), x0 + 2040, y0))
    _connect(cam_out, _pin(to_sight, "self"))
    _connect(_pin(mix, "ReturnValue", is_input=False), _pin(to_sight, "NewLocation"))
    _connect(seated, _pin(to_sight, "execute"))
    look = _author_sight_look(ed, keep, line_out, has_line_out, boom_rot_out,
                              seat_out, x0 + 1260, y0 + 1000)
    to_line = keep(_at(_node(ed, FN_COMP_SET_WORLD_ROT), x0 + 2300, y0))
    _connect(cam_out, _pin(to_line, "self"))
    _connect(look, _pin(to_line, "NewRotation"))
    _connect(BEL.find_then_pin(to_sight), _pin(to_line, "execute"))

    # ...and a scoped weapon gets out of its own scope's way. Written every
    # frame on Held, which is the one weapon the equip sequence shows, so the
    # frame the sights come down (or Held changes) it is visible again.
    scoped, scoped_n = _prop(ed, "Scoped", held, x0 + 2040, y0 + 700)
    keep(scoped_n)
    far_in = keep(_at(_node(ed, FN_GREATER_FF), x0 + 2040, y0 + 840))
    _connect(seat_out, _pin(far_in, "A"))
    _set(far_in, "B", SCOPE_HIDE_BLEND)
    behind_glass = keep(_at(_node(ed, FN_AND), x0 + 2300, y0 + 760))
    _connect(scoped, _pin(behind_glass, "A"))
    _connect(_pin(far_in, "ReturnValue", is_input=False), _pin(behind_glass, "B"))
    tuck = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 2560, y0))
    _connect(held, _pin(tuck, "self"))
    _connect(_pin(behind_glass, "ReturnValue", is_input=False),
             _pin(tuck, "bNewHidden"))
    _connect(BEL.find_then_pin(to_line), _pin(tuck, "execute"))
    body = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 2560, y0 + 700))
    bare = keep(_at(_node(ed, FN_SET_OWNER_NO_SEE), x0 + 2820, y0))
    _connect(_pin(body, "OwnerMesh", is_input=False), _pin(bare, "self"))
    _connect(_pin(behind_glass, "ReturnValue", is_input=False),
             _pin(bare, "bNewOwnerNoSee"))
    _connect(BEL.find_then_pin(tuck), _pin(bare, "execute"))

    # False arm: nothing to look down, so the camera goes home.
    home = keep(_at(_node(ed, FN_COMP_SET_WORLD_LOC), x0 + 2040, y0 + 240))
    _connect(cam_out, _pin(home, "self"))
    _connect(shoulder_out, _pin(home, "NewLocation"))
    _connect(_author_unseat(ed, keep, BEL.find_else_pin(armed),
                            x0 + 1260, y0 + 240),
             _pin(home, "execute"))
    level = keep(_at(_node(ed, FN_COMP_SET_WORLD_ROT), x0 + 2040, y0 + 480))
    _connect(cam_out, _pin(level, "self"))
    _connect(boom_rot_out, _pin(level, "NewRotation"))
    _connect(BEL.find_then_pin(home), _pin(level, "execute"))
    # ...and the body shows again: a sniper dropped while scoped leaves no
    # scope to hide behind.
    body_home = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 2040, y0 + 400))
    shown = keep(_at(_node(ed, FN_SET_OWNER_NO_SEE), x0 + 2300, y0 + 240))
    _connect(_pin(body_home, "OwnerMesh", is_input=False), _pin(shown, "self"))
    _set(shown, "bNewOwnerNoSee", "false")
    _connect(BEL.find_then_pin(level), _pin(shown, "execute"))

    ed.add_comment_to_nodes(
        "Down the sights: the camera eases (SightSeat, at the zoom's own "
        f"{COMBAT.ads_interp_speed:g}) from the boom's end to the held "
        "weapon's SightOffset, and turns from the boom's rotation onto the "
        "weapon's sight line (the eye towards SightAim, the front sight's "
        "tip), so the sights are on the middle of the view, where the shot "
        "goes. It waits on the boom until the gun is up (SightSeated: the "
        f"sight line within {SIGHT_SEAT_DEG:g} deg of the view), so the view "
        "stays on the target while the gun rises to it. Written every frame "
        "both ways, so at SightSeat 0 it is "
        "exactly where and as the boom holds it and there is no restore "
        "path; with empty hands it goes straight home. A scoped "
        f"weapon hides past SightSeat {SCOPE_HIDE_BLEND:g}, out of its own "
        "scope's way, and the player's own body with it (OwnerNoSee), so the "
        "arms' hold and recoil animation stay out of the glass.",
        made)
    return (BEL.find_then_pin(bare), BEL.find_then_pin(shown))
