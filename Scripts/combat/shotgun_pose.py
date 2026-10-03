"""A_AimShotgun: the shotgun's own ready pose, the rifle's with both thumbs
and the left hand placed for a gun with a straight stock, a low sight line
and a slim pump, an AnimSequence keyed here for whatever body the player
wears.

WHY NOT THE RIFLE'S POSE
------------------------
The rifle ready pose (MF_Rifle_Idle_ADS) holds a pistol grip under a tall
receiver: the right thumb lies forward along the grip's left side, and the
left thumb stands up the side of the handguard. The AK's and the Val's sight
lines run 14 cm above the grip, so neither thumb reaches the picture. The
shotgun (Quaternius Shotgun_3) has a straight stock and a sight line that
skims the receiver 7 cm above the grip, and down its sights both did:

  - the left thumb stood up beside the barrel, its last joint 3 cm ABOVE the
    sight line and its tip 5: a finger standing next to the bead;
  - the right thumb, 5 cm under the line and 5-15 cm from the eye, came up
    from the bottom of the view beside the receiver.

A hand on a straight stock puts its thumb over the wrist, and a hand under a
pump lays its thumb along the wood.

The left hand cups a handguard as deep as the AK's: its palm stands on edge
beside it and its fingers reach across underneath. The shotgun's pump is a
5 cm bar (weapon_models.SHOTGUN_PUMP) where the middle of that handguard
would be, so the knuckles were INSIDE the wood (the index's and the middle's
by 2 cm) and the fingers came out of its right side, 3-5 cm off it, and stood
up in the air. A hand on a pump lies under it, palm up, and its fingers come
up the far side and close on the wood.

HOW IT IS MADE
--------------
A copy of the skin's rifle pose, every track re-keyed from it on each build
(so a rifle pose that was retargeted again is followed), and these keyed
constant instead, all from directions given in the WEAPON's frame (+X down
the barrel, +Y right, +Z up):

  - the left hand is turned about its own wrist (SUPPORT_PALM): the line from
    the wrist to the middle knuckle and the line across the knuckles, index
    to pinky, are swung onto the table's, which lays the palm under the pump;
  - the hand, so shaped, is then MOVED to where its own fingers close on the
    pump (pump_seat.py: every joint as near 0.75 cm off the wood as the worst
    can be), and the left arm's two bones are turned to carry the wrist there
    (asset_pipeline/two_hands.reach), by the same turn on every key so the
    arm keeps the rifle pose's breathing. Where the rifle pose's wrist was is
    a matter of the body's arms and how big its hands are; the pump is where
    it is. The support hand's point (support_hand.py) is read off this clip,
    so down the sights the hand is held where it was seated;
  - the three joints of each thumb (PlayerSkin.grip_thumb, support_thumb) and
    of each left finger (support_fingers): each joint's line to the next is
    swung, by the shortest turn, onto its direction in SHOTGUN_THUMBS or
    SUPPORT_FINGERS. The last joint has no child to draw a line to; its line
    is its bone's own long axis, the one its parent's line runs down (the
    finger bones all run down one axis: finger_rig.py, and the mannequin's).

The weapon's frame is the grip's: the weapon is rigid in the right hand,
turned by GripRotation, which grip._grip_rotation solves against the rifle
pose's hand. The right hand differs only in its thumb, so the grip's solve
and the fist the Grip part is seated in come out the same against either
pose.
"""

import unreal

from asset_pipeline.rig_util import mesh_ref_pose
from asset_pipeline.two_hands import reach
from combat import pump_seat
from combat.body_pose import _between, _conj, _mul, _norm, _turn
from combat.log import _log
from uebp.graph import _assets
from combat.grip import (
    _grip_location, _grip_rotation, _grip_socket, part_placement,
)
from combat.hold_pose import _below, _copy_of, _q, _shown
from combat.paths import SHOTGUN_AIM_ANIM_PATH
from combat.weapon_models import SHOTGUN_PUMP, shotgun_outline

