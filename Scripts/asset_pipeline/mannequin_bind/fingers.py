"""fingers -- share a hand's weight between the hand bone and its fifteen
finger bones.

Meshy's hand is one bone: every vertex from the wrist to the fingertips moves
with it.  The mannequin's hand has three joints a finger, and its clips close
them.  So the weight a vertex has on Meshy's hand is shared out by where the
vertex is: near a finger's bones it goes to them, in the palm it stays on the
hand.

Each finger bone is a segment from its joint to the next (the last runs on to
the fingertip), and the palm is four segments from the wrist to the knuckles,
which belong to the hand bone.  A vertex's share on each segment falls off
with its distance from it, steeply (the POWER below), so a vertex inside one
finger is that finger's and a vertex in the web between two is shared.

Where the segments lie is finger_fit.py's answer when it finds the digits in
the mesh.  When it cannot, fan() gives the mannequin's own layout, flattened
into the palm's plane: the mannequin's fingers rest curled and a generated
hand is open, and against the curled bones a fingertip of the mesh is nearer
the next finger's middle joint than its own last one.
"""

from asset_pipeline.mannequin_bind.bone_map import (
    FINGERS, FINGER_JOINTS, KNUCKLE_FINGERS, finger_bone)
from asset_pipeline.mannequin_bind.fit import TIP_SHARE
from asset_pipeline.mannequin_bind.xform import (
    add, cross, dot, length, scale, sub, unit)

# How steeply a segment's share falls with distance: at 6 a segment twice as
# far gets a sixty-fourth.
POWER = 6.0
# Added to every distance, as a share of the hand's length, so a vertex ON a
# bone does not take everything and leave its neighbour a seam.
SOFTEN = 0.03
# Shares under this part of the largest are dropped.
KEEP_OVER = 0.04


def _flat(v, origin, axes):
    d = sub(v, origin)
    return (dot(d, axes[0]), dot(d, axes[1]), dot(d, axes[2]))


def _segment_distance(p, a, b):
    ab = sub(b, a)
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / max(dot(ab, ab), 1e-12)))
    return length(sub(p, add(a, scale(ab, t))))


def hand_axes(skeleton, s):
    """(wrist, (finger axis, across axis, normal)) of a fitted hand: the frame
    its vertices are flattened into."""
    wrist = skeleton.pos(f"hand_{s}")
    knuckles = [skeleton.pos(finger_bone(f, 1, s)) for f in KNUCKLE_FINGERS]
    centre = tuple(sum(k[i] for k in knuckles) / len(knuckles) for i in range(3))
    forward = unit(sub(centre, wrist))
    across = sub(knuckles[-1], knuckles[0])
    across = unit(sub(across, scale(forward, dot(across, forward))))
    return wrist, (forward, across, cross(forward, across))


def flat(v, wrist, axes):
    return _flat(v, wrist, axes)


def unflat(p, wrist, axes):
    return add(wrist, add(scale(axes[0], p[0]),
                          add(scale(axes[1], p[1]), scale(axes[2], p[2]))))


def fan(skeleton, s, verts):
    """{finger: [joint 1, 2, 3, tip]} from the fitted skeleton alone: each
    finger straightened in the plane through the middle of the hand's
    thickness, pointing the way its first bone leaves the knuckle."""
    wrist, axes = hand_axes(skeleton, s)
    heights = sorted(_flat(v, wrist, axes)[2] for v in verts)
    plane = heights[len(heights) // 2]
    out = {}
    for f in FINGERS:
        joints = [finger_bone(f, j, s) for j in FINGER_JOINTS]
        spans = [length(sub(skeleton.pos(b), skeleton.pos(a)))
                 for a, b in zip(joints, joints[1:])]
        spans.append(TIP_SHARE * spans[-1])
        u, v, _h = _flat(skeleton.pos(joints[0]), wrist, axes)
        nu, nv, _h = _flat(skeleton.pos(joints[1]), wrist, axes)
        heading = unit((nu - u, nv - v, 0.0))
        points = [(u, v, plane)]
        for span in spans:
            points.append(add(points[-1], scale(heading, span)))
        out[f] = [unflat(p, wrist, axes) for p in points]
    return out


def shares(wrist, found, s, verts):
    """Per vertex, {bone: share} over hand_<s> and its finger bones, summing
    to one.  ``found`` is {finger: [joint 1, 2, 3, tip]}; ``verts`` are the
    hand's vertices; all in the body's space."""
    segs = []
    for f, points in found.items():
        for j, a, b in zip(FINGER_JOINTS, points, points[1:]):
            segs.append((finger_bone(f, j, s), a, b))
        if f in KNUCKLE_FINGERS:
            segs.append((f"hand_{s}", wrist, points[0]))
    soften = SOFTEN * max(length(sub(v, wrist)) for v in verts)
    out = []
    for p in verts:
        raw = {}
        for bone, a, b in segs:
            pull = (_segment_distance(p, a, b) + soften) ** -POWER
            raw[bone] = max(raw.get(bone, 0.0), pull)
        top = max(raw.values())
        kept = {b: w for b, w in raw.items() if w >= KEEP_OVER * top}
        total = sum(kept.values())
        out.append({b: w / total for b, w in kept.items()})
    return out
