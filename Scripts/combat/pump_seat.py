"""Where the left hand sits on the shotgun's pump: the move that closes its
fingers on the wood, found for whatever hand the worn body has.

Pure (no ``unreal``); shotgun_pose.py calls it and verify/shotgun_pose.py
measures the result with the same pump_distance(). Tests:
dev/tests/test_pump_seat.py.

The shotgun pose turns the left hand under the pump and points each finger
joint where its table says (shotgun_pose.SUPPORT_PALM, SUPPORT_FINGERS). That
fixes the hand's SHAPE; where the hand IS used to be the rifle pose's wrist,
and whether the fingers then met the wood depended on how big the hand was
and where the retargeted wrist happened to be. On the dressed adventurer they
did. On the one in boxers (shorter fingers, the wrist 3 cm off) the middle
finger's tip was 1.9 cm inside the wood and the index's knuckle 4.7 cm off it.

So the hand is moved, as one rigid piece, to where its own joints fit the
pump: every finger joint and tip as near SEAT_OFF_CM from the wood as the
worst of them can be brought, the thumb kept under the barrel's top.
"""

# A finger joint's axis rides this far off the wood: the middle of what the
# verifier allows (1 cm inside to 2.5 cm off), a centimetre of finger.
SEAT_OFF_CM = 0.75
# The thumb's joints stay this far under the barrel's top (the sight line).
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


def misfit(box, joints, move=(0.0, 0.0, 0.0)):
    """How far the worst joint is from riding SEAT_OFF_CM off ``box``, with
    every joint moved by ``move``."""
    return max(abs(box_distance(box, tuple(p + m for p, m in zip(j, move)))
                   - SEAT_OFF_CM) for j in joints)


def seat(box, joints, thumb, ceiling):
    """The move (x, y, z in the weapon's frame) that best fits ``joints`` (the
    fingers' joints and tips) round ``box``, keeping every ``thumb`` point
    under ``ceiling`` (a z). A descent from where the hand is: the nearest
    fit, not the best anywhere on the pump."""
    def allowed(move):
        return (sum(m * m for m in move) ** 0.5 <= SEAT_MAX_MOVE_CM
                and all(p[2] + move[2] < ceiling - THUMB_CLEAR_CM for p in thumb))

    move = (0.0, 0.0, 0.0)
    best = misfit(box, joints, move)
    step = _FIRST_STEP_CM
    while step >= _LAST_STEP_CM:
        found = None
        for axis in _AXES:
            trial = tuple(m + a * step for m, a in zip(move, axis))
            if not allowed(trial):
                continue
            cost = misfit(box, joints, trial)
            if cost < best - 1e-9:
                found, best = trial, cost
        if found is None:
            step /= 2.0
        else:
            move = found
    return move
