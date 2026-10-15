"""The drawn MetaHuman's fingers on a gun: the fit, in the hand's own frame,
of each finger's bend on the gun's real mesh (finger_fit.py does the
bending; drawn_grip_bake.py measures the mesh and keys the clip).

Pure (no ``unreal``). Tests: dev/tests/test_drawn_grip.py.

WHY THE HAND'S FRAME
--------------------
The drawn wrists are pinned to the mannequin's (asset_pipeline/hand_goals.py),
so where a hand is on a gun is known: drawn_grip_capture.json has it, read
off the running game by probes/probe_drawn_grip.py, in every state the gun
is held in. The right hand is the same in all of them; the left is not (the
ready clip's, the sights' IK, the carry's clips). One finger pose has to do
for every state a frame of the clip is played in, so each frame is fitted
in the hand's frame against the gun as seen from every placement it covers
at once (Seen): the nearest of them is what a finger may not press into,
and what it lies on.

A FINGER'S POINTS
-----------------
A chain is a hand's bones from the root the layer replaces (a metacarpal,
or thumb_01) down: the joints of its last three bones and a tip past the
last, along that bone's long axis (gun_hold.thumb_lines' rule), are what
finger_fit bends. Locals are parent-space transforms, ((x, y, z), (qx, qy,
qz, qw)), as the capture holds them.
"""

import math

from combat import finger_fit

FINGERS = ("index", "middle", "ring", "pinky")
# The chain of each finger from the bone the layer replaces down (its side's
# suffix added by chain()); the thumb's starts at its first bone.
FINGER_CHAIN = ("{f}_metacarpal", "{f}_01", "{f}_02", "{f}_03")
THUMB_CHAIN = ("thumb_01", "thumb_02", "thumb_03")
# Past the last joint, how far the tip is (cm): gun_hold's numbers.
FINGER_TIP_CM = 2.5
THUMB_TIP_CM = 3.0
# The axis a MetaHuman finger's joints bend about, in its middle bone's own
# frame (both hands; read off the capture's curled fingers). The plane of a
# finger's points is noise on a straight one: Lyra's pistol index.
CURL_AXIS = (0.0, 0.0, -1.0)
# How far each joint may open from the captured pose and close past it
# (degrees: finger_fit.limits()). Wider than the mannequin fit's: the drawn
# hands are placed by clips and IK made for another hand, and a knuckle
# that sits on the gun lifts its finger out only by opening further.
REACH = ((35.0, 25.0, 20.0), (60.0, 70.0, 60.0))
# What a riding point pressed into the gun costs, per cm2, against one off
# it at 1 (finger_fit.misfit; the mannequin fit's is 4): a finger is laid
# with its skin touching, never with some of it in the gun to bring the
# rest nearer. And how many of its riding points on the gun make a finger
# laid on it (finger_fit.close; the mannequin's 2): one past the end of a
# part, over a magazine's well, is laid on what it can reach.
PRESS_WEIGHT = 400.0
ON_POINTS = 1
# How far a trigger finger may spread at its knuckle, either way, and the
# step it is searched in (degrees).
SPREAD_DEG = 25.0
SPREAD_STEP_DEG = 5.0
# A finger still pressed into the gun more than TIE_CM (cm) once bent, its
# knuckle or a riding point (_deep), may turn at its metacarpal's root
# (fit_finger): about its curl, up to CUP_DEG either way in CUP_STEP_DEG
# steps (the palm cupped or flattened under it), by the least turn that
# lifts its knuckle within CUP_FROM_CM of a skin off the gun; then straight
# out of the gun, LIFT_STEP_DEG at a time up to LIFT_DEG (further than a
# cup: the knuckle is a skin's width in), until a turn leaves the finger
# out. The one whose riding points are left least deep is kept, then whose
# knuckle is, then (within TIE_CM of both) the one that fits best.
CUP_DEG = 15.0
CUP_STEP_DEG = 2.5
CUP_FROM_CM = 0.1
LIFT_DEG = 25.0
LIFT_STEP_DEG = 5.0
TIE_CM = 0.05
# How much further a thumb may swing past where finger_fit.swing() stops
# it, either way, to lift the middle of its first bone out (degrees).
THUMB_ON_DEG = 10.0
# Which of finger_fit.riding()'s points is the trigger finger's pad: the
# middle of its last bone.
PAD = 4

