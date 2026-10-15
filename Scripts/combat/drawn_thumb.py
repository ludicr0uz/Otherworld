"""The drawn right thumb on a pistol: laid forward along the frame's far
side, under the slide, instead of where the retarget leaves it.

drawn_grip.fit_thumb only swings the thumb the retarget gives the drawn
hand, as far as it takes to touch the gun. On the pistol that thumb stands
up behind the slide (its tip 1.4 cm over the slide's top, measured 15 Oct
2026), in front of the rear sight down the sights. A hand round a pistol's
grip has its thumb across the back of the grip, under the slide, and
forward along the frame's left side: lay() puts it there. It turns the
thumb's first bone (the whole thumb about its root) and bends its two outer
joints, so that its tip lies on drawn_grip_consts.THUMB_REST, no point of
it is pressed into the gun or the fitted fingers, and none rises above
THUMB_CEILING (the gun's up).

Pure (no ``unreal``). Tests: dev/tests/test_drawn_thumb.py.
"""

import math

from combat import drawn_grip as D
from combat import finger_fit as F

# The axis the thumb's outer joints bend about, in its middle bone's own
# frame: the plane of the capture's thumbs (finger_fit.hinge) is within 20
# degrees of it on every gun. A bend is searched both ways, so its sign
# only says which way is "curled".
CURL_AXIS = (0.0, 0.0, 1.0)
# How far the search turns the thumb past the turn that points it at its
# rest (degrees, each way: two swings and the roll about that line), and
# how far each outer joint may bend from the capture's pose (open, close).
SWING_DEG = 45.0
ROLL_DEG = 60.0
BEND_DEG = (-20.0, 60.0)
# The coarse grid the search starts from, then halving steps down to
# finger_fit.STEP_DEG (degrees).
GRID_ROLL_DEG = 30.0
GRID_BEND_DEG = 20.0
GRID_SWING_DEG = 15.0
START_STEP_DEG = 8.0
# What a riding point off the gun costs, per cm2 past a skin off it: the
# thumb lies along the frame, not over it (finger_fit.misfit's 1).
LIE_WEIGHT = 1.0
# What a degree of turn off the capture's pose costs (cm2 per degree2, the
# first bone's whole turn and each bend): of poses that fit alike, the
# least turned; a thumb's root turns 60-70 degrees here, not twisted round.
KEEP_WEIGHT = 1e-4
BEND_WEIGHT = 1e-3


def _between(a, b):
    """The least turn (a quat) taking the direction ``a`` to ``b``."""
    a, b = F._unit(a), F._unit(b)
    axis = F._cross(a, b)
    if F._len(axis) < 1e-9:
        return D.IDENTITY[1]
    deg = math.degrees(math.atan2(F._len(axis), F._dot(a, b)))
    return F.quat(F._unit(axis), deg)


