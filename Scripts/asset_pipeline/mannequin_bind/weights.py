"""weights -- Meshy's 24-bone weights as weights on the mannequin's bones.

The weights are the body's own, re-addressed.  Nothing is transferred from
Manny's mesh: a body with other proportions is not Manny's surface, and what
Meshy's skinning already knows -- which vertex belongs to which limb -- is the
part worth keeping.  What changes:

    one bone for one     hips, head, feet, toes, clavicles
    spine and neck       three spine joints become five, one neck joint two:
                         a vertex's spine weight goes to the mannequin bones
                         level with it, shared between the two it lies between
    limbs                the same sharing, along the limb, between the limb's
                         bone and its two twist bones.  Until something drives
                         them a twist bone moves with its parent and this
                         changes nothing; with the mannequin's post-process
                         rig it is what keeps a turned forearm from wringing
    hands                fingers.py
    clavicles and upper  see CLAVICLE and UPPER ARM below: trimmed off the
    arms, trimmed        ribs, the fault this pipeline was written after

Then each vertex keeps its four largest shares.
"""

from asset_pipeline.mannequin_bind import fingers
from asset_pipeline.mannequin_bind.bone_map import (
    DIRECT, HANDS, LIMBS, MANNEQUIN_NECK_LINE, MANNEQUIN_SPINE_LINE,
    NECK_WEIGHT, SIDES, SPINE_WEIGHT)
from asset_pipeline.mannequin_bind.glb import MAX_INFLUENCES
from asset_pipeline.mannequin_bind.xform import (
    add, dot, length, scale, smoothstep, sub)

# ── CLAVICLE ─────────────────────────────────────────────────────────────────
# Meshy's rigger spreads the clavicle far down the ribs.  Measured on
# adventurer_03's rig: on the side of the ribcage 5-25 cm under the shoulder
# joint the clavicle holds 28% of the weight on average, and it reaches 25 cm
# below the joint and past the body's midline.  A clavicle lifts in every jump
# and every reach, and the side of the torso went with it: the lats flaring.
#
# A clavicle moves the shoulder girdle: the top of the chest, the trapezius,
# the root of the arm.  So its weight is faded out below the armpit and across
# the midline, and what is taken off goes to the spine bones level with the
# vertex.  Distances are for a 180 cm body and scale with stature.
#
# Where the fade sits, measured on adventurer_03 (check.clavicle_lift: one
# clavicle lifted 20 degrees, how far that patch of ribs moves on average):
#
#     fade under the joint    clavicle weight on the ribs    ribs move
#     as generated            0.28 / 0.33                    2.0 / 2.5 cm
#     5 to 15 cm              0.16 / 0.15                    1.3 / 1.4
#     2 to 10 cm              0.05 / 0.04                    0.8 / 0.9
#     0 to  8 cm              0.01 / 0.01                    0.7 / 0.8
#
# What is left at the bottom of the table is the upper arm's own hold on the
# armpit, which is right: the skin there does follow a lifted arm.  2 to 10
# takes nearly all of the clavicle's part and still leaves it the armpit's
# top edge; whether the shoulder then creases is for eyes in the editor.
CLAVICLE_FULL_TO_CM = 2.0        # this far under the shoulder joint: untouched
CLAVICLE_NONE_BY_CM = 10.0       # this far under: none left
CLAVICLE_MIDLINE_CM = 4.0        # this far past the midline: none left
REFERENCE_STATURE_CM = 180.0


# ── UPPER ARM ────────────────────────────────────────────────────────────────
# The same fault one bone further out.  Meshy's upper arm holds skin well onto
# the ribs: with the clavicle trimmed and the arms lifted as MM_Fall_Loop lifts
# them (clavicle 20 degrees, upper arm 100), the chest under the armpits still
# measured 1.33 times its resting width -- in the game, a torso a third too
# wide and pulled long whenever the arms went up.
#
# An upper arm moves the arm and the cap of the shoulder.  So its weight (the
# bone's and its twist bones') is faded with distance from the bone's own
# line, measured in arm radii -- the radius being this body's, read off the
# vertices the arm holds outright along its middle.  Skin within ARM_FULL_TO
# radii is the arm's; by ARM_NONE_BY it is the trunk's, and what is taken off
# goes to the trunk bones the vertex already has.  A vertex with no trunk
# weight is left alone: it is arm, however thick.
#
# Where the fade sits, on adventurer_03, by the chest's width under the
# armpits with the arms lifted that way, against its width at rest:
#
#     no trim        1.33
#     1.3  to 2.1    1.14
#     1.15 to 1.8    1.09
#     1.0  to 1.6    1.03
#
# A chest does widen a little under lifted arms, and the tightest line takes
# the armpit's own skin off the arm, which is a crease waiting to be seen.
ARM_FULL_TO = 1.15
ARM_NONE_BY = 1.8


