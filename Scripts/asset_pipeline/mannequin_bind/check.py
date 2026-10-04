"""check -- what can be proved about a bound body without an editor.

Two kinds of thing.  FAILURES are properties the bind must have, read back
out of the file it wrote: if one is false the body is wrong, whatever it looks
like.  MEASURES are numbers to look at: how far the repose stretched the
mesh, and how much of a lifted clavicle the side of the ribcage follows
before the bind and after it (weights.py's CLAVICLE: the fault this pipeline
was written after).

    the file reads back        skinned through its own joints, every vertex
                               rests where the bind put it
    the mannequin's rotations  every bone's local rotation is the mannequin's
    the mannequin's lines      each limb segment lies along the mannequin's
    weights                    sum to one, at most four, on bones that exist;
                               every finger bone holds something
    feet                       on the ground

What it cannot say is whether the body LOOKS right in a clip: that is
import_bound.py and a pair of eyes.
"""

from asset_pipeline.mannequin_bind import glb, lbs, space
from asset_pipeline.mannequin_bind.bone_map import LIMBS, SIDES, finger_bones
from asset_pipeline.mannequin_bind.xform import (
    IDENTITY, angle_between, axis_angle, length, sub)

REST_TOLERANCE_CM = 0.01
ROTATION_TOLERANCE = 1e-4        # 1 - |dot| of two unit quaternions
LINE_TOLERANCE_DEG = 0.05
GROUND_TOLERANCE_CM = 0.05
CLAVICLE_LIFT_DEG = 20.0


def _same_rotation(a, b):
    return 1.0 - abs(sum(p * q for p, q in zip(a, b))) < ROTATION_TOLERANCE


def read_back(path, bound):
    """Failures in the written file against the Bound it was written from."""
    fails = []
    mesh = glb.read_skinned(path)
    sk = bound.skeleton
    if mesh.bones != list(sk.names):
        fails.append("the file's joints are not the skeleton's, in order")
        return fails
    for name, parent in zip(sk.names, sk.parents):
        want = sk.names[parent] if parent >= 0 else None
        if mesh.parents[name] != want:
            fails.append(f"{name}: parent {mesh.parents[name]} in the file, {want} bound")
    worst, at = 0.0, 0
    for prim in mesh.primitives:
        for p in prim.positions:
            d = length(sub(space.point_to_ue(p), bound.verts[at]))
            worst = max(worst, d)
            at += 1
    if at != len(bound.verts):
        fails.append(f"{at} vertices in the file, {len(bound.verts)} bound")
    if worst > REST_TOLERANCE_CM:
        fails.append(f"a vertex rests {worst:.3f} cm from where it was bound: "
                     "the inverse bind matrices disagree with the joints")
    for name in sk.names:
        d = length(sub(space.point_to_ue(mesh.joints[name]), sk.pos(name)))
        if d > REST_TOLERANCE_CM:
            fails.append(f"{name}: joint {d:.3f} cm off in the file")
            break
    for i, node in enumerate(mesh.doc["nodes"][:len(sk.names)]):
        if not _same_rotation(space.quat_swap(tuple(node["rotation"])), sk.local_q[i]):
            fails.append(f"{sk.names[i]}: local rotation changed on the way to the file")
            break
    return fails


def structure(bound, mann):
    """Failures in the Bound itself."""
    fails = []
    sk = bound.skeleton
    if sk.names != mann.names or sk.parents != mann.parents:
        fails.append("not the mannequin's bones and parents")
        return fails
    off = [n for i, n in enumerate(sk.names)
           if not _same_rotation(sk.local_q[i], mann.local_q[i])]
    if off:
        fails.append(f"{len(off)} bones do not have the mannequin's reference "
                     f"rotation, first {off[0]}")
    for _b, (_c, bone, child, _upper) in sorted(LIMBS.items()):
        a = angle_between(sub(sk.pos(child), sk.pos(bone)),
                          sub(mann.pos(child), mann.pos(bone)))
        if a > LINE_TOLERANCE_DEG:
            fails.append(f"{bone}: {a:.2f} deg off the mannequin's line")
    known = set(sk.names)
    used = set()
    for i, w in enumerate(bound.weights):
        if not 0 < len(w) <= glb.MAX_INFLUENCES:
            fails.append(f"vertex {i}: {len(w)} influences")
            break
        if abs(sum(w.values()) - 1.0) > 1e-6 or min(w.values()) < 0.0:
            fails.append(f"vertex {i}: weights sum to {sum(w.values()):.6f}")
            break
        if not set(w) <= known:
            fails.append(f"vertex {i}: weighted to {sorted(set(w) - known)}")
            break
        used.update(w)
    idle = [b for s, _side in SIDES for b in finger_bones(s) if b not in used]
    if idle:
        fails.append(f"finger bones holding no vertex: {idle}")
    low = min(v[2] for v in bound.verts)
    if abs(low) > GROUND_TOLERANCE_CM:
        fails.append(f"the lowest vertex is at {low:.2f} cm, not on the ground")
    return fails


