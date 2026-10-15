"""How far apart the crawl's legs lie: the yaw of a leg's segment off the
body's long axis, and how much of it a narrowed copy keeps.  Pure math,
importable outside the editor (narrow_legs.py applies it to a clip).

The Free Animation Library's prone loops lie frog-legged: on the player's
skeleton the feet are 55-63 cm apart and the forward crawl's knee swings out
until the knees are 81 cm apart, over hips 15 cm wide.  Each thigh and calf
is turned about the vertical through its joint so that its angle off the
line behind the hips is LEG_SPREAD of the pack's; heights are untouched, so
nothing that lay on the ground goes into it.
"""

import math

# The share of each leg segment's angle off the body's line the copy keeps.
LEG_SPREAD = 0.55


def yaw_off_back(x, y):
    """Degrees a mesh-space direction (forward +Y, left +X) turns off
    straight back (-Y), positive toward +X."""
    return math.degrees(math.atan2(x, -y))


def narrowed_turn(now, pack, spread=LEG_SPREAD):
    """Degrees to turn a segment that points ``now`` (an (x, y)) about the
    vertical so it lies at ``spread`` of the pack's angle, ``pack`` (x, y).
    Positive turns toward +X from -Y (an Unreal yaw, which turns +X to +Y)."""
    return spread * yaw_off_back(*pack) - yaw_off_back(*now)