IDENTITY = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def chain(finger, side):
    """The bones of ``finger`` ("thumb" or one of FINGERS) on ``side``
    ("r" or "l"), root first."""
    names = THUMB_CHAIN if finger == "thumb" else [b.format(f=finger) for b in FINGER_CHAIN]
    return [f"{b}_{side}" for b in names]


def roots(side):
    """The bones the layer replaces, with all under them, on ``side``."""
    return [chain(f, side)[0] for f in ("thumb",) + FINGERS]


def _mul(a, b):
    """a * b: turn by b, then by a (FQuat's order; body_pose's, which needs
    the editor)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _conj(q):
    return (-q[0], -q[1], -q[2], q[3])


def _turn(q, v):
    x, y, z, _w = _mul(_mul(q, (v[0], v[1], v[2], 0.0)), _conj(q))
    return (x, y, z)


def compose(parent, local):
    """A child's transform from its parent's and its local one (unit scale)."""
    (pl, pq), (ll, lq) = parent, local
    return (tuple(a + b for a, b in zip(pl, _turn(pq, ll))), _norm_q(_mul(pq, lq)))


def inverse(xf):
    loc, q = xf
    iq = _conj(q)
    return (tuple(-x for x in _turn(iq, loc)), iq)


def apply(xf, p):
    """Point ``p`` of xf's frame in the frame xf is in."""
    loc, q = xf
    return tuple(a + b for a, b in zip(loc, _turn(q, p)))


def _norm_q(q):
    n = math.sqrt(sum(x * x for x in q))
    return tuple(x / n for x in q)


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v)


def placed(locals_, bones, base=IDENTITY):
    """Each of ``bones``' transforms, down the chain from ``base`` (the
    hand's, in whatever frame that is)."""
    out, at = [], base
    for bone in bones:
        at = compose(at, locals_[bone])
        out.append(at)
    return out


def points(xfs, tip_cm):
    """A finger's last three joints and its tip, from its chain's placed
    transforms (a thumb's three)."""
    joints = [xf[0] for xf in xfs[-3:]]
    line = _unit(tuple(b - a for a, b in zip(joints[-2], joints[-1])))
    axis = _turn(_conj(xfs[-2][1]), line)
    tip_dir = _turn(xfs[-1][1], axis)
    return joints + [tuple(p + tip_cm * d for p, d in zip(joints[-1], tip_dir))]


class Seen:
    """A solid in the gun's frame, seen from a hand placed on it at each of
    ``hands`` (the hand's transforms in the gun's frame): a point of the
    hand's frame is as far from it as from the nearest of its placements."""

    def __init__(self, solid, hands):
        self.solid = finger_fit.as_solid(solid)
        self.hands = list(hands)

    def __bool__(self):
        return bool(self.solid) and bool(self.hands)

    def distance(self, p):
        return min(self.solid.distance(apply(h, p)) for h in self.hands)

    def toward(self, p):
        h = min(self.hands, key=lambda h: self.solid.distance(apply(h, p)))
        return apply(inverse(h), self.solid.toward(apply(h, p)))


def _turned(locals_, xfs, bones, rots):
    """New locals for ``bones`` whose placed rotations (hand frame) become
    ``rots``: each one's parent is the chain's bone before it, or the hand."""
    out = {}
    for i, bone in enumerate(bones):
        parent = rots[i - 1] if i else None
        out[bone] = (locals_[bone][0],
                     _norm_q(_mul(_conj(parent), rots[i])) if parent else rots[i])
    return out


def _spun(pts, axis, deg):
    """A finger's points turned ``deg`` about ``axis`` through its knuckle."""
    return [pts[0]] + [tuple(k + d for k, d in zip(pts[0], finger_fit.turned(
        tuple(p - k for p, k in zip(q, pts[0])), axis, deg))) for q in pts[1:]]


def _cupped(xfs, axis, deg):
    """A finger's placed transforms turned ``deg`` about ``axis`` through its
    metacarpal's root: the palm cupped (or flattened) under that finger."""
    if not deg:
        return xfs
    q, root = finger_fit.quat(axis, deg), xfs[0][0]
    return [(tuple(r + d for r, d in zip(root, _turn(q, tuple(a - r for a, r in
                                                              zip(xf[0], root))))),
             _norm_q(_mul(q, xf[1]))) for xf in xfs]