# {PlayerSkin's thumb: the line of each of its joints to the next, palm out,
# in the weapon's frame}.
SHOTGUN_THUMBS = {
    # From the palm (behind the stock's wrist, on its right) the first runs
    # forward and up onto the top of the wrist, the second over it and down
    # its left side, and the tip points down that side at the other fingers'
    # tips, closing the hand round the wood.
    "grip_thumb": ((0.84, -0.16, 0.52), (0.52, -0.60, -0.60), (0.45, 0.00, -0.89)),
    # The left hand is under the pump, its heel on the left: the thumb runs
    # forward and in to the pump's left side and lies along it, under the
    # barrel's top.
    "support_thumb": ((0.83, 0.53, 0.17), (0.93, 0.33, 0.15), (0.97, 0.20, 0.10)),
}
# The left hand's turn about its wrist: where the line from the wrist to the
# middle knuckle points, a little down and across under the pump, and the line
# across the knuckles from the index's to the pinky's, level, so the palm
# faces up at the wood.
SUPPORT_PALM = dict(forward=(0.878, 0.391, -0.275), across=(-0.407, 0.914, 0.0))
# PlayerSkin.support_fingers, index first: each joint's line to the next.
# The first runs from the knuckle under the pump to its lower right edge, the
# second up its right side, and the tip leans in over the wood at the barrel.
# The index's knuckle is the one furthest left, so its first joint lies under
# the wood; the pinky's is already at the right edge and goes straight up.
SUPPORT_FINGERS = (
    ((0.25, 0.95, -0.15), (0.10, 0.45, 0.89), (0.10, -0.10, 0.99)),
    ((0.55, 0.78, 0.20), (0.30, -0.20, 0.93), (0.30, -0.40, 0.87)),
    ((0.83, 0.47, 0.29), (0.50, -0.13, 0.85), (0.40, -0.30, 0.87)),
    ((0.60, 0.10, 0.79), (0.50, -0.20, 0.84), (0.85, -0.30, 0.43)),
)
# The last joint to the thumb's or the finger's tip (cm), for the checks:
# there is no bone.
THUMB_TIP_CM = 3.0
FINGER_TIP_CM = 2.5


def weapon_rotation(skin, comp):
    """The weapon's frame in the component's, a quat, against a component pose
    ``comp`` ({bone: (location, quat, ...)}): the grip socket's turn, then
    GripRotation."""
    _mesh_yaw, socket = _grip_socket()
    bone = str(socket.get_editor_property("bone_name"))
    in_bone = _q(socket.get_editor_property("relative_rotation").quaternion())
    grip = _q(_grip_rotation(skin.aim_rifle).quaternion())
    return _mul(_mul(comp[bone][1], in_bone), grip)


def thumb_lines(bones, comp):
    """[each joint's line to the next, unit, component space] for one thumb's
    ``bones``, against a component pose ``comp``. The last joint's is its
    bone's long axis: the axis its parent's line runs down. Pure."""
    lines = [_norm(tuple(c - p for c, p in zip(comp[child][0], comp[bone][0])))
             for bone, child in zip(bones, bones[1:])]
    axis = _turn(_conj(comp[bones[-2]][1]), lines[-1])
    return lines + [_turn(comp[bones[-1]][1], axis)]


def thumb_rotations(bones, dirs, comp, weapon):
    """{thumb joint: new component-space quat}: each joint's line swung onto
    its direction in ``dirs`` (the weapon's frame, ``weapon`` its quat in the
    component). Pure."""
    return {bone: _mul(_between(line, _turn(weapon, _norm(want))), comp[bone][1])
            for bone, line, want in zip(bones, thumb_lines(bones, comp), dirs)}


def palm_turn(hand, index, middle, pinky, weapon):
    """The turn, in the component, that lays a hand as SUPPORT_PALM says:
    ``hand``, ``index``, ``middle`` and ``pinky`` are where its wrist and
    three of its knuckles are, ``weapon`` the weapon's quat. Pure."""
    def sub(a, b):
        return tuple(p - q for p, q in zip(a, b))

    def across_of(forward, across):
        # The part of ``across`` square to ``forward``: the roll about it.
        d = sum(f * a for f, a in zip(forward, across))
        return _norm(tuple(a - d * f for f, a in zip(forward, across)))

    forward = _norm(sub(middle, hand))
    want = _norm(_turn(weapon, SUPPORT_PALM["forward"]))
    swing = _between(forward, want)
    across = across_of(want, _turn(swing, sub(pinky, index)))
    roll = _between(across, across_of(want, _turn(weapon, SUPPORT_PALM["across"])))
    return _mul(roll, swing)


