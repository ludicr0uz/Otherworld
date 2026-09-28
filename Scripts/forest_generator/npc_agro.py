"""How a wanderer notices the player, and how it passes the time until then.

Constants only -- no `unreal` import -- so the offline generator, the NPC
builder and its verifier all read the same numbers. The builder is
Scripts/npc/ (agro.py, senses.py, patrol.py); the checks are
Scripts/npc/verify.py.

A wanderer starts every life PATROLLING: it strolls about a circle centred on
wherever it spawned, at a fraction of its run speed, and it keeps doing that
until one of four things tells it the player is there:

  hurt    the player damaged it (BP_HealthComponent.DamagedByPlayer)
  sight   the player is inside its vision cone -- within vision_range_cm,
          within vision_half_angle_deg of the way it is facing -- AND it has a
          clear line of sight, so a trunk between the two hides the player
  touch   the player is within touch_range_cm, whichever way it is facing
  sound   it is inside the reach of the most recent noise (see below)

Then it is AGGRO for the rest of its life: the chase-and-swing loop that used
to be all it did. There is no way back to patrolling yet; "lose interest" is
the obvious next dial and would sit in AgroSettings beside these.

WHO DECIDES HOW FAR A NOISE CARRIES
-----------------------------------
The noise does, not the listener. A footstep carries a few metres and a sniper
round carries across the map, and that range is written by whatever made the
noise (combat/noise.py: the player's footsteps from how fast they are moving,
a gunshot from the weapon's ShotVolume). A gunshot also throws a CONE of sound
down the barrel that reaches further than its all-round radius. The listener's
only say is hearing_scale, a multiplier on both: a wendigo with 1.4 hears a
pistol at 1.4x the distance a zombie does.

Per creature, keyed by NpcVariant.key. Adding a creature means adding a row
here; agro_for() raises for a key without one, so a missing row fails the
build rather than quietly giving the new monster someone else's senses.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgroSettings:
    """One creature's senses and patrol. Built upon over time -- add fields."""

    # --- sight ---------------------------------------------------------------
    # A cone, not a circle: something behind a wanderer is not seen, and the
    # player can creep past one that is walking away. Half-angle, so the full
    # field of view is twice this. Checked against the pawn's FACING, which
    # during a patrol is the way it is walking (orient_rotation_to_movement).
    vision_range_cm: float
    vision_half_angle_deg: float
    # --- hearing -------------------------------------------------------------
    # Multiplies the noise's own reach (see the module docstring).
    hearing_scale: float
    # --- touch ---------------------------------------------------------------
    # Standing still right behind one is not a hiding place. Kept short: it is
    # for bumping into a wanderer, not a second, rounder vision.
    touch_range_cm: float
    # --- patrol --------------------------------------------------------------
    # The circle it strolls about, centred where it spawned (a respawn gets a
    # new centre where it respawned).
    patrol_radius_cm: float
    # Of its own run speed, so the wendigo's 1.15x and the per-instance gait
    # still show in a stroll. ~0.3 lands both creatures near 200 cm/s, which
    # the locomotion blend space plays as a walk rather than a slow jog.
    patrol_speed_scale: float
    # How often it picks a new point to walk to, drawn uniformly. It includes
    # the walk itself, so the idle pause at each point is whatever is left.
    patrol_repick_min_s: float
    patrol_repick_max_s: float


NPC_AGRO = {
    # The yardstick. 20 m of sight at night in a dense forest, a normal field
    # of view, normal ears, and a small beat: 15 m, so a pack's members stay
    # roughly where they were put.
    "Zombie": AgroSettings(
        vision_range_cm=2000.0,
        vision_half_angle_deg=50.0,
        hearing_scale=1.0,
        touch_range_cm=250.0,
        patrol_radius_cm=1500.0,
        patrol_speed_scale=0.30,
        patrol_repick_min_s=6.0,
        patrol_repick_max_s=12.0,
    ),
    # The hunter. Sees further and wider, hears better, and ranges over twice
    # the ground -- so it is the one most likely to find the player first, and
    # the one worth hearing coming.
    "Wendigo": AgroSettings(
        vision_range_cm=3500.0,
        vision_half_angle_deg=65.0,
        hearing_scale=1.4,
        touch_range_cm=300.0,
        patrol_radius_cm=3000.0,
        patrol_speed_scale=0.30,
        patrol_repick_min_s=8.0,
        patrol_repick_max_s=16.0,
    ),
}

# A patrol point is accepted only if it lies inside the circle, give or take
# this much. The navigation query's fallback when it finds nothing is the
# centre (fine) or, with no navigation system at all, the world origin -- which
# is the player's spawn. This slack lets a real point through (Recast's point
# can sit a little outside the circle, and the distance is 3D over sloped
# ground) while still rejecting a walk to the origin.
PATROL_ACCEPT_FRACTION = 1.1
PATROL_ACCEPT_SLACK_CM = 200.0

# The line every transition writes, so a -game run can say which sense fired.
AGRO_LOG_PREFIX = "[NPC-AGRO] "


def agro_for(key):
    """The AgroSettings for creature ``key``; raises for a creature with none."""
    try:
        return NPC_AGRO[key]
    except KeyError:
        raise KeyError(f"no AgroSettings for creature {key!r} -- add a row to "
                       f"NPC_AGRO in forest_generator/npc_agro.py") from None
