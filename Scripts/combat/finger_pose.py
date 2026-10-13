"""A gun's own ready clip, its fingers bent onto that gun's model: the clip
its row's ready pose is, with every finger that meets the model closed on it
(finger_fit.py), keyed for the rows weapon_models.GUN_FINGERS names.

WHY A CLIP PER GUN
------------------
A ready pose is a shipped clip (Lyra's rifle ADS idle), and its hands are
shaped for Lyra's rifle. gun_hold.py brings both hands to the gun, each as a
rigid piece: the fingers then hang 0.3 to 4.2 cm off an AK's handguard and 1
to 2.4 cm off its grip. Every item already names the clip it is held in
(BP_WeaponItem.AimPose, which the equip plays and the look replicates), so a
gun whose fingers are fitted is given a clip of its own, A_Aim<Blueprint>: the
row's pose (`pose`) frame for frame, but for the fingers that met the model,
which hold one bend on every frame. No graph changes, and every machine's
copy plays it.

WHAT IS BENT
------------
Against every part of the gun's outline (and the row's measured support box):

  - the left hand's four fingers, with the hand where the seat has it
    (gun_hold.support_move: where the IK holds it down the sights);
  - the left thumb, swung at its base onto the part, under the seat's ceiling;
  - the right hand's middle, ring and little fingers. Its index is the
    clip's (it is at the trigger, verify/grip_fit.py) and so is its thumb
    (it already lies along the receiver).

The grip and the left hand's point are solved against the row's `pose`, not
this clip: the fingers are bent last, onto a gun that is already in the hand.

The left fingers lie on what the hand holds and the parts beside it; where
that is a part of the outline itself, on the parts running through it too
(finger_fit.through: the shotgun's tube and barrel, bare behind its pump).

A NEW GUN: its Blueprint's name in weapon_models.GUN_FINGERS; the build logs
each finger's bend, verify/finger_pose.py holds the saved clip to the model
and probes/probe_gun_hands.py reads the live fingers.
"""

import unreal

from asset_pipeline.rig_util import mesh_ref_pose
from combat import finger_fit, gun_hold
from combat.body_pose import _conj, _mul, _turn
from combat.hold_pose import _copy_of
from combat.log import _log
from combat.paths import WEAPON_DIR
from combat.weapon_models import GUN_FINGERS
from uebp.graph import _assets

FINGER_NAMES = ("index", "middle", "ring", "little")


def _name(spec):
    return spec["path"].rsplit("/", 1)[-1]


def fitted(spec):
    """True for a row whose fingers are bent onto its model."""
    return _name(spec) in GUN_FINGERS


def clip_for(name):
    """Where the ready clip of the gun whose Blueprint is ``name`` is:
    BP_AssaultRifle's is A_AimAssaultRifle."""
    return f"{WEAPON_DIR}/Anims/A_Aim{name.split('_', 1)[-1]}"


def clip_path(spec):
    """Where the row's own ready clip is."""
    return clip_for(_name(spec))


def clips():
    """Every fitted gun's ready clip."""
    return tuple(clip_for(name) for name in GUN_FINGERS)


def solid(skin, spec, comp, placed):
    """(the boxes the left hand's fingers lie on, the right hand's). The
    left: what it holds (the row's part or measured box) and every part
    beside that; a part the measured box is cut out of (the Val's receiver,
    whose outline box reaches under its handguard) is not one, but a part
    that runs through a part of the outline the row names is (the shotgun's
    magazine tube and barrel, bare behind and in front of its pump: the
    little finger lies behind the wood, on the tube). The right: every part
    of the outline."""
    box = gun_hold.support_box(skin, spec, comp, placed)
    parts = [gun_hold.part_box(spec["parts"], part[0]) for part in spec["parts"]]
    return (parts if finger_fit.through(gun_hold.support_of(spec)) else [box] + list(gun_hold.beside(spec, box).values()),
            parts)


def hands(skin, spec, comp, placed):
    """{finger's label: (its bones, its joints and tip in the weapon's
    frame, the boxes it lies on)} for the fingers that are bent, and the
    same for the left thumb: the left hand moved to its seat."""
    left, right = solid(skin, spec, comp, placed)
    move = gun_hold.support_move(skin, spec, quiet=True)

    def points(bones, tip_cm, by):
        return [tuple(c + m for c, m in zip(placed(p), by))
                for p in gun_hold.finger_points(bones, comp, tip_cm)]

    fingers = {f"left {name}": (bones, points(bones, gun_hold.FINGER_TIP_CM, move), left)
               for name, bones in zip(FINGER_NAMES, skin.support_fingers)}
    fingers.update({f"right {name}": (bones, points(bones, gun_hold.FINGER_TIP_CM,
                                                    (0.0, 0.0, 0.0)), right)
                    for name, bones in list(zip(FINGER_NAMES, skin.grip_fingers))[1:]})
    thumb = (skin.support_thumb, points(skin.support_thumb, gun_hold.THUMB_TIP_CM, move), left)
    return fingers, thumb


def measure(skin, spec, clip=None):
    """{finger's label: (how many of its riding points are on the gun, how
    far (cm) its nearest and its furthest are from it)} for the bent
    fingers, and "left thumb" (its joints past the first and its tip), in
    ``clip`` (the row's pose by default) with the gun in the hand."""
    comp, _weapon, placed = gun_hold.held(skin, spec, clip)
    fingers, (_bones, thumb, boxes) = hands(skin, spec, comp, placed)

    def off(points, boxes):
        d = [finger_fit.nearest(boxes, [p]) for p in points]
        return min(d), max(d)

    out = {label: (finger_fit.on(boxes, points),) + off(finger_fit.riding(points), boxes)
           for label, (_bones, points, boxes) in fingers.items()}
    out["left thumb"] = (0,) + off(thumb[1:], boxes)
    return out