def _knuckle(solid, xfs):
    """How deep (cm, 0 for none) a finger's knuckle (its first joint past
    the metacarpal) is pressed into ``solid``, a skin off its bone."""
    return max(0.0, finger_fit.SKIN_CM - solid.distance(xfs[1][0]))


def _bent(xfs, solid, aim, spreads=None):
    """(cost, spread, spread axis, bend axis, angles) of the best bend of a
    finger placed at ``xfs``: fit_finger's search at one cup, over
    ``spreads`` (by default every one an aimed finger may take)."""
    pts = points(xfs, FINGER_TIP_CM)
    curl = _turn(xfs[-2][1], CURL_AXIS)
    spread_axis = finger_fit._unit(finger_fit._cross(
        curl, tuple(b - a for a, b in zip(pts[0], pts[1]))))
    best = None
    if spreads is None:
        spreads = _spreads() if aim is not None else (0.0,)
    for spread in spreads:
        spun = _spun(pts, spread_axis, spread)
        axis = finger_fit.turned(curl, spread_axis, spread)
        target = None if aim is None else (PAD, aim)
        angles, _met = finger_fit.close(spun, solid, aim=target, axis=axis, reach=REACH,
                                        press=PRESS_WEIGHT, on_points=ON_POINTS)
        cost = finger_fit.misfit(solid, spun, angles, target, axis=axis, press=PRESS_WEIGHT)
        if best is None or cost < best[0] - 1e-9:
            best = (cost, spread, spread_axis, axis, angles)
    return best


def fit_finger(locals_, bones, solid, aim=None):
    """(new locals of a finger's bones, its angles, spread and cup) as
    finger_fit.close() bends it on ``solid`` (in the hand's frame), about its
    joints' own axis. ``aim``: a point (or segment) of the hand's frame its
    pad is drawn to; the finger may then also spread at its knuckle, up to
    SPREAD_DEG either way (a pistol's index lies along the frame). A finger
    left pressed into the gun (no bend lifts it: the clip's palm is another
    hand's, its knuckle on the gun) is bent again from its metacarpal turned
    at the root: cupped (_cup), then straight out (_lift), a step further
    each time until it is out (the constants above say how far)."""
    solid = finger_fit.as_solid(solid)
    xfs = placed(locals_, bones)
    best = None
    for way, turn in _turns(solid, xfs):
        cupped = _cupped(xfs, way, turn)
        bent = _bent(cupped, solid, aim) + (turn, cupped)
        deep = _deep(solid, bent)
        if _better(deep, bent[0], best):
            best = (deep, bent)
        if max(best[0]) <= TIE_CM:
            break
    _cost, spread, spread_axis, axis, angles, cup, xfs = best[1]
    if not any(angles) and not spread and not cup:
        return {}, tuple(angles) + (0.0, 0.0)
    spin, total, rots = finger_fit.quat(spread_axis, spread), 0.0, [xfs[0][1]]
    for xf, angle in zip(xfs[1:], angles):
        total += angle
        rots.append(_norm_q(_mul(finger_fit.quat(axis, total), _mul(spin, xf[1]))))
    turned = _turned(locals_, xfs, bones, rots)
    if not cup:
        turned.pop(bones[0])
    return turned, tuple(angles) + (spread, cup)


def _turns(solid, xfs):
    """The metacarpal turns fit_finger bends a finger from, in order: none,
    the cup that lifts its knuckle (if any), then each step straight out."""
    yield None, 0.0
    curl = _turn(xfs[-2][1], CURL_AXIS)
    cup = _cup(solid, xfs, curl, _cups())
    if cup:
        yield curl, cup
    lift = _lift(solid, xfs)
    for i in range(1, int(LIFT_DEG / LIFT_STEP_DEG) + 1 if lift else 0):
        yield lift, LIFT_STEP_DEG * i


def _deep(solid, bent):
    """(how far its deepest riding point is, how far its knuckle is) pressed
    into ``solid`` (cm), of a finger bent as ``bent`` (_bent's, with its cup
    and placement)."""
    _cost, spread, spread_axis, axis, angles, _cup, xfs = bent
    pts = finger_fit.posed(_spun(points(xfs, FINGER_TIP_CM), spread_axis, spread), axis, angles)
    return tuple(max(0.0, finger_fit.SKIN_CM - finger_fit.nearest(solid, some))
                 for some in (finger_fit.riding(pts), pts[:1]))


