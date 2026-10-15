"""Draw a retargeted crawl's legs in toward the body's line (leg_spread.py
says how far and why).  Run inside the editor (import_fal.py), before
ik_follow.follow_feet keys the IK feet onto the feet it moved.

Frame by frame each thigh is turned about the vertical through the hip, then
each calf about the vertical through the knee, so the segment's angle off
straight back is LEG_SPREAD of the pack's; the foot rides on the calf.
"""
import unreal

from asset_pipeline.leg_spread import LEG_SPREAD, narrowed_turn

AL = unreal.AnimationLibrary
LEGS = (("thigh_l", "calf_l", "foot_l"), ("thigh_r", "calf_r", "foot_r"))


def _comp(clip, bone, frame):
    xf = unreal.Transform()
    for b in AL.find_bone_path_to_root(clip, bone):
        xf = xf.multiply(AL.get_bone_pose_for_frame(clip, b, frame, False))
    return xf


def _turn_about(at, yaw):
    """A transform turning ``yaw`` degrees about the vertical through ``at``."""
    return (unreal.Transform(location=unreal.Vector(-at.x, -at.y, -at.z))
            .multiply(unreal.Transform(rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw)))
            .multiply(unreal.Transform(location=at)))


def _xy(v):
    return (v.x, v.y)


def _leg_keys(clip, thigh, calf, foot, n, spread):
    hip_parent = str(AL.find_bone_path_to_root(clip, thigh)[1])
    keys = {thigh: ([], [], []), calf: ([], [], [])}
    for f in range(n):
        parent, t, c, ft = (_comp(clip, b, f) for b in (hip_parent, thigh, calf, foot))
        hip, knee, toe = t.translation, c.translation, ft.translation
        first = _turn_about(hip, narrowed_turn(_xy(knee - hip), _xy(knee - hip), spread))
        t2, c1 = t.multiply(first), c.multiply(first)
        knee1, toe1 = c1.translation, ft.multiply(first).translation
        c2 = c1.multiply(_turn_about(knee1, narrowed_turn(_xy(toe1 - knee1), _xy(toe - knee),
                                                            spread)))
        for bone, local in ((thigh, t2.multiply(parent.inverse())),
                            (calf, c2.multiply(t2.inverse()))):
            keys[bone][0].append(local.translation)
            keys[bone][1].append(local.rotation)
            keys[bone][2].append(unreal.Vector(1.0, 1.0, 1.0))
    return keys


def narrow_legs(clip, spread=LEG_SPREAD):
    """Key ``clip``'s thighs and calves in toward the body's line (unsaved:
    follow_feet saves it)."""
    probe = _turn_about(unreal.Vector(0, 0, 0), 90.0).transform_direction(unreal.Vector(1, 0, 0))
    if probe.y < 0.99:
        raise RuntimeError(f"a yaw of 90 turns +X to {probe}, not +Y")
    n = clip.data_model_interface.get_number_of_keys()
    keys = {}
    for leg in LEGS:
        keys.update(_leg_keys(clip, *leg, n, spread))
    ctl = clip.controller
    ctl.open_bracket(unreal.Text("Legs in toward the body"), False)
    for bone, (locs, rots, scales) in keys.items():
        if not ctl.set_bone_track_keys(bone, locs, rots, scales, False):
            raise RuntimeError(f"could not key {bone} on {clip.get_name()}")
    ctl.close_bracket(False)


def spread_cm(clip, n=8):
    """The feet's and the knees' mean distance apart across the body (cm)."""
    last = clip.data_model_interface.get_number_of_keys() - 1
    frames = sorted({round(last * i / n) for i in range(n + 1)})
    feet = sum(abs(_comp(clip, "foot_l", f).translation.x - _comp(clip, "foot_r", f).translation.x)
               for f in frames) / len(frames)
    knees = sum(abs(_comp(clip, "calf_l", f).translation.x - _comp(clip, "calf_r", f).translation.x)
                for f in frames) / len(frames)
    return feet, knees
