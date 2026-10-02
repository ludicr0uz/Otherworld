"""How a thrown blade sits in the tree it lodged in, worked out of its model.

The flight ends by turning the item so that its own +X runs along the throw
(weapon_component/throw_strike.py), after a turn of its own about its level Y
axis. That turn, LodgeTurn, is the one that takes what goes into the wood
(the knife's blade, the axe's bit) onto +X; LodgePoint is the point of the
item's frame that then sits on the bark, ``depth_cm`` behind the tip or the
bit. Both are per item defaults (knife.knife_lodge, axe.axe_lodge).
"""

import math

import unreal

from combat.graph import _rot
from combat.grip import _rotate_vector


def lodge_pose(along, lead, depth_cm):
    """(LodgeTurn, LodgePoint) for an item whose ``along`` (a direction in
    its own frame, in the X-Z plane every melee model's blade lies in) goes
    into the wood, ``lead`` (a point of that frame: the tip, the bit) first
    and ``depth_cm`` deep.

    The pitch's sign is found by testing, as knife.blade_rotation's is, not
    argued from rotator handedness."""
    a = unreal.Vector(along.x, along.y, along.z).normal()
    if abs(a.y) > 0.01:
        raise RuntimeError(f"{a} is not in the item's X-Z plane")
    deg = math.degrees(math.atan2(a.z, a.x))
    for pitch in (-deg, deg):
        if _rotate_vector(_rot(pitch=pitch), a).x > 0.999:
            return _rot(pitch=pitch), unreal.Vector(lead[0] - a.x * depth_cm,
                                                    lead[1] - a.y * depth_cm,
                                                    lead[2] - a.z * depth_cm)
    raise RuntimeError(f"no pitch turns {a} onto +X")
