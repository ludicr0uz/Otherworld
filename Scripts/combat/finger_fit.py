"""How far each finger bends to rest on a gun: the angles that close a
finger's three joints onto a solid, and the swing that lays a thumb against
it.

A solid is anything with distance(p) (signed, cm, negative inside) and
toward(p) (the nearest point of its surface): Boxes, the outline's parts the
mannequin's fit uses (finger_pose.py; a plain list of boxes is taken as
Boxes); the gun's own mesh, which the drawn hand's fit reads
(drawn_grip_bake.py); Capsules, fingers already closed; a Union of them.

Pure (no ``unreal``); finger_pose.py calls it for every finger of a gun whose
fingers are fitted and keys the answer into that gun's ready clip,
drawn_grip.py for the MetaHuman's hand on the real mesh, and
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
    finger past the end of a handguard is not made into a fist), unless
    that pose presses it into the gun: then it takes the least bend that
    lifts it out (a fallback to a pose inside the gun was a finger through
    it);
  - a trigger finger is drawn to a place instead (close()'s ``aim``), the
    pad of its last bone on the trigger, and only kept out of the gun.

(Closing the knuckle until something touches, then the next joint, was tried
first: the tip of an opened finger touches before the finger is round the
part, and the outer joints then cannot move.)

The thumb does not curl round a part; it is laid against it: one swing at
its base towards the nearest point of the solid (swing()), stopped on
contact or under a ceiling (the sight line). A thumb that starts inside
swings out the same way, the least that clears it.

The points laid on the gun are all six of riding(): the three joints past
the knuckle, the tip and each bone's middle (the first bone's middle was
once left out, and it went through grips unseen).

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
# and a finger is fitted when this many of its six are.
TOUCH_CM = 0.3
ON_POINTS = 2
# A point pressed into the gun weighs this many times one as far off it; a
# degree off the clip's pose weighs this much (cm2 per degree2).
_PRESS_WEIGHT = 4.0
_KEEP_WEIGHT = 1e-5
_GRID_DEG = 5.0
# A finger drawn to a place (misfit's ``aim``: the trigger finger's pad on
# the trigger) weighs this per cm2 off it.
AIM_WEIGHT = 4.0
# The thumb's swing at its base (degrees), and how far under the ceiling its
# points stay (hand_seat.THUMB_CLEAR_CM is the seat's).
THUMB_SWING_DEG = 40.0
THUMB_CLEAR_CM = 0.3
# A finger straighter than this (the sine of its bend, summed over its two
# joints) has no plane of its own to bend in.
_STRAIGHT = 0.05


class Boxes:
    """A solid of boxes ((lo), (hi)), every one in the weapon's frame: the
    outline's parts (hand_seat.box_distance)."""

    def __init__(self, boxes):
        self.boxes = list(boxes)

    def __bool__(self):
        return bool(self.boxes)

    def distance(self, p):
        """Signed (cm): negative inside a box."""
        return min(box_distance(box, p) for box in self.boxes)

    def toward(self, p):
        """The nearest point of the nearest box's surface."""
        lo, hi = min(self.boxes, key=lambda box: box_distance(box, p))
        if box_distance((lo, hi), p) > 0.0:
            return tuple(min(max(x, l), h) for x, l, h in zip(p, lo, hi))
        gaps = [(x - l, i, l) for i, (x, l) in enumerate(zip(p, lo))]
        gaps += [(h - x, i, h) for i, (x, h) in enumerate(zip(p, hi))]
        _gap, axis, face = min(gaps)
        return tuple(face if i == axis else x for i, x in enumerate(p))


class Union:
    """Several solids as one: a gun and the fingers already on it."""

    def __init__(self, solids):
        self.solids = [as_solid(s) for s in solids if s]

    def __bool__(self):
        return bool(self.solids)

    def distance(self, p):
        return min(s.distance(p) for s in self.solids)

    def toward(self, p):
        return min(self.solids, key=lambda s: s.distance(p)).toward(p)


class Capsules:
    """Bones as a solid: each (a, b) segment with its skin, ``radius`` round
    its axis (the fingers of a closed fist, which the other hand's lie on)."""

    def __init__(self, segments, radius=SKIN_CM):
        self.segments, self.radius = list(segments), radius

    def __bool__(self):
        return bool(self.segments)

    def _foot(self, a, b, p):
        ab = _sub(b, a)
        t = _dot(_sub(p, a), ab) / max(_dot(ab, ab), 1e-12)
        return _add(a, tuple(x * min(max(t, 0.0), 1.0) for x in ab))

    def distance(self, p):
        return min(_len(_sub(p, self._foot(a, b, p))) for a, b in self.segments) - self.radius

    def toward(self, p):
        foot = min((self._foot(a, b, p) for a, b in self.segments),
                   key=lambda f: _len(_sub(p, f)))
        way = _sub(p, foot)
        n = _len(way)
        return foot if n < 1e-9 else _add(foot, tuple(x * self.radius / n for x in way))