def _better(deep, cost, best):
    """Whether a bend ``deep`` (_deep's) costing ``cost`` beats ``best``,
    (deep, (cost, ...)): its riding points less deep, then its knuckle, each
    by more than TIE_CM, then fitting better."""
    if best is None:
        return True
    for mine, theirs in zip(deep, best[0]):
        if abs(mine - theirs) > TIE_CM:
            return mine < theirs
    return cost < best[1][0] - 1e-9


def _cups():
    """The cups to try, the least first, each way."""
    n = int(CUP_DEG / CUP_STEP_DEG)
    return [w * i * CUP_STEP_DEG for i in range(1, n + 1) for w in (1, -1)]


def _cup(solid, xfs, axis, turns):
    """The first of ``turns`` about ``axis`` that leaves the knuckle within
    CUP_FROM_CM of a skin off ``solid``, or failing that the one that
    leaves it least deep (0: none lifts it at all)."""
    cup, depth = 0.0, _knuckle(solid, xfs)
    for turn in turns:
        deeper = _knuckle(solid, _cupped(xfs, axis, turn))
        if deeper < depth - 1e-6:
            cup, depth = turn, deeper
        if depth <= CUP_FROM_CM:
            break
    return cup


def _lift(solid, xfs):
    """The axis through a finger's metacarpal's root that a positive turn
    about carries its knuckle straight out of ``solid`` (None when the
    knuckle is on the line out of the root)."""
    root, knuckle = xfs[0][0], xfs[1][0]
    on = solid.toward(knuckle)
    out = tuple((a - b) * (1.0 if solid.distance(knuckle) >= 0.0 else -1.0)
                for a, b in zip(knuckle, on))
    axis = finger_fit._cross(tuple(k - r for k, r in zip(knuckle, root)), out)
    return finger_fit._unit(axis) if finger_fit._len(axis) > 1e-9 else None


def _ons():
    """The thumb's further swings to try, the least first, each way."""
    n = int(THUMB_ON_DEG / finger_fit.STEP_DEG)
    return [0.0] + [w * i * finger_fit.STEP_DEG for i in range(1, n + 1) for w in (-1, 1)]


def _spreads():
    n = int(SPREAD_DEG / SPREAD_STEP_DEG)
    return [i * SPREAD_STEP_DEG for i in range(-n, n + 1)]


def fit_thumb(locals_, bones, solid):
    """(the thumb's first bone's new local, the swing's degrees):
    finger_fit.swing() lays it on ``solid`` (in the hand's frame); if any
    of its riding points (the middle of its first bone too, which swing()
    does not read) is still pressed in, it swings the least further, either
    way and up to THUMB_ON_DEG, that clears them all (none: as swing() left
    it)."""
    xfs = placed(locals_, bones)
    pts = points(xfs, THUMB_TIP_CM)
    axis, deg = finger_fit.swing(pts, solid)
    if deg:
        deg = next((deg + d for d in _ons() if finger_fit.nearest(solid, finger_fit.riding(
            finger_fit.swung(pts, axis, deg + d))) >= finger_fit.SKIN_CM), deg)
    if not deg:
        return {}, 0.0
    return {bones[0]: (locals_[bones[0]][0],
                       _norm_q(_mul(finger_fit.quat(axis, deg), xfs[0][1])))}, deg


def fit_hand(locals_, side, solid, trigger=None):
    """({bone: new local} for every finger and the thumb of ``side`` that
    the fit moves, {finger: its angles or the thumb's swing}). ``solid`` is
    in the hand's frame; ``trigger`` a point of it the index's pad goes to."""
    out, said = {}, {}
    for finger in FINGERS:
        aim = trigger if finger == "index" else None
        moved, said[finger] = fit_finger(locals_, chain(finger, side), solid, aim)
        out.update(moved)
    moved, said["thumb"] = fit_thumb(locals_, chain("thumb", side), solid)
    out.update(moved)
    return out, said


