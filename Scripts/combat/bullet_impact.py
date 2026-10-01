"""BP_BulletImpact: what a bullet knocks off the scenery -- a seeded layout of
chips and dust, and the short-lived actor spawned where a pellet hits anything
that does not bleed (terrain, trees, rocks).
"""

import random

from combat.burst import BURST_VELOCITY_ENCODE, Piece, build_burst, throw
from combat.paths import (
    BULLET_IMPACT_BP_PATH, CUBE, MAT_IMPACT_CHIP, MAT_IMPACT_DUST, SPHERE,
)


# ─── BP_BulletImpact ─────────────────────────────────────────────────────────

IMPACT_SEED = 23           # laid out once, at build time, so it is reproducible
IMPACT_CHIPS = 10          # what the round breaks off: soil, bark, stone
IMPACT_DUST = 6            # fine and slow: the puff left at the hole
# A wound sprays down a channel; a surface shatters. The chips leave much
# wider than blood's 34 degrees, and the dust nearly along the surface.
IMPACT_CONE_DEG = 58.0
IMPACT_DUST_CONE_DEG = 82.0
IMPACT_LIFETIME = 0.60     # long enough for a chip to arc over and start down
IMPACT_FADE_TAIL = 0.18    # the last of the lifetime, spent shrinking to nothing
IMPACT_SPEED_MIN = 110.0   # cm/s -- chips are heavier than droplets and slower
IMPACT_SPEED_MAX = 560.0
# Blood's draw leans fast (0.5): a spray with a few laggards. This leans slow:
# most of what a round breaks off tumbles away and a few chips fly, which is
# also what spreads the speeds (150-494 cm/s; at 0.6 they came out 270-530).
IMPACT_SPEED_BIAS = 1.4
IMPACT_DUST_SPEED_MIN = 20.0
IMPACT_DUST_SPEED_MAX = 120.0
IMPACT_DRAG = 2.6          # 1/s. A chip keeps its speed better than a droplet
IMPACT_GRAVITY = 980.0     # cm/s^2, real gravity as for blood
IMPACT_CHIP_SCALE = (0.010, 0.032)  # 1-3.2 cm chips off a 100 cm cube
IMPACT_DUST_SCALE = (0.008, 0.020)  # 0.8-2 cm
# The actor is spawned at blood's scale (weapon_component/impact.py), a clamp
# on the round's damage, so a sniper round throws a bigger burst than a pellet.


def _impact_pieces():
    """The seeded chips and dust, thrown back along +X, as burst Pieces.

    +X is the actor's forward, and the impact spawns it rotated so that
    forward is the surface normal of whatever the pellet hit: the burst comes
    off the surface, whichever way that faces.

    Chips are cubes, and a cube shows its orientation, so each is built at a
    turn of its own; all of them square to the actor would read as one lattice.
    The turns are drawn after every velocity, so re-tuning a cone or a speed
    never moves them.
    """
    rng = random.Random(IMPACT_SEED)
    chips = [throw(rng, IMPACT_CONE_DEG, IMPACT_SPEED_MIN, IMPACT_SPEED_MAX,
                   *IMPACT_CHIP_SCALE, bias=IMPACT_SPEED_BIAS)
             for _ in range(IMPACT_CHIPS)]
    dust = [throw(rng, IMPACT_DUST_CONE_DEG, IMPACT_DUST_SPEED_MIN,
                  IMPACT_DUST_SPEED_MAX, *IMPACT_DUST_SCALE, bias=1.0)
            for _ in range(IMPACT_DUST)]
    turns = [tuple(round(rng.uniform(-90.0, 90.0), 2) for _ in range(3))
             for _ in range(IMPACT_CHIPS)]
    return tuple(
        [Piece((x, y, z), scale, CUBE, MAT_IMPACT_CHIP, turn)
         for (x, y, z, scale), turn in zip(chips, turns)]
        + [Piece((x, y, z), scale, SPHERE, MAT_IMPACT_DUST)
           for x, y, z, scale in dust])


IMPACT_PIECES = _impact_pieces()


def build_bullet_impact(rebuild=True):
    """Chips and dust thrown off a surface a bullet hit; burst.build_burst flies them.

    Blood's sibling and deliberately so: the same solver, so a round into the
    ground and a round into a wanderer answer in the same visual language, and
    only the stuff differs -- dry, dull, wide and slower here, wet, dark and
    narrow there.
    """
    return build_burst(
        BULLET_IMPACT_BP_PATH, IMPACT_PIECES,
        lifetime=IMPACT_LIFETIME, fade_tail=IMPACT_FADE_TAIL, drag=IMPACT_DRAG,
        gravity=IMPACT_GRAVITY, rebuild=rebuild,
        note=(
            f"{len(IMPACT_PIECES)} pieces -- {IMPACT_CHIPS} chips in a "
            f"{IMPACT_CONE_DEG:.0f} deg cone around the actor's +X, which "
            f"_author_surface_impact points down the surface normal of the hit, "
            f"plus {IMPACT_DUST} slow grains of dust that hang at the hole. Each "
            f"carries its own launch velocity "
            f"({IMPACT_SPEED_MIN:.0f}-{IMPACT_SPEED_MAX:.0f} cm/s) in its "
            f"build-time relative location over {BURST_VELOCITY_ENCODE:.0f}, and "
            f"flies the exact solution of dv/dt = g - {IMPACT_DRAG} v under "
            f"{IMPACT_GRAVITY:.0f} cm/s^2. Flat scale until the last "
            f"{IMPACT_FADE_TAIL}s of {IMPACT_LIFETIME}s, then cut. SetLifeSpan "
            f"removes the actor."))