def _frame(line):
    """Two unit axes square to ``line`` and to each other."""
    w = F._unit(line)
    other = (1.0, 0.0, 0.0) if abs(w[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = F._unit(F._cross(w, other))
    return u, F._cross(w, u)


class _Thumb:
    """A thumb's points and the turns lay() searches, in the hand's frame."""

    def __init__(self, locals_, bones, rest):
        self.xfs = D.placed(locals_, bones)
        self.pts = D.points(self.xfs, D.THUMB_TIP_CM)
        root = self.pts[0]
        mid = F.aimed(rest, tuple((a + b) / 2.0 for a, b in zip(*rest)))
        line = F._sub(mid, root)
        self.base = _between(F._sub(self.pts[-1], root), line)
        self.roll = F._unit(line)
        self.u, self.v = _frame(line)
        self.curl = D._turn(self.xfs[1][1], CURL_AXIS)

    def swing(self, params):
        """The quat the thumb's first bone is turned by."""
        yaw, pitch, roll = params[:3]
        q = D._mul(F.quat(self.roll, roll), self.base)
        q = D._mul(F.quat(self.v, pitch), q)
        return D._norm_q(D._mul(F.quat(self.u, yaw), q))

    def posed(self, params):
        """The thumb's points: swung about its root, its outer joints bent."""
        q, root = self.swing(params), self.pts[0]
        swung = [root] + [F._add(root, D._turn(q, F._sub(p, root))) for p in self.pts[1:]]
        return F.posed(swung, D._turn(q, self.curl), (0.0,) + tuple(params[3:]))

    def rots(self, params):
        """Each bone's placed rotation (hand frame) for ``params``."""
        q = self.swing(params)
        axis = D._turn(q, self.curl)
        out, total = [], 0.0
        for xf, bend in zip(self.xfs, (0.0,) + tuple(params[3:])):
            total += bend
            out.append(D._norm_q(D._mul(F.quat(axis, total), D._mul(q, xf[1]))))
        return out


def misfit(thumb, params, solid, rest, height, ceiling):
    """How badly the thumb lies at ``params``: its tip's square distance off
    ``rest`` (finger_fit.AIM_WEIGHT per cm2), each riding point's off a skin
    off ``solid`` (LIE_WEIGHT; drawn_grip.PRESS_WEIGHT pressed in), each point whose skin rises past ``ceiling`` (``height``
    of a point, cm) drawn_grip.PRESS_WEIGHT per cm2, and a little per degree."""
    pts = thumb.posed(params)
    tip = pts[-1]
    cost = F.AIM_WEIGHT * sum(d * d for d in F._sub(tip, F.aimed(rest, tip)))
    for p in F.riding(pts):
        pressed = F.SKIN_CM - solid.distance(p)
        cost += (D.PRESS_WEIGHT if pressed > 0.0 else LIE_WEIGHT) * pressed * pressed
    for p in pts[1:] + F.riding(pts):
        over = height(p) + F.SKIN_CM - ceiling
        if over > 0.0:
            cost += D.PRESS_WEIGHT * over * over
    turn = math.degrees(2.0 * math.acos(min(1.0, abs(thumb.swing(params)[3]))))
    return cost + KEEP_WEIGHT * turn * turn + BEND_WEIGHT * sum(a * a for a in params[3:])


def _ranges():
    return ((-SWING_DEG, SWING_DEG), (-SWING_DEG, SWING_DEG), (-ROLL_DEG, ROLL_DEG),
            BEND_DEG, BEND_DEG)


def _grid(lo, hi, step):
    n = int(round((hi - lo) / step))
    return [lo + i * step for i in range(n + 1)]


def search(cost_of):
    """The params (yaw, pitch, roll, bend, bend) within _ranges() that cost
    least: every one of a coarse grid, then each on its own in halving
    steps."""
    ranges = _ranges()
    grids = (_grid(-SWING_DEG, SWING_DEG, GRID_SWING_DEG),
             _grid(-SWING_DEG, SWING_DEG, GRID_SWING_DEG),
             _grid(-ROLL_DEG, ROLL_DEG, GRID_ROLL_DEG),
             _grid(0.0, BEND_DEG[1], GRID_BEND_DEG),
             _grid(0.0, BEND_DEG[1], GRID_BEND_DEG))
    best, cost = (0.0,) * 5, cost_of((0.0,) * 5)
    for yaw in grids[0]:
        for pitch in grids[1]:
            for roll in grids[2]:
                for b1 in grids[3]:
                    for b2 in grids[4]:
                        trial = (yaw, pitch, roll, b1, b2)
                        found = cost_of(trial)
                        if found < cost - 1e-9:
                            best, cost = trial, found
    step = START_STEP_DEG
    while step >= F.STEP_DEG:
        moved = False
        for i in range(5):
            for way in (-step, step):
                trial = list(best)
                trial[i] = min(max(trial[i] + way, ranges[i][0]), ranges[i][1])
                found = cost_of(tuple(trial))
                if found < cost - 1e-9:
                    best, cost, moved = tuple(trial), found, True
        if not moved:
            step /= 2.0
    return best, cost


def lay(locals_, bones, solid, rest, height, ceiling):
    """(new locals of the thumb's ``bones``, the params found): its tip on
    ``rest`` (a segment of the hand's frame), clear of ``solid`` (the hand's
    frame) and under ``ceiling`` by ``height`` (hand-frame point -> cm up
    the gun)."""
    thumb = _Thumb(locals_, bones, rest)
    params, _cost = search(lambda q: misfit(thumb, q, solid, rest, height, ceiling))
    return D._turned(locals_, thumb.xfs, bones, thumb.rots(params)), params


def top(locals_, bones, height):
    """The highest any point of the thumb rises, by ``height`` (cm)."""
    pts = D.points(D.placed(locals_, bones), D.THUMB_TIP_CM)
    return max(height(p) for p in pts[1:] + F.riding(pts))
