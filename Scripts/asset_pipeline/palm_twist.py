"""palm_twist -- the hand frame measured from skinned geometry, and the palm
roll correction build_retarget.py calibrates with it.

finger_rig.py reuses hand_frame() to lay finger bones out in the same frame the
retargeter aligns, which is what makes a transferred thumb land on the thumb.
"""

import math

import unreal

from asset_pipeline.retarget_paths import MANNEQUIN_MESH
from asset_pipeline.rig_util import _bone_xf, _load, _log, mesh_ref_pose


# ─── Palms ──────────────────────────────────────────────────────────────────
#
# CHAIN_TO_CHAIN alignment matches each chain's DIRECTION and says nothing
# about roll around it, so the arms came out pointing correctly with the hands
# rolled -- the monsters ran with their palms up.
#
# The roll cannot be read off the skeletons.  Epic runs X down the bone and
# Mixamo runs Y, so the bone axes sit ~90 degrees apart everywhere and comparing
# them measures the convention, not the pose; and Meshy's LeftHand is a LEAF
# with no finger children, so there is no second bone to define a hand plane
# from.  Palm orientation exists only in the skinned geometry.
#
# So it is measured there: take the vertices whose dominant weight is the hand
# (plus its descendants, because the mannequin has 15 finger bones under hand_l
# while Meshy's hand is one bone), and fit a frame to the cloud.
#
#   finger direction  wrist -> cloud centroid.  Unambiguous.
#   palm normal       the least-variance PCA axis.  A hand is a flat slab, so
#                     this is well conditioned (mannequin eigenvalues
#                     26.6/10.7/3.2, zombie 25.0/17.9/2.9).
#
# PCA gives no sign, and the sign is the whole answer, so it comes from the
# cloud's SKEW along that axis: a hand is not symmetric about its own plane --
# the fingers curl toward the palm -- so the third moment has a consistent sign.
# It measures +0.084/-0.084 on the mannequin's two hands (exactly antisymmetric,
# which is the check that it is real and not noise) and +0.418/-0.564 on the
# zombie's.  Signing both rigs by the same geometric rule is what makes their
# palm normals comparable at all.
#
# Measured residual twist after chain alignment, about the finger axis:
#
#     Zombie01   L -70.9   R +62.0
#     Wendigo01  L -87.8   R +90.7
#
# Mirror-consistent on both creatures, and ~90 degrees, which is the known
# difference between a Mixamo A-pose and Epic's.

HAND_PAIRS = (("hand_l", "LeftHand"), ("hand_r", "RightHand"))

# The clip the palm roll is calibrated against, and how close is close enough.
# An idle is the right choice: the hands are at rest, so what is measured is the
# retarget pose's own error and not a pose the animator put there.
PALM_CALIBRATION_CLIP = "MM_Idle"
PALM_TOLERANCE_DEG = 15.0


