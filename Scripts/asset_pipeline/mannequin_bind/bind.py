"""bind -- one cached Meshy body, bound to the mannequin's skeleton.

Host-side, start to finish: no editor.

    read      the rigged GLB (body.py) and the mannequin's reference skeleton
              out of its .uasset (ref_skeleton.py)
    repose    the limbs turned onto the mannequin's lines (repose.py)
    fit       the mannequin's skeleton sized to the body (fit.py)
    fingers   found in the mesh and curled like the mannequin's
              (finger_fit.py), or the mannequin's layout if they cannot be
    weights   Meshy's 24 bones re-addressed to the mannequin's (weights.py)
    write     the same GLB on the new skeleton (glb.py), with a report

The result imports straight onto SK_Mannequin (import_bound.py): the
mannequin's anim blueprint and every clip keyed for it then play on the body
as they are, with no IK rig, no retargeter and no retargeted copies.
"""

import os
from dataclasses import dataclass, field

from asset_pipeline.mannequin_bind import (
    finger_fit, fingers, fit, glb, hand_frame, lbs,
    ref_skeleton, repose, space, weights)
from asset_pipeline.mannequin_bind.bone_map import FINGER_JOINTS, HANDS, finger_bone
from asset_pipeline.mannequin_bind.xform import EYE


@dataclass
class Bound:
    """A body on the mannequin's skeleton, in Unreal's space."""

    spec_id: str
    skeleton: ref_skeleton.RefSkeleton
    verts: list
    normals: list
    tangents: list
    weights: list                # per vertex {mannequin bone: weight}
    report: dict = field(default_factory=dict)


def _hand_scales(mann, pose, verts):
    out = {}
    for bone, s in HANDS.items():
        finger, _palm = hand_frame.mannequin_frame(mann, s)
        out[s] = fit.hand_scale(mann, s, pose.joints[bone], finger,
                                [verts[i] for i in pose.hands[s]["ids"]])
    return out


def _digits(body, verts, skeleton, notes):
    """Per hand: where its finger bones lie, and whether they were found in
    the mesh (True) or are the mannequin's layout (False)."""
    out, found = {}, {}
    for bone, s in sorted(HANDS.items()):
        ids = body.held_by(bone)
        wrist, axes = fingers.hand_axes(skeleton, s)
        flat = {i: fingers.flat(verts[i], wrist, axes) for i in ids}
        thumb = fingers.flat(skeleton.pos(finger_bone("thumb", 2, s)), wrist, axes)
        try:
            digits = finger_fit.find(flat, body.triangles, 1.0 if thumb[1] > 0 else -1.0)
            out[s] = finger_fit.chains(
                digits, skeleton, s, lambda p: fingers.unflat(p, wrist, axes))
            found[s] = True
        except finger_fit.NotFound as why:
            out[s] = fingers.fan(skeleton, s, [verts[i] for i in ids])
            found[s] = False
            notes.append(
                f"hand_{s}: fingers not found in the mesh ({why}); weighted by "
                "the mannequin's layout and left uncurled -- a fist will "
                "close short on this hand")
    return out, found


def _with_fingers(skeleton, placed):
    """``skeleton`` with its finger joints moved to ``placed``
    ({suffix: {finger: [joint 1, 2, 3, tip]}})."""
    at = {n: skeleton.pos(n) for n in skeleton.names}
    for s, by_finger in placed.items():
        for finger, points in by_finger.items():
            for j, p in zip(FINGER_JOINTS, points):
                at[finger_bone(finger, j, s)] = p
    return ref_skeleton.from_component(
        skeleton.names, skeleton.parents, skeleton.comp_q,
        [at[n] for n in skeleton.names])


def bind_body(body, mann):
    """The whole bind, in memory."""
    pose = repose.solve(body, mann)
    notes = list(pose.notes)
    verts, normals, tangents = repose.apply(body, pose)

    # Feet on the ground: the legs were turned a few degrees.
    lift = -min(v[2] for v in verts)
    verts = [(v[0], v[1], v[2] + lift) for v in verts]
    joints = {b: (p[0], p[1], p[2] + lift) for b, p in pose.joints.items()}
    pose_on_ground = repose.Repose(rot=pose.rot, joints=joints, hands=pose.hands)

    hand_scales = _hand_scales(mann, pose_on_ground, verts)
    skeleton, info = fit.fit(mann, joints, hand_scales)
    stature = max(v[2] for v in verts)

    digits, found = _digits(body, verts, skeleton, notes)
    # Every share is kept for the curl; the four largest are taken after it.
    full = weights.remap(body.weights, verts, skeleton, stature, digits, limit=64)

    moves = {n: (EYE, (0.0, 0.0, 0.0)) for n in skeleton.names}
    placed = {}
    for s, was_found in found.items():
        if not was_found:
            continue
        turned, placed[s] = finger_fit.curl(digits[s], mann, s)
        moves.update(turned)
    if placed:
        verts = lbs.points(verts, full, moves)
        normals = lbs.directions(normals, full, moves)
        tangents = lbs.directions(tangents, full, moves)
        skeleton = _with_fingers(skeleton, placed)

    report = {
        "spec": body.spec_id,
        "bones": len(skeleton.names),
        "vertices": len(verts),
        "turned_deg": {b: round(a, 1) for b, a in sorted(pose.turned.items())},
        "forearm_roll_deg": {b: round(a, 1) for b, (_ax, a) in sorted(pose.twists.items())},
        "wrist_bend_deg": {s: round(h["bend_deg"], 1) for s, h in sorted(pose.hands.items())},
        "limb_length_vs_mannequin": {b: round(r, 3) for b, r in sorted(info["limb_ratio"].items())},
        "hand_scale": {s: round(r, 3) for s, r in sorted(hand_scales.items())},
        "fingers_found": dict(sorted(found.items())),
        "lifted_cm": round(lift, 2),
        "notes": notes,
    }
    return Bound(spec_id=body.spec_id, skeleton=skeleton, verts=verts,
                 normals=normals, tangents=tangents,
                 weights=[weights.prune(w) for w in full], report=report)


def write(body, bound, out_path):
    """The bound body as a GLB beside its report; returns the file's size."""
    sk = bound.skeleton
    index = {n: i for i, n in enumerate(sk.names)}
    inverse_bind = []
    for q, t in zip(sk.comp_q, sk.comp_t):
        rot, at = space.rigid_to_gltf(q, t)
        inv = tuple(tuple(rot[j][i] for j in range(3)) for i in range(3))
        back = tuple(-sum(inv[i][k] * at[k] for k in range(3)) for i in range(3))
        inverse_bind.append((inv, back))
    prims = []
    for start, end in body.slices:
        prims.append((
            [space.point_to_gltf(v) for v in bound.verts[start:end]],
            [space.dir_swap(n) for n in bound.normals[start:end]],
            [space.tangent_swap(t) for t in bound.tangents[start:end]],
            [sorted(((index[b], w) for b, w in w.items()), key=lambda jw: -jw[1])
             for w in bound.weights[start:end]]))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    return glb.write_bound(
        body.mesh, out_path, sk.names, sk.parents,
        [space.quat_swap(q) for q in sk.local_q],
        [space.point_to_gltf(t) for t in sk.local_t],
        inverse_bind, prims, mesh_name=f"SKM_{bound.spec_id}")
