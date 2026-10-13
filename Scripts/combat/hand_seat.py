"""Where the left hand sits on a gun: the move that closes its fingers on the
part it holds (a pump, a handguard, the fist on a pistol's grip), found for
whatever hand the worn body has.

Pure (no ``unreal``); gun_hold.py calls it for every gun and verify/gun_hold.py
measures the result with the same box_distance(). Tests:
dev/tests/test_hand_seat.py. (Until the hands were fitted to every gun this
was pump_seat.py, the shotgun's alone.)

The hand's SHAPE is the ready pose's; where the hand IS used to be the pose's
wrist, and whether the fingers then met the gun depended on the gun, on how
big the hand was and on where the retargeted wrist happened to be. On the
dressed adventurer the shotgun's did. On the one in boxers (shorter fingers,
the wrist 3 cm off) the middle finger's tip was 1.9 cm inside the wood and the
index's knuckle 4.7 cm off it; and the rifle pose held under an AK hung the
whole hand 2 to 7 cm under the handguard, a knuckle in the magazine.

So the hand is moved, as one rigid piece, to where its own joints fit the
part: every finger joint and tip as near SEAT_OFF_CM from it as the worst of
them can be brought, the thumb kept under a ceiling (the sight line), no
joint in a part beside it, and the wrist no further than the arm reaches
(the IK that carries the hand there does not stretch the arm).
"""

# A finger joint's axis rides this far off the wood: the middle of what the
# verifier allows (1 cm inside to 2.5 cm off), a centimetre of finger.
SEAT_OFF_CM = 0.75
# A joint's axis deeper in the part than SEAT_SINK_CM is what the seat gets
# rid of first: each centimetre past it counts as _SINK_WEIGHT off the seat.
# A fingertip in the wood shows; a knuckle a centimetre further off does not.
# (The worst joint alone decides the seat, so without this a hand too wide for
# its part was slid sideways until a tip was as deep in as a knuckle was far
# off: 1.1 cm into the pump.)
SEAT_SINK_CM = 0.5
_SINK_WEIGHT = 10.0
# The thumb's joints stay this far under the ceiling (the sight line).
THUMB_CLEAR_CM = 0.3
# The search: steps from the first to the last, halving; and how far the hand
# may be moved in all.
_FIRST_STEP_CM, _LAST_STEP_CM = 2.0, 0.02
SEAT_MAX_MOVE_CM = 12.0
# The axes first, so a move that one axis makes is made along it alone; then
# the diagonals, which a worst-joint cost needs (it has creases no single axis
# crosses).
_AXES = tuple(sorted(((x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1)
                      for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)),
                     key=lambda a: (sum(abs(c) for c in a), a)))


def box_distance(box, point):
    """Signed distance from a point to a box ((lo), (hi)): negative inside."""
    lo, hi = box
    d = [max(l - p, p - h) for p, l, h in zip(point, lo, hi)]
    out = sum(max(x, 0.0) ** 2 for x in d) ** 0.5
    return out if out > 0.0 else max(d)


def bounding(points):
    """The box ((lo), (hi)) round ``points``."""
    return (tuple(min(p[i] for p in points) for i in range(3)),
            tuple(max(p[i] for p in points) for i in range(3)))


def union(a, b):
    """The box round two boxes."""
    return (tuple(min(p, q) for p, q in zip(a[0], b[0])),
            tuple(max(p, q) for p, q in zip(a[1], b[1])))


def grown(box, by):
    """``box`` with every face moved out by ``by`` cm."""
    return (tuple(c - by for c in box[0]), tuple(c + by for c in box[1]))


def overlaps(a, b):
    """True when two boxes share a volume (touching faces do not)."""
    return all(al < bh and bl < ah for al, ah, bl, bh in zip(a[0], a[1], b[0], b[1]))


def crowding(obstacles, joints, move=(0.0, 0.0, 0.0)):
    """How far the worst joint is from standing SEAT_OFF_CM clear of every
    box of ``obstacles`` (the parts beside the one held), with every joint
    moved by ``move``: 0 when all are clear."""
    return max((SEAT_OFF_CM - box_distance(box, tuple(p + m for p, m in zip(j, move)))
                for box in obstacles for j in joints), default=0.0)


def _off_seat(distance):
    return (abs(distance - SEAT_OFF_CM)
            + _SINK_WEIGHT * max(0.0, -SEAT_SINK_CM - distance))


def misfit(box, joints, move=(0.0, 0.0, 0.0), obstacles=()):
    """How far the worst joint is from riding SEAT_OFF_CM off ``box``, with
    every joint moved by ``move`` (one deeper in than SEAT_SINK_CM counted
    far worse); or, when it is worse, how far the worst
    is from standing clear of ``obstacles`` (crowding)."""
    fit = max(_off_seat(box_distance(box, tuple(p + m for p, m in zip(j, move))))
              for j in joints)
    return max(fit, crowding(obstacles, joints, move)) if obstacles else fit


def reached(move, reach):
    """``move`` as an arm can make it: with ``reach`` ((the shoulder, the
    wrist, the arm's length)) a move that would put the wrist further from
    the shoulder than the arm is long is cut short along the line from the
    shoulder, which is where an IK that does not stretch leaves the hand."""
    if reach is None:
        return move
    shoulder, wrist, arm = reach
    out = tuple(w + m - s for w, m, s in zip(wrist, move, shoulder))
    far = sum(c * c for c in out) ** 0.5
    if far <= arm:
        return move
    return tuple(s + c * arm / far - w for s, c, w in zip(shoulder, out, wrist))


def seat(box, joints, thumb, ceiling, obstacles=(), reach=None):
    """The move (x, y, z in the weapon's frame) that best fits ``joints`` (the
    fingers' joints and tips) round ``box``, keeping every ``thumb`` point
    under ``ceiling`` (a z) and the joints out of ``obstacles`` (boxes). With
    ``reach`` every move is taken as the arm can make it (reached()), so the
    fit is of the hand where it will be, and the move returned is one the
    arm reaches. A descent from where the hand is: the nearest fit, not the
    best anywhere on the part."""
    def allowed(move, made):
        return (sum(m * m for m in move) ** 0.5 <= SEAT_MAX_MOVE_CM
                and all(p[2] + made[2] < ceiling - THUMB_CLEAR_CM for p in thumb))

    move = (0.0, 0.0, 0.0)
    best = misfit(box, joints, reached(move, reach), obstacles)
    step = _FIRST_STEP_CM
    while step >= _LAST_STEP_CM:
        found = None
        for axis in _AXES:
            trial = tuple(m + a * step for m, a in zip(move, axis))
            made = reached(trial, reach)
            if not allowed(trial, made):
                continue
            cost = misfit(box, joints, made, obstacles)
            if cost < best - 1e-9:
                found, best = trial, cost
        if found is None:
            step /= 2.0
        else:
            move = found
    return reached(move, reach)
