"""finger_verify -- verify_fingers(): are a creature's fingers skinned, mapped
in its retargeter, and actually posed by the retargeted clips?

Mirrors finger_rig.py.  Each of the three is a separate way for the hands to
stay flat with nothing in the log: a bone no vertex follows moves nothing, an
unmapped chain keeps its retarget pose, and a mapped chain whose retarget pose
is wrong curls the fingers somewhere other than where the mannequin's go.
"""

import math

import unreal

from asset_pipeline.finger_rig import _skinned
from asset_pipeline.palm_twist import hand_frame
from asset_pipeline.retarget_paths import (
    MANNEQUIN_MESH, anim_dir, anim_prefix, retargeter_path,
)
from asset_pipeline.rig_chains import (
    FINGER_JOINTS, FINGERS, HANDS, mannequin_finger_bone, meshy_finger_bone,
    meshy_finger_bones,
)
from asset_pipeline.rig_util import _load, _log, mesh_ref_pose, visible_bone_xf

# The clips whose hands are compared against the mannequin's.  The idle has a
# relaxed hand; the two ready poses grip a weapon, which is the pose a flat
# hand ruins.  Paths are the mannequin's; the creature's copy is derived.
FINGER_CLIPS = (
    "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle",
    "/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS",
    "/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS",
)
# How far a retargeted finger's curl may sit from the mannequin's, in degrees.
CURL_TOLERANCE_DEG = 25.0
# A finger bone needs at least this many vertices it moves by at least
# MIN_WEIGHT, or it is a bone with nothing on it.
MIN_SKINNED_VERTS = 8
MIN_WEIGHT = 0.25


def _angle(u, v):
    lu, lv = u.length(), v.length()
    if lu < 1e-6 or lv < 1e-6:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, u.dot(v) / (lu * lv)))))


def _curl(pos, finger_axis, joints):
    """Knuckle bend plus middle-joint bend, degrees; 0 is a straight finger.

    The knuckle is measured off the palm's finger axis, not off the line from
    the wrist joint to the knuckle: that line depends on where a stretched
    layout put the knuckle, which says nothing about where the finger points.
    """
    a, b, c = (pos(x) for x in joints)
    return _angle(finger_axis, b - a) + _angle(b - a, c - b)


def _axis_in(mesh, hand, ref):
    """The hand's finger axis, as a function of the hand bone's rotation.

    Measured once in the mesh's rest pose (palm_twist.hand_frame), then carried
    rigidly by however the hand bone is turned -- the same carry
    measure_clip_palm_twist uses.
    """
    f, _p = hand_frame(mesh, hand)
    local = ref[hand][0].rotation.inversed().rotate_vector(f)
    return lambda rot: rot.rotate_vector(local)


def _fingers():
    """(label, mannequin hand, mannequin joints, Meshy hand, Meshy joints)."""
    for suffix, side, man_hand, hand in HANDS:
        for f in FINGERS:
            yield (f"{side}{f}", man_hand,
                   [mannequin_finger_bone(f, j, suffix)
                    for j in range(1, FINGER_JOINTS + 1)],
                   hand,
                   [meshy_finger_bone(f, j, side)
                    for j in range(1, FINGER_JOINTS + 1)])


def _check_skin(mesh):
    counts = {b: 0 for b in meshy_finger_bones()}
    _order, verts = _skinned(mesh)
    for _i, _pt, w in verts:
        for b, x in w.items():
            if b in counts and x >= MIN_WEIGHT:
                counts[b] += 1
    thin = {b: n for b, n in counts.items() if n < MIN_SKINNED_VERTS}
    _log(f"  finger skin: {min(counts.values())}-{max(counts.values())} "
         f"vertices per bone")
    return [f"{b} moves only {n} vertices" for b, n in sorted(thin.items())]


def _check_mapping(name):
    ctl = unreal.IKRetargeterController.get_controller(_load(retargeter_path(name)))
    bad = []
    for label, *_rest in _fingers():
        src = str(ctl.get_source_chain(label))
        if src != label:
            bad.append(f"retargeter maps {label} from {src!r}")
    return bad


def _check_curl(name, mesh):
    """Each finger's curl in each clip, against the mannequin's in the source.

    Both clips are read as they are SHOWN on their meshes (visible_bone_xf),
    and both bind poses are the meshes' own: sampled raw against the
    skeleton's rest, the mannequin's idle fingers read 15 degrees off what the
    retargeter -- and the player -- actually sees.
    """
    man = _load(MANNEQUIN_MESH)
    man_ref, ref = mesh_ref_pose(man), mesh_ref_pose(mesh)
    axes = {h: (_axis_in(man, mh, man_ref), _axis_in(mesh, h, ref))
            for _s, _side, mh, h in HANDS}

    def pos(xf_of):
        return lambda bone: xf_of(bone).translation

    man_bind = pos(lambda b: man_ref[b][0])
    bind = pos(lambda b: ref[b][0])
    bad = []
    for clip in FINGER_CLIPS:
        short = clip.rsplit("/", 1)[1]
        src_xf = visible_bone_xf(_load(clip), man, man_ref)
        tgt_xf = visible_bone_xf(
            _load(f"{anim_dir(name)}/{anim_prefix(name)}{short}"), mesh, ref)
        src, tgt = pos(src_xf), pos(tgt_xf)
        errs, moved_src, moved_tgt = [], 0.0, 0.0
        for label, man_hand, man_joints, hand, joints in _fingers():
            man_axis, axis = axes[hand]
            s = _curl(src, man_axis(src_xf(man_hand).rotation), man_joints)
            t = _curl(tgt, axis(tgt_xf(hand).rotation), joints)
            s0 = _curl(man_bind, man_axis(man_ref[man_hand][0].rotation), man_joints)
            t0 = _curl(bind, axis(ref[hand][0].rotation), joints)
            moved_src += abs(s - s0)
            moved_tgt += abs(t - t0)
            errs.append(abs(t - s))
            if abs(t - s) > CURL_TOLERANCE_DEG:
                bad.append(f"{short} {label}: curl {t:.0f} deg, mannequin {s:.0f}")
        n = len(errs)
        _log(f"  {short}: finger curl within {max(errs):.0f} deg of the "
             f"mannequin (mean {sum(errs) / n:.0f}); off bind pose by "
             f"{moved_tgt / n:.0f} deg per finger (mannequin {moved_src / n:.0f})")
        # The bind-pose test proper: where the mannequin's hand moves off its
        # own bind pose, this one has to move off its bind pose too.
        if moved_src / n > 10.0 and moved_tgt < 0.5 * moved_src:
            bad.append(f"{short}: fingers stay near the bind pose "
                       f"({moved_tgt / n:.0f} deg vs mannequin {moved_src / n:.0f})")
    return bad


def verify_fingers(name, mesh):
    """Raise unless the creature's hands are skinned, mapped and posed."""
    bad = _check_skin(mesh) + _check_mapping(name) + _check_curl(name, mesh)
    for why in bad:
        _log(f"  FAIL {why}")
    if bad:
        raise RuntimeError(f"{name}: {len(bad)} finger problems")
    _log(f"  {name}: {len(meshy_finger_bones())} finger bones skinned, "
         f"{len(list(_fingers()))} chains mapped, clips curl like the mannequin")
