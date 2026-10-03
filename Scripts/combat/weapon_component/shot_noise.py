"""The noise a shot makes: the held weapon's ShotVolume all round, and a louder
cone down the aim line, written into the GameMode's noise record.
"""

import math

from uebp.graph import _connect, _node, _pin, _set, out
from combat.noise import _author_make_noise
from combat.nodes import FN_MUL_FF
from combat.tuning import COMBAT
from combat.weapon_component.common import _prop


def _author_shot_noise(ed, held, muzzle, direction, exec_in):
    """After the pellets: make this weapon's noise. Returns the exec to carry on.

    The reach is read off Held, like every other per-weapon number, so the
    sniper is heard across the map and the pistol barely past the next stand
    of trees without anything here knowing which is which (SHOT_VOLUME_CM in
    tuning.py). The cone points the way the pellets flew: ``direction`` is
    _author_fire's own muzzle -> AimPoint pin, not a second copy of it, so a
    shot fired at a pack reaches it from further away than one fired away
    from it.
    """
    volume, volume_n = _prop(ed, "ShotVolume", held)

    ahead = _node(ed, FN_MUL_FF)
    _connect(volume, _pin(ahead, "A"))
    _set(ahead, "B", COMBAT.shot_noise_cone_range_scale)

    made, then = _author_make_noise(
        ed, exec_in, muzzle, volume,
        direction=direction,
        cone_reach=out(ahead),
        cone_cos=math.cos(math.radians(COMBAT.shot_noise_cone_half_angle_deg)))
    ed.add_comment_to_nodes(
        f"The shot's noise: heard all round out to the weapon's ShotVolume, "
        f"and {COMBAT.shot_noise_cone_range_scale}x that inside "
        f"{COMBAT.shot_noise_cone_half_angle_deg:.0f} degrees of the aim line. "
        f"Written to the GameMode for the wanderers to hear.",
        made + [volume_n, ahead])
    return then
