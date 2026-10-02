"""A sprint is allowed only forwards: within 60 degrees of the way the player faces.

No key can be injected into a headless game, so Sprinting itself stays down
for the whole run (verify/sprint.py checks that it needs SprintAhead). What
the game can show is SprintAhead, the stored answer to "is the player steering
into the cone?": the probe steers the pawn each frame at an angle off its own
forward and reads the flag back.
"""

import math

from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_AHEAD_VAR, SPRINT_CONE_HALF_ANGLE_DEG

FRAMES = 6
# Degrees off forward (positive is to the right), and whether a sprint may run.
CASES = [("forward", 0.0, True), ("forward-right, a keyboard's diagonal", 45.0, True),
         ("forward-left", -45.0, True), ("just inside the cone", 55.0, True),
         ("just outside it", 65.0, False), ("just outside, to the left", -65.0, False),
         ("right", 90.0, False), ("left", -90.0, False),
         ("back-right", 135.0, False), ("backwards", 180.0, False)]


def _steer(pawn, degrees):
    import unreal
    yaw = math.radians(pawn.get_actor_rotation().yaw + degrees)
    pawn.add_movement_input(unreal.Vector(math.cos(yaw), math.sin(yaw), 0.0), 1.0, False)


def probe(p):
    yield 0.2
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    p.check("the cone is 60 degrees either side of forward",
            SPRINT_CONE_HALF_ANGLE_DEG == 60.0, str(SPRINT_CONE_HALF_ANGLE_DEG))
    yield 0.0
    p.check("standing still is not steering ahead", not p.get(wc, SPRINT_AHEAD_VAR))

    for label, degrees, allowed in CASES:
        seen = []
        for _ in range(FRAMES):
            _steer(pawn, degrees)
            yield 0.0
            seen.append(bool(p.get(wc, SPRINT_AHEAD_VAR)))
        # The first frames may still hold the last case's input: read the tail.
        p.check(f"steering {label} ({degrees:+.0f} deg) "
                f"{'may' if allowed else 'may not'} sprint",
                all(a == allowed for a in seen[2:]), str(seen))

    for _ in range(FRAMES):
        yield 0.0
    p.check("letting go of the stick ends it", not p.get(wc, SPRINT_AHEAD_VAR))
    p.check("no key was held, so the player never sprinted",
            not p.get(wc, "Sprinting"))
