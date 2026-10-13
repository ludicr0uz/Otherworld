"""How far each finger bends to rest on a gun: the angles that close a
finger's three joints onto the boxes of the model, and the swing that lays a
thumb against it.

Pure (no ``unreal``); finger_pose.py calls it for every finger of a gun whose
fingers are fitted and keys the answer into that gun's ready clip, and
verify/finger_pose.py measures the saved clip with the same nearest(). Tests:
dev/tests/test_finger_fit.py.

A ready clip's hand was made for some other gun. gun_hold.py brings the hand
to the part as one rigid piece, the worst joint as near as it can be, which
leaves the others in the air: under an AK's handguard the rifle pose's
fingers ride 0.3 to 4.2 cm off it, and round its grip 1 to 2.4 cm.

So each finger is closed the way a hand closes on a thing:

  - it bends about one axis, the normal of the plane its own joints lie in
    (hinge()): the way the clip already curls it, whatever the rig's bone
    axes are;
  - its three joints take the bend that lays it best on the gun (close()):
    its outer joints, its tip and the middles of its outer bones each as
    near a SKIN_CM off a box as they can all be, the axis of a finger riding
    its own thickness off what it lies on, a point pressed into the gun
    counted worse than one as far off it;
  - a joint opens at most OPEN_DEG from the clip's pose and closes at most
    CLOSE_DEG, never back past straight nor past BEND_MAX_DEG;
  - a finger that cannot be laid on anything keeps the clip's pose (a little
    finger past the end of a handguard is not made into a fist).

(Closing the knuckle until something touches, then the next joint, was tried
first: the tip of an opened finger touches before the finger is round the
part, and the outer joints then cannot move.)

The thumb does not curl round a part; it is laid against it: one swing at
its base towards the nearest box (swing()), stopped on contact or under a
ceiling (the sight line).

Everything is in one frame, the weapon's (+X down the barrel, +Z up), in cm.
"""

import math

from combat.hand_seat import SEAT_OFF_CM, box_distance

# A finger's axis rides this far off what it lies on: the seat's own number.
SKIN_CM = SEAT_OFF_CM
# How far each joint (knuckle, middle, last) may open from the clip's pose,
# and how far it may close past it (degrees). The knuckle's opening is what
# lifts a middle joint out of a part (20 degrees of a 4 cm bone are 1.4 cm);
# the closing is short of a fist.
OPEN_DEG = (20.0, 20.0, 20.0)
CLOSE_DEG = (45.0, 60.0, 50.0)
STEP_DEG = 0.5
# A joint is never bent further than this from straight, clip and fit
# together (degrees), nor back past straight.
BEND_MAX_DEG = 100.0
# A riding point counts as on the gun within this of a SKIN_CM off it (cm),
# and a finger is fitted when this many of its five are.
TOUCH_CM = 0.3
ON_POINTS = 2
# A point pressed into the gun weighs this many times one as far off it; a
# degree off the clip's pose weighs this much (cm2 per degree2).
_PRESS_WEIGHT = 4.0
_KEEP_WEIGHT = 1e-5
_GRID_DEG = 5.0
# The thumb's swing at its base (degrees), and how far under the ceiling its
# points stay (hand_seat.THUMB_CLEAR_CM is the seat's).
THUMB_SWING_DEG = 40.0
THUMB_CLEAR_CM = 0.3
# A finger straighter than this (the sine of its bend, summed over its two
# joints) has no plane of its own to bend in.
_STRAIGHT = 0.05


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _len(a):
    return sum(x * x for x in a) ** 0.5


def _unit(a):
    n = _len(a)
    return tuple(x / n for x in a)


