"""Key a retargeted clip's IK foot bones onto its feet.

The retargeters move the chains (rig_chains.py) and leave the skeleton's IK
bones in the reference pose: ik_foot_l and ik_foot_r stay under a standing
body's hips whatever the legs do. Nothing reads them while a clip plays on
the arms and the spine, but the motion-matching graph's Foot Placement and
Leg IK come after the weapon layers and pull each foot to its IK bone, so a
body lying down had its legs folded under it (P1: the prone clips). A clip
that poses the legs is keyed here after the retarget, each IK bone onto the
foot it stands for, frame by frame. Run inside the editor (import_fal.py).
"""
import unreal

AL = unreal.AnimationLibrary
# IK bone -> the bone it follows.
IK_FEET = {"ik_foot_l": "foot_l", "ik_foot_r": "foot_r"}


def _comp(clip, bone, frame):
    """Component-space transform of ``bone`` at ``frame``."""
    xf = unreal.Transform()
    for b in AL.find_bone_path_to_root(clip, bone):
        xf = xf.multiply(AL.get_bone_pose_for_frame(clip, b, frame, False))
    return xf


def off_cm(clip, n=8):
    """The furthest an IK foot bone is from its foot over ``clip`` (cm)."""
    last = clip.data_model_interface.get_number_of_keys() - 1
    return max((_comp(clip, ik, f).translation - _comp(clip, fk, f).translation).length()
               for ik, fk in IK_FEET.items()
               for f in sorted({round(last * i / n) for i in range(n + 1)}))


def follow_feet(clip):
    """Key each IK foot bone of ``clip`` onto its foot, and save the clip."""
    n = clip.data_model_interface.get_number_of_keys()
    keys = {}
    for ik, fk in IK_FEET.items():
        parent = str(AL.find_bone_path_to_root(clip, ik)[1])
        locs, rots, scales = [], [], []
        for f in range(n):
            local = _comp(clip, fk, f).multiply(_comp(clip, parent, f).inverse())
            locs.append(local.translation)
            rots.append(local.rotation)
            scales.append(unreal.Vector(1.0, 1.0, 1.0))
        keys[ik] = (locs, rots, scales)
    ctl = clip.controller
    ctl.open_bracket(unreal.Text("IK feet follow the feet"), False)
    for ik, (locs, rots, scales) in keys.items():
        ctl.add_bone_curve(ik, False)   # False when the track is already there
        if not ctl.set_bone_track_keys(ik, locs, rots, scales, False):
            raise RuntimeError(f"could not key {ik} on {clip.get_name()}")
    ctl.close_bracket(False)
    unreal.EditorAssetLibrary.save_loaded_asset(clip, False)
