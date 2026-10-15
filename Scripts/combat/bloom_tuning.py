"""The bloom: an automatic gun fired from the hip grows less accurate with
each round of a burst, as the hands start to shake, and settles again soon
after the trigger is let go. Constants only, with the rule in plain Python
for the unit tests; the graph is weapon_component/bloom.py, and the cloud it
widens accuracy.py's.

    a shot (Held.Automatic, NOT SightAiming):
        Bloom = Min(Bloom + BLOOM_PER_SHOT, BLOOM_MAX); BloomShotTime = now
    every frame, once now > BloomShotTime + BLOOM_HOLD_S:
        Bloom = FInterpTo(Bloom, 0, dt, BLOOM_RECOVER_SPEED)
    AimSpread = ... x (1 + Bloom)

Down the sights the cloud is zero whatever Bloom is, and a shot there adds
none: the sights are where the hands are steady.
"""

from uebp.vars import FLOAT, Var

# What one round of a burst adds, as a fraction of the gun's own cloud: the
# SMG (0.09 s a round) is at the cap after 13 rounds, 1.2 s of fire; the
# rifle (0.14 s) after 1.8 s.
BLOOM_PER_SHOT = 0.12
# The cap: the cloud at most 2.5 times the gun's own.
BLOOM_MAX = 1.5
# How long after a round the bloom holds before it settles. Longer than either
# automatic's interval (0.14 s at most), or a burst would settle between its
# own rounds; short enough that a brief stop is felt at once.
BLOOM_HOLD_S = 0.2
# How fast it settles (FInterpTo's speed): ~8% left half a second after the
# hold, a smooth fall rather than a step.
BLOOM_RECOVER_SPEED = 5.0

# The component's variables: the bloom now, and when a round last added to it.
Bloom = Var("Bloom", FLOAT, 0.0)
BloomShotTime = Var("BloomShotTime", FLOAT, 0.0)
TABLE = (Bloom, BloomShotTime)


def bloom_shot(bloom):
    """A round of an automatic, fired from the hip."""
    return min(bloom + BLOOM_PER_SHOT, BLOOM_MAX)


def bloom_rest(bloom, since_shot, dt):
    """One frame of the graph's settling, ``since_shot`` seconds after the
    last round (FInterpTo to zero, as UE's: a step of the rest, clamped)."""
    if since_shot <= BLOOM_HOLD_S:
        return bloom
    return bloom - bloom * min(max(dt * BLOOM_RECOVER_SPEED, 0.0), 1.0)


def spread_scale(bloom):
    """What the cloud is multiplied by."""
    return 1.0 + bloom
