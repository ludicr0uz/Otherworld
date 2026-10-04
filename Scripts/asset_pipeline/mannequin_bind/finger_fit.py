"""finger_fit -- find the five digits in a hand's vertices, and bend them
into the mannequin's resting curl.

WHY THE FINGERS ARE FOUND AND NOT ASSUMED
-----------------------------------------
The mannequin's hand, scaled to this hand's length and laid on it, does not
land its fingers on this hand's fingers: a generated hand spreads its fingers
wider, and its wrist joint sits to the thumb's side of the hand's middle.
Shared out by that layout, half of each finger went to its neighbour's bones.
So each digit is found in the mesh, and its three bones are laid down it.

HOW A DIGIT IS FOUND
--------------------
In the hand's flat frame (fingers.py: along the fingers, across them, out of
the palm), with the mesh's own triangles saying which vertices are joined:

    fingers   cut the hand across at a height and the vertices beyond it fall
              into separate pieces, one per finger, until the cut drops under
              a web and two pieces join.  The lowest cut that still leaves
              four pieces gives the four fingers, in order from the thumb.
    thumb     the same, cutting by distance from the wrist on the thumb's
              side of the fingers: the piece that stands apart.

A digit's line is the long axis of its piece, and its tip the furthest vertex
along it.  Its joints go back from the tip at the mannequin's spacing for
that digit, scaled to this hand.

A hand that does not come apart into four fingers and a thumb (a mitten, a
fist, a claw) raises NotFound; bind.py then falls back to the mannequin's
layout and says so.

THE CURL
--------
The mannequin's fingers rest curled; a generated hand is flat and open.  With
the fingers found and weighted, each finger bone is swung onto the
mannequin's line for it, knuckle first, and the vertices follow -- the same
repose the limbs get (repose.py), for the same reason: the mannequin's
reference rotations must be true of this body, or a fist closes short and a
straight finger bends back.
"""

import math

from asset_pipeline.mannequin_bind import lbs
from asset_pipeline.mannequin_bind.bone_map import (
    FINGER_JOINTS, KNUCKLE_FINGERS, finger_bone)
from asset_pipeline.mannequin_bind.fit import TIP_SHARE
from asset_pipeline.mannequin_bind.xform import (
    IDENTITY, add, length, mul, sub, swing, turn, unit)

# A piece smaller than this is a stray, not a digit.
PIECE_MIN_VERTS = 12
# The cut moves in steps of this share of the hand's length.
CUT_STEP = 0.01
# Fingers are looked for above this share of the hand's length (below it the
# cut is in the palm), and the thumb beyond this share from the wrist.
FINGER_CUT_FLOOR = 0.45
THUMB_CUT_FLOOR = 0.30
# A piece under this elongation has no long axis worth reading.
STUBBY = 1.6
# Vertices closer than this are one vertex doubled along a UV seam.
WELD_CM = 0.002
# A vertex this far round toward the thumb, seen from the wrist, is not one of
# the four fingers.
THUMB_SECTOR_DEG = 30.0


class NotFound(ValueError):
    """The hand did not come apart into four fingers and a thumb."""


def _pieces(ids, edges, keep):
    """Connected pieces of the vertices ``keep`` holds, largest first."""
    inside = {i for i in ids if keep(i)}
    parent = {i: i for i in inside}

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in edges:
        if a in inside and b in inside:
            ra, rb = root(a), root(b)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for i in inside:
        groups.setdefault(root(i), []).append(i)
    return sorted((g for g in groups.values() if len(g) >= PIECE_MIN_VERTS),
                  key=len, reverse=True)


def _axis2(points):
    """(centre, unit long axis, elongation) of flat points, by their 2x2
    covariance: elongation is the long axis's spread over the short one's."""
    n = float(len(points))
    cu = sum(p[0] for p in points) / n
    cv = sum(p[1] for p in points) / n
    a = sum((p[0] - cu) ** 2 for p in points) / n
    b = sum((p[0] - cu) * (p[1] - cv) for p in points) / n
    c = sum((p[1] - cv) ** 2 for p in points) / n
    angle = 0.5 * math.atan2(2.0 * b, a - c)
    half, root = (a + c) / 2.0, math.sqrt(((a - c) / 2.0) ** 2 + b * b)
    return ((cu, cv), (math.cos(angle), math.sin(angle)),
            math.sqrt((half + root) / max(half - root, 1e-9)))