def as_solid(solid):
    """``solid`` as a solid: one with distance() and toward() is one; a list
    of boxes is made Boxes."""
    return solid if hasattr(solid, "distance") else Boxes(solid or ())


def through(support):
    """True when what the left hand holds (a row's ``support``) is a part of
    the outline itself, not a box measured out of one nor the right fist:
    every part that shares its volume is then model too, running through it
    (a shotgun's tube and barrel through its pump), and a finger past the
    part's end may lie on them."""
    return "part" in support and "box" not in support and not support.get("fist")


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


def nearest(solid, points):
    """The least signed distance from any of ``points`` to ``solid`` (a
    solid or a list of boxes)."""
    solid = as_solid(solid)
    return min(solid.distance(p) for p in points)


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


def limits(points, axis, reach=(OPEN_DEG, CLOSE_DEG)):
    """((lo, hi) in degrees for each of the three joints): OPEN_DEG back and
    CLOSE_DEG on from the clip's pose (``reach``: another pair of the
    two), the last two joints never bent back
    past straight nor past BEND_MAX_DEG."""
    opening, closing = reach
    out = [(-opening[0], closing[0])]
    for now, back, on in zip(bend(points, axis), opening[1:], closing[1:]):
        out.append((min(0.0, max(-back, -now)), max(0.0, min(on, BEND_MAX_DEG - now))))
    return tuple(out)


def riding(points):
    """The points of a finger that are laid on the gun: its three joints past
    the knuckle and its tip, and the middle of each of its three bones."""
    return beyond(points, 0)


def misfit(solid, points, angles=(0.0, 0.0, 0.0), aim=None, reach=True, axis=None,
           press=_PRESS_WEIGHT):
    """How badly a finger lies on ``solid`` with its joints bent by
    ``angles``: the squares of how far each riding point is from a SKIN_CM
    off the solid, one nearer than that (pressed in) counted ``press``
    times (_PRESS_WEIGHT), and a little for every degree off the clip's pose, which decides
    between bends that fit alike. ``reach`` False counts only the points
    pressed in (the least bend that lifts a finger out). ``aim``, (which
    riding point, where): that point drawn to that place, AIM_WEIGHT per cm2,
    the others counted only where pressed in (a trigger finger, through a
    guard, on the trigger); the place may be a segment, (a, b), and the
    point is drawn to its nearest point of it. ``axis``: the one the finger
    bends about, when not the plane of its points (hinge())."""
    solid = as_solid(solid)
    axis = axis or hinge(points)
    at = riding(posed(points, axis, angles)) if axis else riding(points)
    cost = _KEEP_WEIGHT * sum(a * a for a in angles)
    for p in at:
        off = solid.distance(p) - SKIN_CM
        if off < 0.0:
            cost += off * off * press
        elif reach and aim is None:
            cost += off * off
    if aim is not None:
        which, where = aim
        off = _sub(at[which], aimed(where, at[which]))
        cost += AIM_WEIGHT * _dot(off, off)
    return cost


def aimed(where, p):
    """The point of ``where`` (a point, or a segment (a, b)) nearest ``p``."""
    if len(where) == 2 and hasattr(where[0], "__len__"):
        a, b = where
        ab = _sub(b, a)
        t = _dot(_sub(p, a), ab) / max(_dot(ab, ab), 1e-12)
        return _add(a, tuple(x * min(max(t, 0.0), 1.0) for x in ab))
    return tuple(where)


def on(solid, points):
    """How many of a finger's riding points are on ``solid``: within
    TOUCH_CM of a SKIN_CM off it."""
    solid = as_solid(solid)
    return sum(1 for p in riding(points)
               if abs(solid.distance(p) - SKIN_CM) <= TOUCH_CM)


def pressed(solid, points):
    """True when a riding point of the finger is nearer ``solid`` than a
    SKIN_CM less TOUCH_CM: its skin is in the gun."""
    solid = as_solid(solid)
    return any(solid.distance(p) < SKIN_CM - TOUCH_CM for p in riding(points))