def _descendants(mesh, root):
    """``root`` plus every bone beneath it, and the mesh's own bone order.

    The order matters and is not the order AnimPoseExtensions reports: skin
    weight bone indices are into the MESH's reference skeleton, and indexing one
    with the other silently attributes vertices to the wrong bone -- it put 974
    units of variance in the mannequin's "hand", which is an arm.
    """
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, -1000000))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skeletal_mesh_asset(mesh)
        order = [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
        family = set()
        for n in order:
            cur, depth = n, 0
            while cur and cur != "None" and depth < 64:
                if cur == root:
                    family.add(n)
                    break
                cur = str(comp.get_parent_bone(cur))
                depth += 1
        return family, order
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def _unit(x, y, z):
    m = math.sqrt(x * x + y * y + z * z) or 1.0
    return unreal.Vector(x / m, y / m, z / m)


def _eig3(m):
    """Eigenvectors of a symmetric 3x3 by Jacobi rotation, descending."""
    a = [row[:] for row in m]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(64):
        p, q, best = 0, 1, 0.0
        for i in range(3):
            for j in range(i + 1, 3):
                if abs(a[i][j]) > best:
                    best, p, q = abs(a[i][j]), i, j
        if best < 1e-12:
            break
        theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, sn = math.cos(theta), math.sin(theta)
        for k in range(3):
            a[k][p], a[k][q] = c * a[k][p] - sn * a[k][q], sn * a[k][p] + c * a[k][q]
        for k in range(3):
            a[p][k], a[q][k] = c * a[p][k] - sn * a[q][k], sn * a[p][k] + c * a[q][k]
        for k in range(3):
            v[k][p], v[k][q] = c * v[k][p] - sn * v[k][q], sn * v[k][p] + c * v[k][q]
    out = [(a[i][i], (v[0][i], v[1][i], v[2][i])) for i in range(3)]
    out.sort(key=lambda t: -t[0])
    return out


def hand_frame(mesh, bone):
    """(finger direction, palm normal) for one hand, in component space."""
    family, order = _descendants(mesh, bone)
    # The mesh's rest, not the skeleton's: the cloud below is the mesh's, and
    # on the mannequin the two wrists are 2.8 cm apart (see mesh_ref_pose).
    wrist = mesh_ref_pose(mesh)[bone][0].translation

    dm = unreal.DynamicMesh()
    dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
        mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    pts = []
    for i in range(dm.get_vertex_count()):
        _d, w, ok = dm.get_vertex_bone_weights(i)
        if not ok or not w:
            continue
        top = max(w, key=lambda x: x.get_editor_property("weight"))
        if order[top.get_editor_property("bone_index")] not in family:
            continue
        pt, _ = dm.get_vertex_position(i)
        pts.append((pt.x, pt.y, pt.z))
    if len(pts) < 32:
        raise RuntimeError(f"{mesh.get_name()}/{bone}: only {len(pts)} skinned "
                           "vertices -- cannot fit a palm frame")

    n = len(pts)
    c = [sum(p[i] for p in pts) / n for i in range(3)]
    cov = [[0.0] * 3 for _ in range(3)]
    for p in pts:
        d = [p[i] - c[i] for i in range(3)]
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    for i in range(3):
        for j in range(3):
            cov[i][j] /= n
    ev = _eig3(cov)
    normal = _unit(*ev[2][1])

    s1 = s3 = 0.0
    for p in pts:
        d = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
        proj = d[0] * normal.x + d[1] * normal.y + d[2] * normal.z
        s1 += proj * proj
        s3 += proj ** 3
    sigma = math.sqrt(s1 / n) or 1.0
    if (s3 / n) / (sigma ** 3) < 0:
        normal = unreal.Vector(-normal.x, -normal.y, -normal.z)

    finger = _unit(c[0] - wrist.x, c[1] - wrist.y, c[2] - wrist.z)
    return finger, normal


def _signed_twist(src_finger, src_normal, tgt_finger, tgt_normal):
    """Roll left over once the target's finger axis is turned onto the source's.

    This is the part chain alignment does not fix: turning the finger axis onto
    the source's still leaves the hand free to spin about that axis, and the
    spin is what points the palms at the sky.
    """
    axis = tgt_finger.cross(src_finger)
    d = max(-1.0, min(1.0, tgt_finger.dot(src_finger)))
    if axis.length() > 1e-6:
        turned = _rodrigues(_unit(axis.x, axis.y, axis.z), math.acos(d), tgt_normal)
    else:
        turned = tgt_normal
    a = _reject(turned, src_finger)
    b = _reject(src_normal, src_finger)
    return math.degrees(math.atan2(a.cross(b).dot(src_finger), a.dot(b)))


def _rodrigues(axis, angle, v):
    c, s = math.cos(angle), math.sin(angle)
    cr = axis.cross(v)
    return unreal.Vector(
        v.x * c + cr.x * s + axis.x * axis.dot(v) * (1 - c),
        v.y * c + cr.y * s + axis.y * axis.dot(v) * (1 - c),
        v.z * c + cr.z * s + axis.z * axis.dot(v) * (1 - c))


def _reject(v, axis):
    d = v.dot(axis)
    return _unit(v.x - d * axis.x, v.y - d * axis.y, v.z - d * axis.z)

def measure_clip_palm_twist(src_anim, tgt_anim, tgt_mesh, time=0.0, src_mesh=None):
    """Residual palm roll in an actual retargeted clip, per side, in degrees.

    The reference-pose measurement cannot see the fix: auto-align writes into
    the retargeter's retarget pose, not into the meshes.  This samples what the
    player is shown -- the animated hand -- and is therefore the only honest
    check that the palms came out facing the same way as the mannequin's.

    The hand cloud is rigid to its bone, so the palm frame at time t is the
    reference-pose frame carried by the bone's animated rotation.
    ``src_mesh`` is the source's skin, the mannequin unless given: any rig
    whose hands are named hand_l/hand_r (the Quaternius UAL's are).
    """
    man = src_mesh or _load(MANNEQUIN_MESH)
    out = {}
    for src_bone, tgt_bone in HAND_PAIRS:
        sf0, sn0 = hand_frame(man, src_bone)
        tf0, tn0 = hand_frame(tgt_mesh, tgt_bone)

        sr = _bone_xf(src_anim, src_bone, time).rotation
        s_ref = mesh_ref_pose(man)[src_bone][0].rotation
        tr = _bone_xf(tgt_anim, tgt_bone, time).rotation
        t_ref = mesh_ref_pose(tgt_mesh)[tgt_bone][0].rotation

        def carry(cur, ref, v):
            return cur.rotate_vector(ref.inversed().rotate_vector(v))

        out[tgt_bone] = _signed_twist(
            carry(sr, s_ref, sf0), carry(sr, s_ref, sn0),
            carry(tr, t_ref, tf0), carry(tr, t_ref, tn0))
    return out


def measure_palm_twist(target_mesh):
    """Residual palm roll per side, target vs the mannequin, in degrees."""
    man = _load(MANNEQUIN_MESH)
    out = {}
    for src_bone, tgt_bone in HAND_PAIRS:
        sf, sn = hand_frame(man, src_bone)
        tf, tn = hand_frame(target_mesh, tgt_bone)
        out[tgt_bone] = _signed_twist(sf, sn, tf, tn)
    return out


def measure_clip_hand_turn(src_anim, tgt_anim, tgt_mesh, time=0.0, src_mesh=None):
    """The whole turn from the target hand's frame onto the mannequin's, in a
    retargeted clip: {hand: (axis in the hand bone's local space, degrees)}.

    The palm roll is one component of this.  The fingers need the rest: the
    retargeter hands a finger its source's WORLD-space delta, so a finger curls
    about the mannequin's knuckle axis, and that is this hand's knuckle axis
    only once the hands agree about pitch and yaw as well as roll.  Chain
    alignment leaves the wrist bend between them, and on the adventurer that
    moved the idle's fingers 27 degrees where the mannequin's move 7.

    The axis is taken into the hand's local space through its rotation at the
    same instant, which is where a retarget-pose offset rotates it.
    ``src_mesh`` as in measure_clip_palm_twist.
    """
    man = src_mesh or _load(MANNEQUIN_MESH)
    out = {}
    for src_bone, tgt_bone in HAND_PAIRS:
        frames = []
        for mesh, anim, bone in ((man, src_anim, src_bone),
                                 (tgt_mesh, tgt_anim, tgt_bone)):
            f0, n0 = hand_frame(mesh, bone)
            cur = _bone_xf(anim, bone, time).rotation
            ref = mesh_ref_pose(mesh)[bone][0].rotation
            f = cur.rotate_vector(ref.inversed().rotate_vector(f0))
            n = cur.rotate_vector(ref.inversed().rotate_vector(n0))
            frames.append((unreal.MathLibrary.make_rot_from_xz(f, n).quaternion(),
                           cur))
        (qs, _), (qt, cur_t) = frames
        turn = qs.multiply(qt.inversed())
        deg = math.degrees(turn.get_angle())
        if deg > 180.0:
            deg -= 360.0
        axis = cur_t.inversed().rotate_vector(turn.get_rotation_axis())
        out[tgt_bone] = ((axis.x, axis.y, axis.z), deg)
    return out


# The local axis the roll is applied about.
PALM_TWIST_AXIS_LOCAL = (0.0, 1.0, 0.0)   # Mixamo runs Y down the bone


def _quat_axis_angle(axis, degrees):
    half = math.radians(degrees) * 0.5
    sn = math.sin(half)
    a = _unit(*axis)
    return unreal.Quat(a.x * sn, a.y * sn, a.z * sn, math.cos(half))


def _apply_palm_twist(ctl, name, angles):
    """Roll each hand in the target retarget pose so the palms face right.

    Chain alignment fixes the direction a chain points and says nothing about
    the spin around it, so the hands arrive rolled -- the monsters ran with
    their palms up, measured at 75-95 degrees off the mannequin.

    The offsets are LOCAL-space deltas and which way round they compose is not
    something to guess at, so the angle is not derived analytically, it is
    CALIBRATED: retarget once, measure the roll in the resulting clip, apply
    the negative of it, retarget again.  A trial of +45 degrees moved the
    measured roll by +43 to +48 on every hand of both creatures, so the
    response is essentially one-for-one -- but nothing here depends on that
    being exactly true, only on it being monotonic, and the second measurement
    checks the result rather than assuming it.

    Being a measurement rather than a constant is what makes it work for the
    next creature without anyone opening the retargeter.
    """
    pose = ctl.get_current_retarget_pose(unreal.RetargetSourceOrTarget.TARGET)
    existing = dict(pose.get_editor_property("bone_rotation_offsets"))
    for _src, bone in HAND_PAIRS:
        # A bare angle is a roll about the bone; (axis, angle) is a whole turn
        # from measure_clip_hand_turn.
        want = angles.get(bone)
        if want is None:
            continue
        axis, deg = want if isinstance(want, tuple) else (PALM_TWIST_AXIS_LOCAL, want)
        if not deg:
            continue
        q = _quat_axis_angle(axis, deg)
        prior = existing.get(unreal.Name(bone))
        combined = prior.multiply(q) if prior else q
        ctl.set_rotation_offset_for_retarget_pose_bone(
            unreal.Name(bone), combined, unreal.RetargetSourceOrTarget.TARGET)
        _log(f"  {bone} turned {deg:+.1f} deg about local "
             f"({axis[0]:+.2f}, {axis[1]:+.2f}, {axis[2]:+.2f})")
