"""A_AimShotgun: the shotgun's own ready pose, the rifle's with both thumbs
placed for a gun with a straight stock and a low sight line, an AnimSequence
keyed here for whatever body the player wears.

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

HOW IT IS MADE
--------------
A copy of the skin's rifle pose, every track re-keyed from it on each build
(so a rifle pose that was retargeted again is followed), and the three joints
of each thumb (PlayerSkin.grip_thumb, support_thumb) keyed constant instead:
each joint's line to the next is swung, by the shortest turn, onto a
direction given in the WEAPON's frame (+X down the barrel, +Y right, +Z up),
SHOTGUN_THUMBS. The last joint has no child to draw a line to; its line is
its bone's own long axis, the one its parent's line runs down (the finger
bones all run down one axis: finger_rig.py, and the mannequin's).

The weapon's frame is the grip's: the weapon is rigid in the right hand,
turned by GripRotation, which grip._grip_rotation solves against the rifle
pose's hand. Nothing but the thumbs differs between the two poses, so the
grip's solve, the fist the Grip part is seated in and the support hand's
point (support_hand.py) come out the same against either.
"""

import unreal

from asset_pipeline.rig_util import mesh_ref_pose
from combat.body_pose import _between, _conj, _mul, _norm, _turn
from combat.graph import _assets, _log
from combat.grip import _grip_rotation, _grip_socket
from combat.hold_pose import _copy_of, _q, _shown
from combat.paths import SHOTGUN_AIM_ANIM_PATH

# {PlayerSkin's thumb: the line of each of its joints to the next, palm out,
# in the weapon's frame}.
SHOTGUN_THUMBS = {
    # From the palm (behind the stock's wrist, on its right) the first runs
    # forward and up onto the top of the wrist, the second over it and down
    # its left side, and the tip points down that side at the other fingers'
    # tips, closing the hand round the wood.
    "grip_thumb": ((0.84, -0.16, 0.52), (0.52, -0.60, -0.60), (0.45, 0.00, -0.89)),
    # The left hand is under the pump, its heel on the left: the thumb lies
    # forward along the pump's left side, closing on it, under the barrel's
    # top.
    "support_thumb": ((0.95, 0.25, 0.18), (0.98, 0.12, -0.05), (0.99, 0.10, -0.10)),
}
# The last joint to the thumb's tip (cm), for the checks: there is no bone.
THUMB_TIP_CM = 3.0


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


def _thumb_locals(skin, comp, ref):
    """{thumb joint: local Transform} for both turned thumbs: the rifle
    pose's translations and scales, the new rotations."""
    weapon = weapon_rotation(skin, comp)
    turned = {}
    for thumb, dirs in SHOTGUN_THUMBS.items():
        turned.update(thumb_rotations(getattr(skin, thumb), dirs, comp, weapon))
    out = {}
    for bone, rotation in turned.items():
        parent = ref[bone][1]
        up = turned.get(parent, comp[parent][1])
        local = comp[bone][2]
        out[bone] = unreal.Transform(
            location=local.translation,
            rotation=unreal.Quat(*_mul(_conj(up), rotation)).rotator(),
            scale=local.scale3d)
    return out


def build_shotgun_pose(skin):
    """Key A_AimShotgun for ``skin``'s body off its rifle pose; returns the
    clip."""
    rifle = _assets().load_asset(skin.aim_rifle)
    if rifle is None:
        raise RuntimeError(f"could not load {skin.aim_rifle}")
    mesh = _assets().load_asset(skin.mesh)
    ref = mesh_ref_pose(mesh)
    thumbs = _thumb_locals(skin, _shown(rifle, mesh, ref), ref)
    model = rifle.data_model_interface
    frames = model.get_number_of_frames()
    n = model.get_number_of_keys()
    # Track names are FNames and can come back in another case than the bones.
    by_lower = {b.lower(): b for b in ref}
    tracks = {by_lower[str(t).lower()] for t in model.get_bone_track_names()} | set(thumbs)

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
            keys = ([t.translation for t in got], [t.rotation for t in got],
                    [t.scale3d for t in got])
        if not ctrl.add_bone_curve(track, False):
            raise RuntimeError(f"could not add a track for {track}")
        if not ctrl.set_bone_track_keys(track, *keys, False):
            raise RuntimeError(f"could not key {track}")
    ctrl.close_bracket(False)
    _assets().save_loaded_asset(clip, False)
    _log(f"built {SHOTGUN_AIM_ANIM_PATH} ({len(tracks)} tracks off "
         f"{skin.aim_rifle.rsplit('/', 1)[-1]}, {n} keys; the thumbs "
         f"{', '.join(sorted(thumbs))} placed for a straight stock)")
    return clip
