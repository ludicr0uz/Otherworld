"""Aiming down the sights: the camera leaves the shoulder boom for the held
weapon's eye point (SightOffset) and turns onto its sight line (towards
SightAim, the front sight's tip), so the player looks through the gun's own
sights in first person. ads.py decides *whether* the player is down the
sights (SightAiming) and how far to zoom; this module owns only where the
camera is and which way it looks; seat.py decides how far it has gone
(SightSeat, from the key: one motion from wherever the camera is) and how far
it has turned onto the sight line (SightLook: only once the gun is up, so the
view stays on the target while the gun rises to it).

Why the camera is moved rather than a second camera switched to: the camera is
what everything else already reads -- the FOV zoom, the aim trace (off the
camera manager) and the HUD -- so one camera that travels keeps all three
right, and SightSeat eases it home off the gun rather than cutting.

Where the camera is while the gun rises: the gun's eye point rides the gun,
and a gun is carried at the hip, so a camera put on the eye point from the
key would ride up with it and the world would swing while the gun stood
still in the view. It stands instead at the anchor (SightAnchor): the head
bone (OwnerMesh's, the one head_hide.py hides) in the owner's frame, taken
every frame the view is not on the sights and held from the cut. Held, not
read live: the ready pose leans the head in to the sights, and a camera on
the live bone was carried a few centimetres with that lean while the gun
rose, a bob under the raise. From the anchor it looks where the player
looks, and the gun is what moves: up from below and to the right of the view
onto the crosshair. Once the gun is up (SightSeated) the camera settles from
the anchor onto the eye point with its turn onto the sight line (SightLook),
a few centimetres over the same fifth of a second.

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

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.nodes import CAMERA_CLASS_PATH, SPRING_ARM_CLASS_PATH, SPRING_ARM_SOCKET
from combat.seat_tuning import SEAT_HOLD, SEAT_VAR, SIGHT_SEAT_DEG
from combat.weapon_component.body_parts import author_parts_no_see
from combat.weapon_component.common import _prop
from combat.weapon_component.head_hide import head_bone
from combat.weapon_component.seat import _author_sight_seat, _author_unseat
from combat.weapon_component.sight_cut import author_cut_turn
from uebp.nodes.actor import (
    FN_ADD_TICK_PREREQ, FN_COMP_SET_WORLD_LOC, FN_COMP_SET_WORLD_ROT, FN_GET_COMP,
    FN_GET_TRANSFORM, FN_SET_HIDDEN, FN_SET_OWNER_NO_SEE, FN_SOCKET_LOC, FN_SOCKET_ROT)
from uebp.nodes.math import (
    FN_AND, FN_BOOL_TO_FLOAT, FN_GREATER_FF, FN_INTERP_FF, FN_INV_XFORM_LOC, FN_MUL_FF,
    FN_NOT, FN_OR, FN_RLERP, FN_ROT_FROM_X, FN_SUB_VV, FN_TRANSFORM_LOC, FN_VLERP, FN_VSIZE)
from combat import item_vars as IV
from combat.weapon_component import vars as WV

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


def _author_sight_line(ed, keep, held, xform, eye_out):
    """The held weapon's sight line in the world, as a pure chain:

        line = TransformLocation(Held, Held.SightAim) - eye

    Returns (the line, whether it is one: longer than SIGHT_LINE_MIN_CM).
    """
    aim_pin, aim_n = _prop(ed, IV.SightAim, held)
    keep(aim_n)
    front = keep(_node(ed, FN_TRANSFORM_LOC))
    _connect(out(xform), _pin(front, "T"))
    _connect(aim_pin, _pin(front, "Location"))
    line = keep(_node(ed, FN_SUB_VV))
    _connect(out(front), _pin(line, "A"))
    _connect(eye_out, _pin(line, "B"))
    length = keep(_node(ed, FN_VSIZE))
    _connect(out(line), _pin(length, "A"))
    has_line = keep(_node(ed, FN_GREATER_FF))
    _connect(out(length), _pin(has_line, "A"))
    _set(has_line, "B", SIGHT_LINE_MIN_CM)
    return (out(line), out(has_line))


def _author_sight_look(ed, keep, line_out, has_line_out, boom_rot, look_out):
    """The camera's rotation down the sights, as a pure chain:

        RLerp(boom's, MakeRotFromX(line), SightLook x (|line| > 1 cm), shortest)

    MakeRotFromX has no roll, so a canted gun does not tip the horizon.
    """
    look = keep(_node(ed, FN_ROT_FROM_X))
    _connect(line_out, _pin(look, "X"))
    weight = keep(_node(ed, FN_BOOL_TO_FLOAT))
    _connect(has_line_out, _pin(weight, "InBool"))
    alpha = keep(_node(ed, FN_MUL_FF))
    _connect(look_out, _pin(alpha, "A"))
    _connect(out(weight), _pin(alpha, "B"))
    turn = keep(_node(ed, FN_RLERP))
    _connect(boom_rot, _pin(turn, "A"))
    _connect(out(look), _pin(turn, "B"))
    _connect(out(alpha), _pin(turn, "Alpha"))
    _set(turn, "bShortestPath", True)
    return out(turn)


def _boom(ed, owner_out):
    """The owner's SpringArmComponent, as a pure node."""
    arm = _node(ed, FN_GET_COMP)
    _connect(owner_out, _pin(arm, "self"))
    _pin(arm, "ComponentClass").set_pin_value(SPRING_ARM_CLASS_PATH)
    return arm


def _author_tick_order(ed, owner_out, exec_in):
    """BeginPlay: tick this component after the camera boom and after the
    owner's mesh (OwnerMesh, cached just before this runs).

    The boom: both tick in TG_PostPhysics, in no promised order. The boom
    moves its end to follow the character and the control rotation when it
    ticks, and the camera rides along at whatever offset it had. Placed before
    the boom has moved, the camera would sit one frame's walk off the sight --
    a few centimetres of shimmer while strafing with the sights up.

    The mesh: the held item rides its hand, and the Tick reads that pose --
    the sight camera (the eye point and the sight line), the muzzle, the
    light, the throw. The mesh's tick group is earlier, but that is not an
    order: on Lvl_Horde_Survival, on about one frame in seven, the hand was
    posed after the camera had been put on the gun, and walking down the
    sights the gun left the crosshair by up to 2.5 degrees
    (probes/probe_sight_lag.py; 0 on Lvl_Forest_1000m with the same code).
    """
    arm = _boom(ed, owner_out)
    after = _node(ed, FN_ADD_TICK_PREREQ)
    _connect(out(arm), _pin(after, "PrerequisiteComponent"))
    _connect(exec_in, _pin(after, "execute"))
    mesh = ed.add_get_member_variable_node(WV.OwnerMesh)
    posed = _node(ed, FN_ADD_TICK_PREREQ)
    _connect(out(mesh, WV.OwnerMesh), _pin(posed, "PrerequisiteComponent"))
    _connect(then(after), _pin(posed, "execute"))
    ed.add_comment_to_nodes(
        "Tick after the camera boom and after the owner's mesh, so the sight "
        "camera, the muzzle and the light read this frame's boom and this "
        "frame's hand, not last frame's.",
        [arm, after, mesh, posed])
    return then(posed)


def _author_sight_camera(ed, tick, pc_out, owner_out, held, armed_out, exec_ins):
    """Put the camera in the sights' view from the key, and ease it home.

        SightBlend = FInterpTo(SightBlend,
                               SightSnapped OR SightSeat > SEAT_HOLD ? 1 : 0,
                               dt, AdsSpeed)
        shoulder   = CameraBoom.GetSocketLocation(SpringEndpoint)
        if IsValid(Held):
            eye    = TransformLocation(Held.GetTransform(), Held.SightOffset)
            if NOT SightSnapped:
                SightAnchor = InverseTransformLocation(
                                  Owner.GetTransform(),
                                  OwnerMesh.GetSocketLocation(head bone))
            anchor = TransformLocation(Owner.GetTransform(), SightAnchor)
            if SightCut: turn the view onto ViewPoint     (sight_cut.py)
            SightSeat, SightSeated, SightLook = ...       (seat.py)
            Camera.SetWorldLocation(VLerp(shoulder, VLerp(anchor, eye, SightLook),
                                          SightSeat))
            Camera.SetWorldRotation(RLerp(boom's, look down the sight line,
                                          SightLook))     (_author_sight_look)
        else:
            SightSeat, SightSeated, SightLook = 0, false, 0
            Camera.SetWorldLocation(shoulder)
            Camera.SetWorldRotation(boom's)

    SightBlend is the body's share of the sights (the pitch, the sway, the
    steady hand): it starts with the cut, as the gun's raise does, and lasts
    until the camera has left the gun. SightSeat is 1 from the cut (seat.py:
    SightSnapped, the player's SightZoomIn after the key, during which the
    camera stays on the boom and the zoom eases in): the camera is at the
    anchor on that frame, and ads.py lands the weapon's own zoom on the same
    frame, so the sniper's glass (which fades on the zoom) is closed round
    the view with the cut. SightLook is the camera's turn onto the sight
    line, and starts only when the gun is up: until then the view keeps
    looking where the player is looking, from the anchor, and the gun rises
    into it from the hip; as it turns, the camera also settles the few
    centimetres from the anchor onto the gun's own eye point. Letting go,
    SightSeat eases home at the gun's AdsSpeed.

    Written every frame, both ways. At SightSeat and SightLook 0 the write
    puts the camera
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
    wanted = keep(ed.add_get_member_variable_node(WV.SightSnapped))
    seat_was = keep(ed.add_get_member_variable_node(SEAT_VAR))
    on_gun = keep(_node(ed, FN_GREATER_FF))
    _connect(out(seat_was, SEAT_VAR), _pin(on_gun, "A"))
    _set(on_gun, "B", SEAT_HOLD)
    either = keep(_node(ed, FN_OR))
    _connect(out(wanted, WV.SightSnapped), _pin(either, "A"))
    _connect(out(on_gun), _pin(either, "B"))
    as_float = keep(_node(ed, FN_BOOL_TO_FLOAT))
    _connect(out(either), _pin(as_float, "InBool"))
    have = keep(ed.add_get_member_variable_node(WV.SightBlend))
    step = keep(_node(ed, FN_INTERP_FF))
    _connect(out(have, WV.SightBlend), _pin(step, "Current"))
    _connect(out(as_float), _pin(step, "Target"))
    _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
    rate = keep(ed.add_get_member_variable_node(WV.AdsSpeed))
    _connect(out(rate, WV.AdsSpeed), _pin(step, "InterpSpeed"))
    blend = keep(ed.add_set_member_variable_node(WV.SightBlend))
    _connect(out(step), _pin(blend, WV.SightBlend))
    for e in exec_ins:
        _connect(e, _pin(blend, "execute"))

    arm = keep(_boom(ed, owner_out))
    shoulder = keep(_node(ed, FN_SOCKET_LOC))
    _connect(out(arm), _pin(shoulder, "self"))
    _set(shoulder, "InSocketName", SPRING_ARM_SOCKET)
    shoulder_out = out(shoulder)
    boom_rot = keep(_node(ed, FN_SOCKET_ROT))
    _connect(out(arm), _pin(boom_rot, "self"))
    _set(boom_rot, "InSocketName", SPRING_ARM_SOCKET)
    boom_rot_out = out(boom_rot)

    cam = keep(_node(ed, FN_GET_COMP))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    cam_out = out(cam)

    armed = keep(ed.add_branch_node())
    _connect(armed_out, _pin(armed, "Condition"))
    _connect(then(blend), _pin(armed, "execute"))

    # True arm: Held is valid, so its transform and SightOffset can be read.
    xform = keep(_node(ed, FN_GET_TRANSFORM))
    _connect(held, _pin(xform, "self"))
    off_pin, off_n = _prop(ed, IV.SightOffset, held)
    keep(off_n)
    eye = keep(_node(ed, FN_TRANSFORM_LOC))
    _connect(out(xform), _pin(eye, "T"))
    _connect(off_pin, _pin(eye, "Location"))
    line_out, has_line_out = _author_sight_line(ed, keep, held, xform, out(eye))
    # Where the camera stands while the gun rises: the head bone in the
    # owner's frame, taken while the view is not on the sights and held from
    # the cut, so the head's lean into the ready pose does not carry the
    # camera. The turn onto the sight line carries it the rest of the way,
    # onto the eye point.
    snapped = keep(ed.add_get_member_variable_node(WV.SightSnapped))
    off_sights = keep(_node(ed, FN_NOT))
    _connect(out(snapped, WV.SightSnapped), _pin(off_sights, "A"))
    taking = keep(ed.add_branch_node())
    _connect(out(off_sights), _pin(taking, "Condition"))
    _connect(then(armed), _pin(taking, "execute"))
    frame = keep(_node(ed, FN_GET_TRANSFORM))
    _connect(owner_out, _pin(frame, "self"))
    body_now = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    head = keep(_node(ed, FN_SOCKET_LOC))
    _connect(out(body_now, WV.OwnerMesh), _pin(head, "self"))
    _set(head, "InSocketName", head_bone())
    local = keep(_node(ed, FN_INV_XFORM_LOC))
    _connect(out(frame), _pin(local, "T"))
    _connect(out(head), _pin(local, "Location"))
    stand = keep(ed.add_set_member_variable_node(WV.SightAnchor))
    _connect(out(local), _pin(stand, WV.SightAnchor))
    _connect(then(taking), _pin(stand, "execute"))
    kept = keep(ed.add_get_member_variable_node(WV.SightAnchor))
    anchor = keep(_node(ed, FN_TRANSFORM_LOC))
    _connect(out(frame), _pin(anchor, "T"))
    _connect(out(kept, WV.SightAnchor), _pin(anchor, "Location"))
    # On the cut's frame the view turns from the anchor onto what the boom's
    # view was on, so the crosshair's point does not move (sight_cut.py).
    turned, view_rot = author_cut_turn(
        ed, keep, pc_out, out(anchor), boom_rot_out, (then(stand), else_(taking)))
    seated, seat_out, look_out = _author_sight_seat(
        ed, tick, keep, line_out, has_line_out, view_rot, turned)
    perch = keep(_node(ed, FN_VLERP))
    _connect(out(anchor), _pin(perch, "A"))
    _connect(out(eye), _pin(perch, "B"))
    _connect(look_out, _pin(perch, "Alpha"))
    mix = keep(_node(ed, FN_VLERP))
    _connect(shoulder_out, _pin(mix, "A"))
    _connect(out(perch), _pin(mix, "B"))
    _connect(seat_out, _pin(mix, "Alpha"))
    to_sight = keep(_node(ed, FN_COMP_SET_WORLD_LOC))
    _connect(cam_out, _pin(to_sight, "self"))
    _connect(out(mix), _pin(to_sight, "NewLocation"))
    _connect(seated, _pin(to_sight, "execute"))
    look = _author_sight_look(ed, keep, line_out, has_line_out, view_rot, look_out)
    to_line = keep(_node(ed, FN_COMP_SET_WORLD_ROT))
    _connect(cam_out, _pin(to_line, "self"))
    _connect(look, _pin(to_line, "NewRotation"))
    _connect(then(to_sight), _pin(to_line, "execute"))

    # ...and a scoped weapon gets out of its own scope's way. Written every
    # frame on Held, which is the one weapon the equip sequence shows, so the
    # frame the sights come down (or Held changes) it is visible again.
    scoped, scoped_n = _prop(ed, IV.Scoped, held)
    keep(scoped_n)
    far_in = keep(_node(ed, FN_GREATER_FF))
    _connect(seat_out, _pin(far_in, "A"))
    _set(far_in, "B", SCOPE_HIDE_BLEND)
    behind_glass = keep(_node(ed, FN_AND))
    _connect(scoped, _pin(behind_glass, "A"))
    _connect(out(far_in), _pin(behind_glass, "B"))
    tuck = keep(_node(ed, FN_SET_HIDDEN))
    _connect(held, _pin(tuck, "self"))
    _connect(out(behind_glass), _pin(tuck, "bNewHidden"))
    _connect(then(to_line), _pin(tuck, "execute"))
    body = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    bare = keep(_node(ed, FN_SET_OWNER_NO_SEE))
    _connect(out(body, WV.OwnerMesh), _pin(bare, "self"))
    _connect(out(behind_glass), _pin(bare, "bNewOwnerNoSee"))
    _connect(then(tuck), _pin(bare, "execute"))
    # ...and whatever is drawn under it (body_parts.py: a MetaHuman skin).
    bare_tail = author_parts_no_see(ed, keep, then(bare), no_see_out=out(behind_glass))

    # False arm: nothing to look down, so the camera goes home.
    home = keep(_node(ed, FN_COMP_SET_WORLD_LOC))
    _connect(cam_out, _pin(home, "self"))
    _connect(shoulder_out, _pin(home, "NewLocation"))
    _connect(_author_unseat(ed, keep, else_(armed)), _pin(home, "execute"))
    level = keep(_node(ed, FN_COMP_SET_WORLD_ROT))
    _connect(cam_out, _pin(level, "self"))
    _connect(boom_rot_out, _pin(level, "NewRotation"))
    _connect(then(home), _pin(level, "execute"))
    # ...and the body shows again: a sniper dropped while scoped leaves no
    # scope to hide behind.
    body_home = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    shown = keep(_node(ed, FN_SET_OWNER_NO_SEE))
    _connect(out(body_home, WV.OwnerMesh), _pin(shown, "self"))
    _set(shown, "bNewOwnerNoSee", False)
    _connect(then(level), _pin(shown, "execute"))
    shown_tail = author_parts_no_see(ed, keep, then(shown), no_see=False)

    ed.add_comment_to_nodes(
        "Down the sights: with the cut (SightSnapped, the player's SightZoomIn "
        "after the key, the zoom easing in meanwhile) the camera is at once "
        f"(SightSeat 1) in the sights' view, standing at the anchor (the head "
        f"bone, {head_bone()}, in the owner's frame, held from the cut so the "
        "head's lean does not carry it) and "
        "looking where the player looks, while the gun rises into the view "
        "from the hip. It turns (SightLook) from the boom's rotation onto the "
        "weapon's sight line (the eye towards SightAim, the front sight's "
        "tip), so the sights are on the middle of the view, where the shot "
        "goes, and settles from the head onto the weapon's SightOffset as it "
        "turns. The turn waits until the gun is up (SightSeated: the "
        f"sight line within {SIGHT_SEAT_DEG:g} deg of the view), so the view "
        "stays on the target while the gun rises to it. Letting go, the seat "
        "eases home at the gun's own AdsZoomSpeed (AdsSpeed). Written every frame "
        "both ways, so at SightSeat and SightLook 0 it is "
        "exactly where and as the boom holds it and there is no restore "
        "path; with empty hands it goes straight home. A scoped "
        f"weapon hides past SightSeat {SCOPE_HIDE_BLEND:g}, out of its own "
        "scope's way, and the player's own body with it (OwnerNoSee), so the "
        "arms' hold and recoil animation stay out of the glass. What is "
        "drawn under the mannequin (a MetaHuman) goes with it both ways.",
        made)
    return (bare_tail, shown_tail)