def expected(skin, spec):
    """measure() as the fit's own arithmetic has it: the row's pose with each
    finger's points bent by close() and the thumb's by swing(). What a clip
    that was keyed right measures."""
    comp, _weapon, placed = gun_hold.held(skin, spec)
    fingers, (_bones, thumb, thumb_boxes) = hands(skin, spec, comp, placed)

    def off(points, boxes):
        d = [finger_fit.nearest(boxes, [p]) for p in points]
        return min(d), max(d)

    out = {}
    for label, (_bones, points, boxes) in fingers.items():
        angles, met = finger_fit.close(points, boxes)
        if met:
            points = finger_fit.posed(points, finger_fit.hinge(points), angles)
        out[label] = (finger_fit.on(boxes, points),) + off(finger_fit.riding(points), boxes)
    axis, deg = finger_fit.swing(thumb, thumb_boxes, gun_hold.ceiling(spec))
    out["left thumb"] = (0,) + off(finger_fit.swung(thumb, axis, deg)[1:], thumb_boxes)
    return out


def fit(skin, spec):
    """({bone: (axis in the weapon's frame, degrees)} for every bone that
    turns, {finger's label: its joints' angles, or None where it is left as
    the clip has it}), against the row's pose."""
    comp, _weapon, placed = gun_hold.held(skin, spec)
    fingers, (thumb_bones, thumb, thumb_boxes) = hands(skin, spec, comp, placed)
    turns, bends = {}, {}
    for label, (bones, points, boxes) in fingers.items():
        angles, met = finger_fit.close(points, boxes)
        bends[label] = angles if met else None
        if met:
            axis, total = finger_fit.hinge(points), 0.0
            for bone, angle in zip(bones, angles):
                total += angle
                turns[bone] = (axis, total)
    axis, deg = finger_fit.swing(thumb, thumb_boxes, gun_hold.ceiling(spec))
    bends["left thumb"] = (deg,) if deg else None
    if deg:
        turns.update({bone: (axis, deg) for bone in thumb_bones})
    return turns, bends


def local_poses(skin, spec, turns):
    """{bone: its local Transform} for the bones of ``turns``, in the row's
    pose with each turned in the weapon's frame."""
    mesh = _assets().load_asset(skin.mesh)
    ref = mesh_ref_pose(mesh)
    comp, weapon, _placed = gun_hold.held(skin, spec)

    def now(bone):
        if bone not in turns:
            return comp[bone][1]
        axis, deg = turns[bone]
        return _mul(finger_fit.quat(_turn(weapon, axis), deg), comp[bone][1])

    out = {}
    for bone in turns:
        local = comp[bone][2]
        rot = _mul(_conj(now(ref[bone][1])), now(bone))
        out[bone] = unreal.Transform(location=local.translation,
                                     rotation=unreal.Quat(*rot).rotator(),
                                     scale=local.scale3d)
    return out


def _bake(spec, bent):
    """The row's clip: its pose frame for frame, the bones of ``bent``
    ({bone: local Transform}) held on every frame; saved."""
    src = _assets().load_asset(spec["pose"])
    model = src.data_model_interface
    frames, rate = model.get_number_of_frames(), model.get_frame_rate()
    fps = rate.numerator / float(rate.denominator)
    times = [min(f / fps, src.get_play_length()) for f in range(frames + 1)]
    held = {b.lower() for b in bent}
    moving = [t for t in (str(n) for n in model.get_bone_track_names())
              if t.lower() not in held]
    poses = [unreal.AnimationLibrary.get_bone_poses_for_time(src, moving, t, False)
             for t in times]
    clip = _copy_of(spec["pose"], clip_path(spec))
    ctrl = clip.controller
    ctrl.open_bracket(unreal.Text("Bend the fingers onto a gun"), False)
    ctrl.remove_all_bone_tracks(False)
    ctrl.set_frame_rate(rate, False)
    ctrl.set_number_of_frames(unreal.FrameNumber(frames), False)
    tracks = [(t, [pose[i] for pose in poses]) for i, t in enumerate(moving)]
    tracks += [(bone, [xf] * len(times)) for bone, xf in sorted(bent.items())]
    for track, xfs in tracks:
        if not ctrl.add_bone_curve(track, False):
            raise RuntimeError(f"could not add a track for {track}")
        if not ctrl.set_bone_track_keys(track, [x.translation for x in xfs],
                                        [x.rotation for x in xfs],
                                        [x.scale3d for x in xfs], False):
            raise RuntimeError(f"could not key {track}")
    ctrl.close_bracket(False)
    _assets().save_loaded_asset(clip, False)
    return clip


def build_finger_pose(skin, spec):
    """Key ``spec``'s own ready clip and say what each finger did."""
    turns, bends = fit(skin, spec)
    clip = _bake(spec, local_poses(skin, spec, turns))
    was, now = measure(skin, spec), measure(skin, spec, clip_path(spec))
    said = "; ".join(
        f"{label} " + ("left as the clip has it" if bend is None else
                       "/".join(f"{a:+.0f}" for a in bend) + " deg")
        + f", {was[label][1]:.2f} to {was[label][2]:.2f} -> "
          f"{now[label][1]:.2f} to {now[label][2]:.2f} cm"
        for label, bend in bends.items())
    _log(f"{spec['display']}: built {clip_path(spec)} off "
         f"{spec['pose'].rsplit('/', 1)[-1]}, its fingers bent onto the model "
         f"(each finger's bend, and its nearest and furthest riding point from the gun): {said}")
    return clip


def build_finger_poses(skin, specs):
    """Every fitted row's clip; {path: clip}."""
    return {clip_path(spec): build_finger_pose(skin, spec)
            for spec in specs if fitted(spec)}
