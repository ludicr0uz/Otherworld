"""BP_BloodSplash: the droplet and mist layout (seeded, reproducible) and the
short-lived actor spawned at each impact.
"""

import random

from combat.burst import BURST_VELOCITY_ENCODE, Piece, build_burst, throw
from combat.paths import BLOOD_BP_PATH, MAT_BLOOD, SPHERE


# ─── BP_BloodSplash ──────────────────────────────────────────────────────────

BLOOD_SEED = 7             # laid out once, at build time, so it is reproducible
BLOOD_DROPLETS = 14        # the fast spray
BLOOD_MIST = 5             # fine, slow, near the wound: what is left hanging
BLOOD_CONE_DEG = 34.0      # spray half-angle around the surface normal
BLOOD_MIST_CONE_DEG = 72.0 # the haze is not directional in the way the spray is
BLOOD_LIFETIME = 0.45      # punctuation, not a fountain
BLOOD_FADE_TAIL = 0.14     # the last of the lifetime, spent shrinking to nothing
BLOOD_SPEED_MIN = 140.0    # cm/s -- the laggards
BLOOD_SPEED_MAX = 900.0    # cm/s -- the leading edge of the spray
BLOOD_MIST_SPEED_MIN = 25.0
BLOOD_MIST_SPEED_MAX = 90.0
BLOOD_DRAG = 3.6           # 1/s. Air drag on a 2 mm droplet, near enough
BLOOD_GRAVITY = 980.0      # cm/s^2, real gravity and not a stylised fraction
BLOOD_DROP_SCALE = (0.010, 0.030)   # 1-3 cm droplets off a 100 cm sphere
BLOOD_MIST_SCALE = (0.005, 0.011)   # 0.5-1.1 cm
# Each droplet's launch velocity is baked into its build-time location, over
# this (burst.py says why).
BLOOD_VELOCITY_ENCODE = BURST_VELOCITY_ENCODE
# Damage the spray is sized against. Shotgun pellets are 18 each and there are
# eight of them; the sniper is one large number. Clamped either side so no
# weapon can produce either a mist or a fire hose.
BLOOD_REFERENCE_DAMAGE = 24.0
BLOOD_SCALE_MIN = 0.65
BLOOD_SCALE_MAX = 1.60


def _blood_blobs():
    """A seeded spray of droplet velocities, thrown back along +X.

    +X is the actor's forward, and _author_impact spawns the splash rotated so
    that forward *is* the surface normal of whatever the pellet hit. So the
    spray comes out of the wound rather than out of an arbitrary world axis,
    and a shot to the chest and a shot to the back throw blood opposite ways.

    Each tuple is (x, y, z, scale) where x/y/z is the droplet's launch velocity
    over BLOOD_VELOCITY_ENCODE -- see that constant for why the velocity lives
    in the location.

    Seeded rather than authored by hand: the shape wanted here is "irregular",
    which a person writing tuples produces badly and a seed produces for free --
    and a fixed seed keeps it reproducible, so the verifier can recompute the
    same layout and compare it against the saved components.
    """
    rng = random.Random(BLOOD_SEED)
    blobs = []
    for _ in range(BLOOD_DROPLETS):
        blobs.append(throw(rng, BLOOD_CONE_DEG, BLOOD_SPEED_MIN, BLOOD_SPEED_MAX,
                           *BLOOD_DROP_SCALE, bias=0.5))
    for _ in range(BLOOD_MIST):
        blobs.append(throw(rng, BLOOD_MIST_CONE_DEG, BLOOD_MIST_SPEED_MIN,
                           BLOOD_MIST_SPEED_MAX, *BLOOD_MIST_SCALE, bias=1.0))
    return tuple(blobs)


BLOOD_BLOBS = _blood_blobs()


def build_blood_splash(rebuild=True):
    """Small dark droplets thrown out of the wound under drag and real gravity.

    The flight is burst.build_burst's (and so is why this is not Niagara): each
    droplet has its own launch velocity, so they separate as they fly. That
    separation is most of what the old version was missing. It threw ten
    spheres as one rigid cone at a single speed and swelled them on a sine to
    35 cm across, which is a cartoon for three separate reasons -- one speed,
    one shape, and blood does not inflate.
    """
    return build_burst(
        BLOOD_BP_PATH,
        [Piece((x, y, z), scale, SPHERE, MAT_BLOOD)
         for x, y, z, scale in BLOOD_BLOBS],
        lifetime=BLOOD_LIFETIME, fade_tail=BLOOD_FADE_TAIL, drag=BLOOD_DRAG,
        gravity=BLOOD_GRAVITY, rebuild=rebuild,
        note=(
            f"{len(BLOOD_BLOBS)} droplets -- {BLOOD_DROPLETS} of spray in a "
            f"{BLOOD_CONE_DEG:.0f} deg cone around the actor's +X, which "
            f"_author_impact points down the surface normal of the hit, plus "
            f"{BLOOD_MIST} slow fine ones that hang at the wound. Each carries its "
            f"own launch velocity ({BLOOD_SPEED_MIN:.0f}-{BLOOD_SPEED_MAX:.0f} cm/s) "
            f"in its build-time relative location over {BLOOD_VELOCITY_ENCODE:.0f}, "
            f"and flies the exact solution of dv/dt = g - {BLOOD_DRAG} v under "
            f"{BLOOD_GRAVITY:.0f} cm/s^2 -- two scalars for the burst, one "
            f"multiply-add each. Flat scale until the last {BLOOD_FADE_TAIL}s of "
            f"{BLOOD_LIFETIME}s, then cut. SetLifeSpan removes the actor."))
