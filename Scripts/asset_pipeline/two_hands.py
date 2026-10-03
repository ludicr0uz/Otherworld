"""two_hands.py -- the two-handed ready poses keep the source's hands together.

The retargeter copies each arm's rotations, and where the hands end up is then
a matter of the target's arm lengths and shoulders. On a rig built like the
mannequin's that is near enough: SKM_Adventurer01's hands in the rifle and
pistol ready poses sat within 1.5 cm of the mannequin's spacing. On
SKM_Adventurer02 (shorter upper arms, the shoulders set back) the left hand
came out 10-17 cm off the right -- off the handguard, and 29 cm from a pistol
held in both hands -- and down the sights the support hand's IK holds it
exactly there (combat/support_hand.py reads its point off these clips).

So after the retarget, on every frame of each AIM_SOURCES clip, the left wrist
is put where the source puts it relative to the right wrist, in component
space, by a two-bone turn of the upper arm and the forearm in the plane the
elbow already bends in. The hands' component rotations are the source's
already (the palm calibration in build_retarget.py measures that), so the
offset carries over unchanged. A clip already within KEEP_CM is left alone, so
the rigs that retargeted well keep theirs exactly.
"""

import math
import os

import unreal

from asset_pipeline.quat_math import (
    add, between, conj, dot, length, mul, norm, scale, sub, turn,
)
from asset_pipeline.retarget_paths import AIM_SOURCES
from asset_pipeline.rig_util import _log

SOURCE_HANDS = ("hand_l", "hand_r")
TARGET_ARM = ("LeftArm", "LeftForeArm", "LeftHand")
TARGET_RIGHT = "RightHand"
KEEP_CM = 3.0


def _comp(anim, bone, frame):
    """(location, quat) of ``bone`` in component space at ``frame``."""
    xf = unreal.Transform()
    for b in unreal.AnimationLibrary.find_bone_path_to_root(anim, bone):
        xf = xf.multiply(unreal.AnimationLibrary.get_bone_pose_for_frame(
            anim, b, frame, False))
    r = xf.rotation
    return xf.translation.to_tuple(), (r.x, r.y, r.z, r.w)


def reach(shoulder, elbow, wrist, target):
    """(new upper-arm swing, new forearm swing): component-space turns that
    put ``wrist`` on ``target`` with the elbow in the plane it bends in now.
    Pure."""
    a, b = length(sub(elbow, shoulder)), length(sub(wrist, elbow))
    to = sub(target, shoulder)
    d = min(length(to), a + b - 1e-3)
    u = norm(to)
    bend = sub(elbow, shoulder)
    v = sub(bend, scale(u, dot(bend, u)))
    v = norm(v) if length(v) > 1e-6 else norm(sub(elbow, wrist))
    cos_a = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2.0 * a * d)))
    elbow2 = add(shoulder, add(scale(u, a * cos_a), scale(v, a * math.sqrt(1.0 - cos_a ** 2))))
    upper = between(norm(sub(elbow, shoulder)), norm(sub(elbow2, shoulder)))
    fore_now = turn(upper, sub(wrist, elbow))
    wrist2 = add(shoulder, scale(u, d))
    fore = between(norm(fore_now), norm(sub(wrist2, elbow2)))
    return upper, fore


def _fix_clip(source, target):
    n = target.data_model_interface.get_number_of_keys()
    upper_b, fore_b, hand_b = TARGET_ARM
    parent = str(unreal.AnimationLibrary.find_bone_path_to_root(target, upper_b)[1])
    keys = {b: ([], [], []) for b in TARGET_ARM}
    worst = 0.0
    for f in range(n):
        sl, sr = (_comp(source, b, f)[0] for b in SOURCE_HANDS)
        tr = _comp(target, TARGET_RIGHT, f)[0]
        want = add(tr, sub(sl, sr))
        (s, qs), (e, qe), (w, qw) = (_comp(target, b, f) for b in TARGET_ARM)
        _p, qp = _comp(target, parent, f)
        worst = max(worst, length(sub(w, want)))
        upper, fore = reach(s, e, w, want)
        qs2 = mul(upper, qs)
        qe2 = mul(fore, mul(upper, qe))
        for bone, here, up in ((upper_b, qs2, qp), (fore_b, qe2, qs2), (hand_b, qw, qe2)):
            local = unreal.AnimationLibrary.get_bone_pose_for_frame(target, bone, f, False)
            keys[bone][0].append(local.translation)
            keys[bone][1].append(unreal.Quat(*mul(conj(up), here)))
            keys[bone][2].append(local.scale3d)
    if worst < KEEP_CM:
        return worst, False
    ctl = target.controller
    ctl.open_bracket(unreal.Text("Keep the two hands together"), False)
    for bone, (locs, rots, scales) in keys.items():
        if not ctl.set_bone_track_keys(bone, locs, rots, scales, False):
            raise RuntimeError(f"could not key {bone} on {target.get_name()}")
    ctl.close_bracket(False)
    unreal.EditorAssetLibrary.save_loaded_asset(target, False)
    return worst, True


def keep_two_hands(anim_dir, prefix):
    """Put the left hand back on the right's spacing in each two-handed ready
    pose under ``anim_dir``; returns {clip: cm it was off}."""
    out = {}
    for src_path in AIM_SOURCES:
        stem = os.path.basename(src_path)
        source = unreal.EditorAssetLibrary.load_asset(src_path)
        target = unreal.EditorAssetLibrary.load_asset(f"{anim_dir}/{prefix}{stem}")
        if not source or not target:
            continue
        worst, fixed = _fix_clip(source, target)
        out[stem] = worst
        _log(f"  {prefix}{stem}: left hand {worst:.1f} cm off the source's spacing"
             + (" -- put back" if fixed else ""))
    return out