def turned(v, axis, deg):
    """``v`` turned ``deg`` about the unit ``axis`` (right-handed)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    k = sum(a * b for a, b in zip(axis, v)) * (1.0 - c)
    return tuple(x * c + w * s + a * k for x, w, a in zip(v, _cross(axis, v), axis))


def quat(axis, deg):
    """The turn of ``deg`` about the unit ``axis`` as (x, y, z, w)."""
    h = math.radians(deg) / 2.0
    return tuple(a * math.sin(h) for a in axis) + (math.cos(h),)


def hinge(points):
    """The unit axis a finger bends about: the normal of the plane its joints
    and tip lie in, signed so a positive turn curls it further. ``points``:
    its three joints and its tip. None for a finger held straight."""
    lines = [_unit(_sub(b, a)) for a, b in zip(points, points[1:])]
    n = _add(_cross(lines[0], lines[1]), _cross(lines[1], lines[2]))
    return _unit(n) if _len(n) > _STRAIGHT else None


def posed(points, axis, angles):
    """``points`` (three joints and the tip) with each joint bent by its angle
    of ``angles`` (degrees) about ``axis``: a joint carries all past it."""
    out, total = [points[0]], 0.0
    for i, angle in enumerate(angles):
        total += angle
        out.append(_add(out[-1], turned(_sub(points[i + 1], points[i]), axis, total)))
    return out


def beyond(points, joint):
    """The points of a finger that turn with ``joint`` (0, 1 or 2): the
    middle and the end of every bone past it."""
    out = []
    for a, b in zip(points[joint:], points[joint + 1:]):
        out += [tuple((x + y) / 2.0 for x, y in zip(a, b)), b]
    return out


def nearest(boxes, points):
    """The least signed distance from any of ``points`` to any of ``boxes``."""
    return min(box_distance(box, p) for box in boxes for p in points)


def _sweep(angles, clear):
    """Of ``angles`` (rising), the last one clear before the first contact:
    (angle, True). (None, False) when the whole sweep is clear."""
    free = None
    for angle in angles:
        if clear(angle) < 0.0:
            return free, free is not None
        free = angle
    return None, False


def _steps(lo, hi, step=STEP_DEG):
    return [lo + i * step for i in range(int((hi - lo) / step + 1e-6) + 1)]


def bend(points, axis):
    """How far each of a finger's last two joints is bent already (degrees
    about ``axis``; 0 is straight)."""
    lines = [_unit(_sub(b, a)) for a, b in zip(points, points[1:])]
    return tuple(math.degrees(math.atan2(_dot(_cross(a, b), axis), _dot(a, b)))
                 for a, b in zip(lines, lines[1:]))


def limits(points, axis):
    """((lo, hi) in degrees for each of the three joints): OPEN_DEG back and
    CLOSE_DEG on from the clip's pose, the last two joints never bent back
    past straight nor past BEND_MAX_DEG."""
    out = [(-OPEN_DEG[0], CLOSE_DEG[0])]
    for now, back, on in zip(bend(points, axis), OPEN_DEG[1:], CLOSE_DEG[1:]):
        out.append((min(0.0, max(-back, -now)), max(0.0, min(on, BEND_MAX_DEG - now))))
    return tuple(out)


def riding(points):
    """The points of a finger that are laid on the gun: its two outer joints,
    its tip and the middles of its two outer bones."""
    return beyond(points, 1) + [points[1]]


def misfit(boxes, points, angles=(0.0, 0.0, 0.0)):
    """How badly a finger lies on ``boxes`` with its joints bent by
    ``angles``: the squares of how far each riding point is from a SKIN_CM
    off the nearest box, one nearer than that (pressed in) counted
    _PRESS_WEIGHT times, and a little for every degree off the clip's pose,
    which decides between bends that fit alike."""
    axis = hinge(points)
    at = riding(posed(points, axis, angles)) if axis else riding(points)
    cost = _KEEP_WEIGHT * sum(a * a for a in angles)
    for p in at:
        off = min(box_distance(box, p) for box in boxes) - SKIN_CM
        cost += off * off * (_PRESS_WEIGHT if off < 0.0 else 1.0)
    return cost


def on(boxes, points):
    """How many of a finger's riding points are on ``boxes``: within
    TOUCH_CM of a SKIN_CM off one."""
    return sum(1 for p in riding(points)
               if abs(min(box_distance(box, p) for box in boxes) - SKIN_CM) <= TOUCH_CM)


def close(points, boxes):
    """How a finger closes on ``boxes``: (the three joints' angles in degrees
    from where ``points`` has them, True when it is laid on a box).
    ``points``: its three joints and its tip. The bend whose riding points
    lie best a SKIN_CM off the boxes (misfit), within the joints' limits; a
    finger that even so has fewer than ON_POINTS of them on a box (one past
    the end of the part) is left as the clip has it, and so is a straight
    one."""
    still = (0.0, 0.0, 0.0)
    axis = hinge(points)
    if axis is None or not boxes:
        return still, False
    ranges = limits(points, axis)
    best, cost = still, misfit(boxes, points)
    # Every bend on a coarse grid first: the fit has more than one hollow (a
    # tip laid on the near face, or the finger round the far edge).
    grids = [sorted(set(_steps(0.0, hi, _GRID_DEG)) | {-a for a in _steps(0.0, -lo, _GRID_DEG)})
             for lo, hi in ranges]
    for a in grids[0]:
        for b in grids[1]:
            for c in grids[2]:
                found = misfit(boxes, points, (a, b, c))
                if found < cost - 1e-9:
                    best, cost = (a, b, c), found
    step = _GRID_DEG / 2.0
    while step >= STEP_DEG:
        moved = False
        for joint in range(3):
            for way in (-step, step):
                trial = list(best)
                trial[joint] = min(max(trial[joint] + way, ranges[joint][0]), ranges[joint][1])
                found = misfit(boxes, points, tuple(trial))
                if found < cost - 1e-9:
                    best, cost, moved = tuple(trial), found, True
        if not moved:
            step /= 2.0
    if on(boxes, posed(points, axis, best)) < ON_POINTS:
        return still, False
    return best, True


def swung(points, axis, deg):
    """A thumb's ``points`` swung ``deg`` about ``axis`` through its first."""
    return [points[0]] + [_add(points[0], turned(_sub(p, points[0]), axis, deg))
                          for p in points[1:]]


def swing(points, boxes, ceiling):
    """How a thumb is laid against ``boxes``: (the unit axis through its
    first joint, the degrees it swings about it). ``points``: its three joints
    and its tip. It swings its tip towards the nearest box and stops a
    SKIN_CM off it, or THUMB_CLEAR_CM under ``ceiling`` (a z); a thumb that
    meets neither in THUMB_SWING_DEG stays where it is."""
    still = ((0.0, 0.0, 1.0), 0.0)
    if not boxes:
        return still
    tip = points[-1]
    lo, hi = min(boxes, key=lambda box: box_distance(box, tip))
    on = tuple(min(max(p, l), h) for p, l, h in zip(tip, lo, hi))
    axis = _cross(_sub(tip, points[0]), _sub(on, points[0]))
    if _len(axis) < 1e-6:
        return still
    axis = _unit(axis)

    def clear(angle):
        moved = swung(points, axis, angle)[1:]
        under = ceiling - THUMB_CLEAR_CM - max(p[2] for p in moved)
        return min(nearest(boxes, moved) - SKIN_CM, under)

    if clear(0.0) < 0.0:
        return still
    found, met = _sweep(_steps(0.0, THUMB_SWING_DEG), clear)
    return (axis, found) if met else still
