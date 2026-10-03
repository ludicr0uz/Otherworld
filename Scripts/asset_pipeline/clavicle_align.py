"""clavicle_align.py -- point a target's clavicles the source's way in the
retarget pose, before the chains are auto-aligned.

The clavicle is a chain of one bone (rig_chains: LeftClavicle runs
LeftShoulder to LeftShoulder), and CHAIN_TO_CHAIN auto-alignment draws a
chain's direction from its bones, so a one-bone chain is never turned. Every
rig before SKM_Adventurer02 had its clavicles out to the side within about 20
degrees of the mannequin's, and it did not matter. The adventurer in boxers
was generated with its arms hanging back: its clavicle runs 38 degrees behind
the mannequin's, and the retargeter copies that offset into every clip. The
shoulder joint rode 13 cm behind the spine, the arm chains (aligned from
there) put the hands somewhere else, and in the two-handed ready poses the
left hand came off the gun.

So a clavicle more than ALIGN_OVER_DEG off its source's is turned onto the
source's line to the upper arm, in component space, and that side's arm chain
is aligned again from where the shoulder now is. After auto_align_all_bones,
which clears an offset on a one-bone chain (measured: None after it). Under
the threshold nothing is written, so the rigs that retargeted well keep their
clips exactly.

The offset is a LOCAL delta applied after the reference rotation (local *
offset), so the component-space swing D becomes C^-1 * D * C; palm_twist.py
says why such composition is measured, and retarget_verify's clips are what
measure it.
"""

import math

import unreal

from asset_pipeline.quat_math import between, conj, mul, norm
from asset_pipeline.rig_util import _log, mesh_ref_pose

CLAVICLE_CHAINS = (("LeftClavicle", "LeftArm"), ("RightClavicle", "RightArm"))
ALIGN_OVER_DEG = 30.0


def _q(t):
    r = t.rotation
    return (r.x, r.y, r.z, r.w)


def _line(ref, bone, child):
    a, b = ref[bone][0].translation, ref[child][0].translation
    return norm((b.x - a.x, b.y - a.y, b.z - a.z))


def _chain_bones(rig, clavicle, arm):
    ctl = unreal.IKRigController.get_controller(rig)
    return (str(ctl.get_retarget_chain_start_bone(clavicle)),
            str(ctl.get_retarget_chain_start_bone(arm)))


def align_clavicles(ctl, source_rig, target_rig, name):
    """Write a TARGET retarget-pose offset for each clavicle that runs more
    than ALIGN_OVER_DEG off the source's; returns {bone: degrees turned}."""
    src_mesh = unreal.IKRigController.get_controller(source_rig).get_skeletal_mesh()
    tgt_mesh = unreal.IKRigController.get_controller(target_rig).get_skeletal_mesh()
    if not src_mesh or not tgt_mesh:
        return {}
    src_ref, tgt_ref = mesh_ref_pose(src_mesh), mesh_ref_pose(tgt_mesh)
    turned = {}
    for clavicle, arm in CLAVICLE_CHAINS:
        s_bone, s_child = _chain_bones(source_rig, clavicle, arm)
        t_bone, t_child = _chain_bones(target_rig, clavicle, arm)
        if not all(b in r for b, r in ((s_bone, src_ref), (s_child, src_ref),
                                       (t_bone, tgt_ref), (t_child, tgt_ref))):
            continue
        want, have = _line(src_ref, s_bone, s_child), _line(tgt_ref, t_bone, t_child)
        deg = math.degrees(math.acos(max(-1.0, min(1.0, sum(
            p * q for p, q in zip(want, have))))))
        if deg <= ALIGN_OVER_DEG:
            continue
        comp = _q(tgt_ref[t_bone][0])
        offset = mul(mul(conj(comp), between(have, want)), comp)
        ctl.set_rotation_offset_for_retarget_pose_bone(
            unreal.Name(t_bone), unreal.Quat(*offset),
            unreal.RetargetSourceOrTarget.TARGET)
        turned[t_bone] = deg
        _log(f"{name}: {t_bone} turned {deg:.1f} deg onto the source's clavicle")
        ctl.auto_align_bones([unreal.Name(b) for b in _chain(target_rig, arm, tgt_ref)],
                             unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN,
                             unreal.RetargetSourceOrTarget.TARGET)
    return turned


def _chain(rig, chain, ref):
    """The bones of one retarget chain, start to end, off ``ref``'s parents."""
    ctl = unreal.IKRigController.get_controller(rig)
    start = str(ctl.get_retarget_chain_start_bone(chain))
    out = [str(ctl.get_retarget_chain_end_bone(chain))]
    while out[-1] != start and ref[out[-1]][1]:
        out.append(ref[out[-1]][1])
    return out[::-1]