def hat(nodes, u):
    """{bone: share} between the two nodes ``u`` lies between; nodes are
    (position, bone) in rising order, and past either end the end node takes
    it all."""
    if u <= nodes[0][0]:
        return {nodes[0][1]: 1.0}
    for (a, bone_a), (b, bone_b) in zip(nodes, nodes[1:]):
        if u <= b:
            t = (u - a) / (b - a) if b > a else 1.0
            return {bone_a: 1.0 - t, bone_b: t} if 0.0 < t < 1.0 else \
                   ({bone_b: 1.0} if t >= 1.0 else {bone_a: 1.0})
    return {nodes[-1][1]: 1.0}


class _Line:
    """A polyline of bones: where a point is along it, and the hat nodes at
    the middle of each bone's own stretch."""

    def __init__(self, skeleton, bones):
        self.points = [skeleton.pos(b) for b in bones]
        self.starts = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.starts.append(self.starts[-1] + length(sub(b, a)))
        # bones[-1] only ends the line: it is the next bone's joint.
        self.nodes = [((self.starts[i] + self.starts[i + 1]) / 2.0, bones[i])
                      for i in range(len(bones) - 1)]

    def at(self, p):
        best, where = None, 0.0
        for i, (a, b) in enumerate(zip(self.points, self.points[1:])):
            ab = sub(b, a)
            t = max(0.0, min(1.0, dot(sub(p, a), ab) / max(dot(ab, ab), 1e-12)))
            d = length(sub(p, add(a, scale(ab, t))))
            if best is None or d < best:
                best, where = d, self.starts[i] + t * (self.starts[i + 1] - self.starts[i])
        return where


def limb_nodes(skeleton, bone, child, upper):
    """Hat nodes along one limb segment, 0 at its joint and 1 at its child's:
    the twist bones where they sit, and the bone itself at the end that takes
    the whole twist."""
    start = skeleton.pos(bone)
    line = sub(skeleton.pos(child), start)
    nodes = [(dot(sub(skeleton.pos(t), start), line) / dot(line, line), t)
             for t in skeleton.children(bone) if "_twist_" in t]
    nodes.append((1.0 if upper else 0.0, bone))
    return sorted(nodes), start, line


def _add(into, shares, by):
    for bone, share in shares.items():
        into[bone] = into.get(bone, 0.0) + share * by


def _trim_clavicles(new, v, skeleton, spine, stature):
    k = stature / REFERENCE_STATURE_CM
    middle = skeleton.pos("spine_05")[0]
    for s, _side in SIDES:
        bone = f"clavicle_{s}"
        have = new.get(bone, 0.0)
        if have <= 0.0:
            continue
        shoulder = skeleton.pos(f"upperarm_{s}")
        under = shoulder[2] - v[2]
        keep = 1.0 - smoothstep(CLAVICLE_FULL_TO_CM * k, CLAVICLE_NONE_BY_CM * k, under)
        outward = 1.0 if shoulder[0] > middle else -1.0
        across = -(v[0] - middle) * outward
        keep *= 1.0 - smoothstep(0.0, CLAVICLE_MIDLINE_CM * k, across)
        if keep >= 1.0:
            continue
        new[bone] = have * keep
        if new[bone] <= 0.0:
            del new[bone]
        _add(new, hat(spine.nodes, spine.at(v)), have * (1.0 - keep))


def _to_segment(p, a, b):
    ab = sub(b, a)
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / max(dot(ab, ab), 1e-12)))
    return length(sub(p, add(a, scale(ab, t)))), t