def _digit(piece, flat):
    """(tip, heading, height) of one piece: the furthest point along its
    line, the line pointing away from the wrist, and the piece's middle
    height out of the palm's plane.  A piece too stubby to have a long axis
    (a short finger cut high) points the way it lies from the wrist."""
    pts = [flat[i] for i in piece]
    centre, axis, elongation = _axis2(pts)
    if elongation < STUBBY:
        axis = unit((centre[0], centre[1], 0.0))[:2]
    if centre[0] * axis[0] + centre[1] * axis[1] < 0:
        axis = (-axis[0], -axis[1])
    reach = max((p[0] - centre[0]) * axis[0] + (p[1] - centre[1]) * axis[1] for p in pts)
    tip = (centre[0] + axis[0] * reach, centre[1] + axis[1] * reach)
    heights = sorted(p[2] for p in pts)
    return tip, axis, heights[len(heights) // 2]


def find(flat, triangles, thumb_sign):
    """{digit: (tip, heading, height)} in the hand's flat frame.

    flat         {vertex id: (along, across, out)} for the hand's vertices,
                 the wrist at the origin
    triangles    the mesh's, as vertex ids
    thumb_sign   +1 or -1: which way across the thumb is
    """
    ids = list(flat)
    have = set(ids)
    edges = set()
    for a, b, c in triangles:
        if a in have and b in have and c in have:
            edges.update(((a, b), (b, c), (a, c)))
    # A textured mesh is cut along its UV seams: the vertices on a seam are
    # doubled, one per island, and no triangle joins the two copies.  Meshy's
    # atlas is hundreds of islands, so by its triangles alone a finger is a
    # dozen scraps.  Vertices at the same place are joined here.
    at = {}
    for i in ids:
        key = tuple(round(c / WELD_CM) for c in flat[i])
        if key in at:
            edges.add((at[key], i))
        else:
            at[key] = i
    hand_length = max(p[0] for p in flat.values())
    sector = math.tan(math.radians(THUMB_SECTOR_DEG))

    def thumbward(i):
        return flat[i][1] * thumb_sign

    def in_finger_sector(i):
        return thumbward(i) < sector * max(flat[i][0], 0.0)

    fingers = None
    cut = 0.98
    while cut >= FINGER_CUT_FLOOR:
        level = cut * hand_length
        pieces = _pieces(ids, edges,
                         lambda i: flat[i][0] > level and in_finger_sector(i))
        if len(pieces) == 4:
            fingers = pieces
        elif fingers and len(pieces) < 4:
            break
        cut -= CUT_STEP
    if not fingers:
        raise NotFound("no cut across the hand leaves four fingers")

    thumb = None
    cut = 0.98
    reach = max(math.hypot(p[0], p[1]) for i, p in flat.items()
                if not in_finger_sector(i)) if any(
                    not in_finger_sector(i) for i in ids) else 0.0
    while reach and cut >= THUMB_CUT_FLOOR:
        level = cut * reach
        pieces = _pieces(ids, edges, lambda i: not in_finger_sector(i)
                         and math.hypot(flat[i][0], flat[i][1]) > level)
        if len(pieces) == 1:
            thumb = pieces[0]
        cut -= CUT_STEP
    if not thumb:
        raise NotFound("no thumb stands apart on the thumb's side")

    out = {"thumb": _digit(thumb, flat)}
    order = sorted(fingers, key=lambda piece: -sum(thumbward(i) for i in piece) / len(piece))
    for name, piece in zip(KNUCKLE_FINGERS, order):
        out[name] = _digit(piece, flat)
    return out


def chains(digits, skeleton, s, to_space):
    """{finger: [joint 1, joint 2, joint 3, tip]} in the body's space: each
    digit's joints laid back from its tip along its line, at the mannequin's
    spacing for that finger on ``skeleton``, the one fitted to this hand.
    ``to_space`` turns a flat
    (along, across, out) point into the body's space."""
    out = {}
    for finger, (tip, heading, height) in digits.items():
        joints = [skeleton.pos(finger_bone(finger, j, s)) for j in FINGER_JOINTS]
        spans = [length(sub(b, a)) for a, b in zip(joints, joints[1:])]
        spans.append(TIP_SHARE * spans[-1])
        # ``skeleton`` is already at this hand's scale (fit.py).
        points, back = [(tip[0], tip[1], height)], 0.0
        for span in reversed(spans):
            back += span
            points.append((tip[0] - heading[0] * back, tip[1] - heading[1] * back, height))
        out[finger] = [to_space(p) for p in reversed(points)]
    return out


def curl(found, mann, s):
    """How each finger bone turns to take the mannequin's resting curl:
    ({bone: move}, {finger: [joint 1, 2, 3, tip] after the turn}).  ``found``
    is chains()'s result; the knuckles stay where they are."""
    moves, after = {}, {}
    for finger, points in found.items():
        bones = [finger_bone(finger, j, s) for j in FINGER_JOINTS]
        want = [sub(mann.pos(b), mann.pos(a)) for a, b in zip(bones, bones[1:])]
        # The last bone has no child: it runs on the way its own offset from
        # its parent runs, carried by its own rotation.
        last = mann.index(bones[-1])
        want.append(turn(mann.comp_q[last], mann.local_t[last]))
        base, placed = IDENTITY, [points[0]]
        for k, bone in enumerate(bones):
            have = turn(base, sub(points[k + 1], points[k]))
            q = mul(swing(have, want[k]), base)
            moves[bone] = lbs.about(q, points[k], placed[k])
            placed.append(add(placed[k], turn(q, sub(points[k + 1], points[k]))))
            base = q
        after[finger] = placed
    return moves, after