def finger_points(locals_, side, base=IDENTITY):
    """{finger: its joints and tip} for every finger and the thumb of
    ``side``, from the hand at ``base``."""
    return {f: points(placed(locals_, chain(f, side), base),
                      THUMB_TIP_CM if f == "thumb" else FINGER_TIP_CM)
            for f in ("thumb",) + FINGERS}


def offsets(locals_, side, solid, base=IDENTITY):
    """{finger: (nearest, furthest)} of its riding points' distances (cm) to
    ``solid`` (in base's frame), less the skin: below 0 is pressed in, as
    probe_drawn_grip measures them."""
    out = {}
    for finger, pts in finger_points(locals_, side, base).items():
        d = [solid.distance(p) - finger_fit.SKIN_CM for p in finger_fit.riding(pts)]
        out[finger] = (min(d), max(d))
    return out


def capsules(locals_, side, base):
    """The fingers of ``side`` (not the thumb) as capsules in base's frame:
    a closed fist, which the other hand's fingers lie on."""
    segments = []
    for finger in FINGERS:
        pts = finger_points(locals_, side, base)[finger]
        segments += list(zip(pts, pts[1:]))
    return finger_fit.Capsules(segments)


def trim(capture, frames, bones, starts=None):
    """The part of probe_drawn_grip's capture the fit reads: {gun: {"hand_r":
    xf, "right": {bone: local}, "frames": {frame: {"hands": [hand_l xf, ...],
    "left": {bone: local}}}}}. ``frames``: {frame: (its states, the state
    whose locals start it)}; ``bones``: the bones to keep, by side;
    ``starts``: {gun: {frame: state}}, a gun's own state to start a frame
    from instead."""
    def rounded(xf):
        return [[round(x, 4) for x in xf[0]], [round(x, 6) for x in xf[1]]]

    out = {}
    for gun, states in sorted(capture.items()):
        start = states[frames[next(iter(frames))][1]]
        row = {"hand_r": rounded(start["hand_r"]),
               "right": {b: rounded(start["local"][b]) for b in bones["r"]},
               "frames": {}}
        for frame, (names, first) in frames.items():
            first = (starts or {}).get(gun, {}).get(frame, first)
            have = [n for n in names if n in states]
            row["frames"][frame] = {
                "hands": [rounded(states[n]["hand_l"]) for n in have],
                "left": {b: rounded(states[first]["local"][b]) for b in bones["l"]}}
        out[gun] = row
    return out


def xf_of(row):
    """A capture's [[x, y, z], [qx, qy, qz, qw]] as a transform."""
    return (tuple(row[0]), tuple(row[1]))


def locals_of(rows):
    return {bone: xf_of(row) for bone, row in rows.items()}


def finger_bones(names, side):
    """Of ``names``, the bones under the roots of ``side``'s fingers and
    thumb: what the clip keys (each finger's helpers move with it)."""
    heads = ("thumb",) + FINGERS
    return sorted(n for n in names if n.endswith(f"_{side}") and n.split("_")[0] in heads)


def take_capture(source, out, frames, guns, starts=None):
    """Write the trimmed capture (trim()) of probe_drawn_grip's ``source``
    JSON to ``out``: the guns of ``guns``, each frame's states (``starts``:
    trim()'s)."""
    import json
    with open(source) as f:
        capture = {g: s for g, s in json.load(f).items() if g in guns}
    names = next(iter(next(iter(capture.values())).values()))["local"]
    bones = {side: finger_bones(names, side) for side in "rl"}
    with open(out, "w") as f:
        json.dump(trim(capture, frames, bones, starts), f, indent=None, separators=(",", ":"))
        f.write("\n")


if __name__ == "__main__":
    # (cd Scripts && python3 -m combat.drawn_grip): take the last
    # probe_drawn_grip run's capture (Saved/grip_report/drawn_hands.json)
    # into the tracked drawn_grip_capture.json the bake reads.
    import os
    from combat.drawn_grip_consts import FRAME_START_BY_GUN, FRAME_STATES, GUNS
    here = os.path.dirname(os.path.abspath(__file__))
    take_capture(os.path.join(here, "..", "..", "Saved", "grip_report", "drawn_hands.json"),
                 os.path.join(here, "drawn_grip_capture.json"), FRAME_STATES, GUNS,
                 FRAME_START_BY_GUN)