def support_hand_pose(skin, comp, ref, weapon):
    """``comp`` with the left hand turned about its wrist onto SUPPORT_PALM,
    everything under it carried round rigidly: (the pose, the hand bone)."""
    hand = skin.pose_bones["hand_l"]
    index, middle, _ring, pinky = (f[0] for f in skin.support_fingers)
    wrist = comp[hand][0]
    turn = palm_turn(wrist, comp[index][0], comp[middle][0], comp[pinky][0], weapon)
    out = dict(comp)
    for bone in ref:
        if bone == hand or _below(ref, bone, hand):
            loc, quat, local = comp[bone][:3]
            off = _turn(turn, tuple(p - w for p, w in zip(loc, wrist)))
            out[bone] = (tuple(w + o for w, o in zip(wrist, off)), _mul(turn, quat), local)
    return out, hand


def weapon_origin(comp, grip_loc):
    """Where the weapon's own origin is in the component, against a component
    pose ``comp``: the grip socket, then GripLocation (the weapon is attached
    at the socket and moved by it, in the socket's frame)."""
    _mesh_yaw, socket = _grip_socket()
    bone = str(socket.get_editor_property("bone_name"))
    in_bone = _q(socket.get_editor_property("relative_rotation").quaternion())
    at = socket.get_editor_property("relative_location")
    loc = tuple(a + g for a, g in zip((at.x, at.y, at.z), _turn(in_bone, grip_loc)))
    return tuple(c + o for c, o in zip(comp[bone][0], _turn(comp[bone][1], loc)))


def finger_points(bones, dirs, placed, weapon, tip_cm):
    """Where a finger's (or thumb's) joints and tip are once its joints point
    along ``dirs`` (the weapon's frame): its knuckle where ``placed`` has it,
    each bone its own length. Component space. Pure."""
    at = [placed[bones[0]][0]]
    lengths = [sum((c - p) ** 2 for p, c in zip(placed[a][0], placed[b][0])) ** 0.5
               for a, b in zip(bones, bones[1:])] + [tip_cm]
    for want, length in zip(dirs, lengths):
        line = _turn(weapon, _norm(want))
        at.append(tuple(p + length * d for p, d in zip(at[-1], line)))
    return at


def pump_move(skin, placed, weapon, origin):
    """How far to move the shaped left hand so its fingers close on the pump
    (pump_seat.seat), in the component."""
    into = _conj(weapon)

    def in_weapon(point):
        return _turn(into, tuple(p - o for p, o in zip(point, origin)))

    joints = [in_weapon(p) for bones, dirs in zip(skin.support_fingers, SUPPORT_FINGERS)
              for p in finger_points(bones, dirs, placed, weapon, FINGER_TIP_CM)]
    thumb = [in_weapon(p) for p in finger_points(
        skin.support_thumb, SHOTGUN_THUMBS["support_thumb"], placed, weapon,
        THUMB_TIP_CM)[1:]]
    centre, _rot, half = part_placement(shotgun_outline(), "Barrel")
    move = pump_seat.seat(SHOTGUN_PUMP, joints, thumb, centre.z + half.z)
    was, now = (pump_seat.misfit(SHOTGUN_PUMP, joints, m)
                for m in ((0.0, 0.0, 0.0), move))
    _log(f"A_AimShotgun: the left hand moved ({move[0]:.1f}, {move[1]:.1f}, "
         f"{move[2]:.1f}) cm in the weapon's frame onto the pump: its worst "
         f"joint {was:.2f} -> {now:.2f} cm from riding "
         f"{pump_seat.SEAT_OFF_CM:g} cm off the wood")
    return _turn(weapon, move)