def stretch(body, bound):
    """How the repose changed the mesh's edge lengths: {share of edges:
    after/before}.  A repose is a pose, so most edges do not change; the tail
    is the elbows, the wrists and the knuckles."""
    ratios = []
    for a, b, c in body.triangles:
        for i, j in ((a, b), (b, c), (a, c)):
            before = length(sub(body.verts[i], body.verts[j]))
            if before > 1e-4:
                ratios.append(length(sub(bound.verts[i], bound.verts[j])) / before)
    ratios.sort()
    at = lambda share: ratios[int(share * (len(ratios) - 1))]     # noqa: E731
    return {"p01": round(at(0.01), 3), "p50": round(at(0.5), 3),
            "p99": round(at(0.99), 3), "min": round(ratios[0], 3),
            "max": round(ratios[-1], 3)}


def _ribs(body, bound, s, side):
    """Vertex ids on the side of the ribcage under one shoulder: 5-25 cm below
    the joint, inboard of it, and not the arm's."""
    shoulder = bound.skeleton.pos(f"upperarm_{s}")
    middle = bound.skeleton.pos("spine_05")[0]
    out = 1.0 if shoulder[0] > middle else -1.0
    ids = []
    for i, v in enumerate(bound.verts):
        under = shoulder[2] - v[2]
        if not 5.0 < under < 25.0:
            continue
        if (shoulder[0] - v[0]) * out < 2.0 or (v[0] - middle) * out < 5.0:
            continue
        if body.weights[i].get(f"{side}Arm", 0.0) >= 0.5:
            continue
        ids.append(i)
    return ids


def clavicle_lift(body, bound):
    """How far the side of the ribcage moves, in cm on average, when one
    clavicle is lifted CLAVICLE_LIFT_DEG about the body's forward axis --
    on Meshy's rig as generated, and on the bound body."""
    out = {}
    forward = (0.0, 1.0, 0.0)
    for s, side in SIDES:
        ids = _ribs(body, bound, s, side)
        if not ids:
            continue
        up = 1.0 if s == "l" else -1.0
        turn_q = axis_angle(forward, -CLAVICLE_LIFT_DEG * up)

        root = f"{side}Shoulder"
        under = {root}
        for b in body.bones:
            if body.parents[b] in under:
                under.add(b)
        pivot = body.joints[root]
        moves = {b: (lbs.about(turn_q, pivot, pivot) if b in under
                     else lbs.about(IDENTITY, pivot, pivot)) for b in body.bones}
        before = lbs.points([body.verts[i] for i in ids],
                            [body.weights[i] for i in ids], moves)
        was = sum(length(sub(p, body.verts[i])) for p, i in zip(before, ids)) / len(ids)

        sk = bound.skeleton
        root = f"clavicle_{s}"
        under = {root, *sk.descendants(root)}
        pivot = sk.pos(root)
        moves = {b: (lbs.about(turn_q, pivot, pivot) if b in under
                     else lbs.about(IDENTITY, pivot, pivot)) for b in sk.names}
        after = lbs.points([bound.verts[i] for i in ids],
                           [bound.weights[i] for i in ids], moves)
        now = sum(length(sub(p, bound.verts[i])) for p, i in zip(after, ids)) / len(ids)

        held = sum(bound.weights[i].get(root, 0.0) for i in ids) / len(ids)
        held_before = sum(body.weights[i].get(f"{side}Shoulder", 0.0) for i in ids) / len(ids)
        out[s] = {"vertices": len(ids),
                  "clavicle_weight_before": round(held_before, 3),
                  "clavicle_weight_after": round(held, 3),
                  "moved_cm_before": round(was, 2), "moved_cm_after": round(now, 2)}
    return out


def run(body, bound, mann, path=None):
    """(failures, measures) for one bound body; with ``path`` the written
    file is read back as well."""
    fails = structure(bound, mann)
    if path:
        fails += read_back(path, bound)
    measures = {"edge_length_after_over_before": stretch(body, bound),
                "ribs_when_a_clavicle_lifts": clavicle_lift(body, bound)}
    return fails, measures