def arm_radii(weighted, verts, skeleton):
    """{suffix: (upper arm bones, shoulder, elbow, radius)}: the radius is the
    median distance from the bone's line of the vertices the arm holds
    outright, along the middle of the arm."""
    out = {}
    for s, _side in SIDES:
        bones = [f"upperarm_{s}"] + [b for b in skeleton.children(f"upperarm_{s}")
                                     if "_twist_" in b]
        a, b = skeleton.pos(f"upperarm_{s}"), skeleton.pos(f"lowerarm_{s}")
        around = []
        for v, w in zip(verts, weighted):
            if sum(w.get(x, 0.0) for x in bones) < 0.9:
                continue
            d, t = _to_segment(v, a, b)
            if 0.35 < t < 0.85:
                around.append(d)
        if len(around) < 16:
            raise ValueError(f"upperarm_{s}: only {len(around)} vertices to "
                             "read the arm's thickness from")
        around.sort()
        out[s] = (bones, a, b, around[len(around) // 2])
    return out


def _trim_arms(new, v, arms):
    trunk = {b: w for b, w in new.items()
             if b == "pelvis" or b.startswith(("spine_", "clavicle_", "neck_"))}
    if not trunk:
        return
    for bones, a, b, radius in arms.values():
        have = {x: new[x] for x in bones if x in new}
        if not have:
            continue
        d, _t = _to_segment(v, a, b)
        keep = 1.0 - smoothstep(ARM_FULL_TO * radius, ARM_NONE_BY * radius, d)
        if keep >= 1.0:
            continue
        freed = sum(have.values()) * (1.0 - keep)
        for x, w in have.items():
            if w * keep > 0.0:
                new[x] = w * keep
            else:
                del new[x]
        total = sum(trunk.values())
        for x, w in trunk.items():
            new[x] += freed * w / total


def prune(w, limit=MAX_INFLUENCES):
    """The ``limit`` largest shares, made to sum to one."""
    top = sorted(w.items(), key=lambda kv: -kv[1])[:limit]
    total = sum(share for _b, share in top)
    return {b: share / total for b, share in top}


def remap(body_weights, verts, skeleton, stature, digits, limit=MAX_INFLUENCES):
    """Per vertex {mannequin bone: weight}, from per vertex {Meshy bone:
    weight}.  ``verts`` and ``skeleton`` are the body in the mannequin's pose
    and the skeleton fitted to it; ``digits`` is {suffix: {finger: [joint 1,
    2, 3, tip]}}, where each hand's finger bones lie (fingers.py)."""
    spine = _Line(skeleton, MANNEQUIN_SPINE_LINE)
    neck = _Line(skeleton, MANNEQUIN_NECK_LINE)
    limbs = {b: limb_nodes(skeleton, m, mc, upper)
             for b, (_c, m, mc, upper) in LIMBS.items()}

    hand_share = {}
    for bone, s in HANDS.items():
        ids = [i for i, w in enumerate(body_weights) if w.get(bone, 0.0) > 0.0]
        for i, share in zip(ids, fingers.shares(
                skeleton.pos(f"hand_{s}"), digits[s], s, [verts[i] for i in ids])):
            hand_share[(bone, i)] = share

    out = []
    for i, (v, w) in enumerate(zip(verts, body_weights)):
        new = {}
        for bone, share in w.items():
            if bone in DIRECT:
                _add(new, {DIRECT[bone]: 1.0}, share)
            elif bone in SPINE_WEIGHT:
                _add(new, hat(spine.nodes, spine.at(v)), share)
            elif bone in NECK_WEIGHT:
                _add(new, hat(neck.nodes, neck.at(v)), share)
            elif bone in LIMBS:
                nodes, start, line = limbs[bone]
                u = dot(sub(v, start), line) / dot(line, line)
                _add(new, hat(nodes, u), share)
            elif bone in HANDS:
                _add(new, hand_share[(bone, i)], share)
            else:
                raise ValueError(f"no rule for Meshy bone {bone}")
        _trim_clavicles(new, v, skeleton, spine, stature)
        out.append(new)
    arms = arm_radii(out, verts, skeleton)
    for v, new in zip(verts, out):
        _trim_arms(new, v, arms)
    return [prune(new, limit) for new in out]