def _search(points, cost_of, ranges):
    """The bend within ``ranges`` that costs least: every bend on a coarse
    grid first (the fit has more than one hollow: a tip laid on the near
    face, or the finger round the far edge), then each joint on its own in
    halving steps."""
    best = (0.0, 0.0, 0.0)
    cost = cost_of(best)
    grids = [sorted(set(_steps(0.0, hi, _GRID_DEG)) | {-a for a in _steps(0.0, -lo, _GRID_DEG)})
             for lo, hi in ranges]
    for a in grids[0]:
        for b in grids[1]:
            for c in grids[2]:
                found = cost_of((a, b, c))
                if found < cost - 1e-9:
                    best, cost = (a, b, c), found
    step = _GRID_DEG / 2.0
    while step >= STEP_DEG:
        moved = False
        for joint in range(3):
            for way in (-step, step):
                trial = list(best)
                trial[joint] = min(max(trial[joint] + way, ranges[joint][0]), ranges[joint][1])
                found = cost_of(tuple(trial))
                if found < cost - 1e-9:
                    best, cost, moved = tuple(trial), found, True
        if not moved:
            step /= 2.0
    return best


def close(points, solid, aim=None, axis=None, reach=(OPEN_DEG, CLOSE_DEG),
          press=_PRESS_WEIGHT, on_points=ON_POINTS):
    """How a finger closes on ``solid``: (the three joints' angles in degrees
    from where ``points`` has them, True when it is laid on the solid).
    ``points``: its three joints and its tip. The bend whose riding points
    lie best a SKIN_CM off the solid (misfit), within the joints' limits. A
    finger that even so has fewer than ON_POINTS of them on it (one past the
    end of the part) is left as the clip has it, unless the clip's pose
    presses it into the gun: then it takes the least bend that lifts it
    out. A straight finger is left as it is, unless given the ``axis`` it
    bends about (its joint's own: the plane of a straight finger's points is
    noise). ``aim``: misfit's; a finger drawn to a place is laid there
    whether or not it touches. ``reach``: limits()'; ``press``: misfit()'s;
    ``on_points``: how many riding points make it laid on (ON_POINTS)."""
    still = (0.0, 0.0, 0.0)
    solid = as_solid(solid)
    axis = axis or hinge(points)
    if axis is None or not solid:
        return still, False
    ranges = limits(points, axis, reach)
    best = _search(points, lambda angles: misfit(solid, points, angles, aim, axis=axis,
                                                 press=press), ranges)
    if aim is not None:
        return best, True
    if on(solid, posed(points, axis, best)) >= on_points:
        return best, True
    if not pressed(solid, points):
        return still, False
    return _search(points, lambda angles: misfit(solid, points, angles, reach=False, axis=axis,
                                                 press=press), ranges), False


def wrapped(fingers, solid):
    """A fist closed on ``solid``: the points of every finger of ``fingers``
    (each its three joints and its tip) as close() lays it on it, one after
    another in one list; a finger close() leaves is where it was. What the
    other hand closes over in a pistol's hold."""
    out = []
    for points in fingers:
        angles, _met = close(points, solid)
        out += posed(points, hinge(points), angles) if any(angles) else list(points)
    return out


def swung(points, axis, deg):
    """A thumb's ``points`` swung ``deg`` about ``axis`` through its first."""
    return [points[0]] + [_add(points[0], turned(_sub(p, points[0]), axis, deg))
                          for p in points[1:]]


def swing(points, solid, ceiling=None):
    """How a thumb is laid against ``solid``: (the unit axis through its
    first joint, the degrees it swings about it). ``points``: its three joints
    and its tip. It swings its tip towards the nearest point of the solid and
    stops a SKIN_CM off it, or THUMB_CLEAR_CM under ``ceiling`` (a z, None
    for none); a thumb that meets neither in THUMB_SWING_DEG stays where it
    is. A thumb the clip has pressed into the gun swings the same way (the
    nearest point of the surface is the way out) and stops as soon as it is
    clear; failing that, back the other way."""
    still = ((0.0, 0.0, 1.0), 0.0)
    solid = as_solid(solid)
    if not solid:
        return still
    tip = points[-1]
    axis = _cross(_sub(tip, points[0]), _sub(solid.toward(tip), points[0]))
    if _len(axis) < 1e-6:
        return still
    axis = _unit(axis)

    def clear(angle):
        moved = swung(points, axis, angle)[1:]
        off = nearest(solid, moved) - SKIN_CM
        if ceiling is None:
            return off
        return min(off, ceiling - THUMB_CLEAR_CM - max(p[2] for p in moved))

    if clear(0.0) < 0.0:
        for way in (1.0, -1.0):
            out = next((way * a for a in _steps(0.0, THUMB_SWING_DEG) if clear(way * a) >= 0.0),
                       None)
            if out is not None:
                return axis, out
        return still
    found, met = _sweep(_steps(0.0, THUMB_SWING_DEG), clear)
    return (axis, found) if met else still