def _keyed_locals(skin, comp, ref):
    """({bone: local Transform} for everything this pose holds still: the left
    hand, its fingers and both thumbs; {bone: local turn} for the left arm's
    two bones, to be laid over every key of theirs). The rifle pose's
    translations and scales, the new rotations."""
    weapon = weapon_rotation(skin, comp)
    placed, hand = support_hand_pose(skin, comp, ref, weapon)
    turned = {hand: placed[hand][1]}
    for thumb, dirs in SHOTGUN_THUMBS.items():
        turned.update(thumb_rotations(getattr(skin, thumb), dirs, placed, weapon))
    for bones, dirs in zip(skin.support_fingers, SUPPORT_FINGERS):
        turned.update(thumb_rotations(bones, dirs, placed, weapon))

    # The shaped hand, moved onto the pump; the arm turned to carry it there.
    grip_rot = _grip_rotation(skin.aim_rifle)
    grip_loc = _grip_location(skin.aim_rifle, grip_rot, shotgun_outline())
    origin = weapon_origin(comp, grip_loc)
    upper_b, fore_b = (skin.pose_bones[f"{k}_l"] for k in ("upperarm", "forearm"))
    wrist = placed[hand][0]
    target = tuple(w + m for w, m in zip(wrist, pump_move(skin, placed, weapon, origin)))
    upper, fore = reach(comp[upper_b][0], comp[fore_b][0], wrist, target)
    arm = {upper_b: _mul(upper, comp[upper_b][1]),
           fore_b: _mul(fore, _mul(upper, comp[fore_b][1]))}
    carried = {}
    for bone in (upper_b, fore_b):
        up = arm.get(ref[bone][1], comp[ref[bone][1]][1])
        was = _q(comp[bone][2].rotation)
        carried[bone] = _mul(_conj(was), _mul(_conj(up), arm[bone]))
    turned.update(arm)

    out = {}
    for bone, rotation in turned.items():
        if bone in arm:
            continue
        parent = ref[bone][1]
        up = turned.get(parent, placed[parent][1])
        local = comp[bone][2]
        out[bone] = unreal.Transform(
            location=local.translation,
            rotation=unreal.Quat(*_mul(_conj(up), rotation)).rotator(),
            scale=local.scale3d)
    return out, carried


def build_shotgun_pose(skin):
    """Key A_AimShotgun for ``skin``'s body off its rifle pose; returns the
    clip."""
    rifle = _assets().load_asset(skin.aim_rifle)
    if rifle is None:
        raise RuntimeError(f"could not load {skin.aim_rifle}")
    mesh = _assets().load_asset(skin.mesh)
    ref = mesh_ref_pose(mesh)
    thumbs, carried = _keyed_locals(skin, _shown(rifle, mesh, ref), ref)
    model = rifle.data_model_interface
    frames = model.get_number_of_frames()
    n = model.get_number_of_keys()
    # Track names are FNames and can come back in another case than the bones.
    by_lower = {b.lower(): b for b in ref}
    tracks = ({by_lower[str(t).lower()] for t in model.get_bone_track_names()}
              | set(thumbs) | set(carried))

    clip = _copy_of(skin.aim_rifle, SHOTGUN_AIM_ANIM_PATH)
    ctrl = clip.controller
    ctrl.open_bracket(unreal.Text("Key the shotgun's ready pose"), False)
    ctrl.remove_all_bone_tracks(False)
    ctrl.set_frame_rate(model.get_frame_rate(), False)
    ctrl.set_number_of_frames(unreal.FrameNumber(frames), False)
    for track in sorted(tracks):
        if track in thumbs:
            xf = thumbs[track]
            keys = [xf.translation] * n, [xf.rotation] * n, [xf.scale3d] * n
        else:
            got = [unreal.AnimationLibrary.get_bone_pose_for_frame(rifle, track, f, False)
                   for f in range(n)]
            rots = [t.rotation for t in got]
            if track in carried:
                # The rifle pose's own motion, with the one turn laid over it.
                rots = [unreal.Quat(*_mul(_q(r), carried[track])) for r in rots]
            keys = ([t.translation for t in got], rots, [t.scale3d for t in got])
        if not ctrl.add_bone_curve(track, False):
            raise RuntimeError(f"could not add a track for {track}")
        if not ctrl.set_bone_track_keys(track, *keys, False):
            raise RuntimeError(f"could not key {track}")
    ctrl.close_bracket(False)
    _assets().save_loaded_asset(clip, False)
    _log(f"built {SHOTGUN_AIM_ANIM_PATH} ({len(tracks)} tracks off "
         f"{skin.aim_rifle.rsplit('/', 1)[-1]}, {n} keys; both thumbs, the left "
         f"hand and its fingers placed for a straight stock and a pump: "
         f"{len(thumbs)} bones; the left arm carries the hand onto the pump)")
    return clip
