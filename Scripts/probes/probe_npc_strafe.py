"""A wanderer moves between its swings: it backs off the player and steps
round them, facing them, then comes back in and swings again on time.

npc/verify_strafe.py reads the graph; this watches one zombie do it. Put
beside the player it goes aggro (touch) and swings. From that swing to the
next the probe samples where it stands and which way it faces:

  - the first Chase step after the swing picks an angle and a distance inside
    forest_generator/npc_strafe.py's ranges, for that swing;
  - it ends up further from the player than it swung from, and round them;
  - while it steps it faces the player, though that is not the way it moves;
  - it is back in reach for the next swing, which is not late, and by then it
    turns the way it runs again.
"""

SYSTEMS = ('npc',)

import math

import unreal

from forest_generator.npc_placement import (
    NAV_REACHABLE_EXTENT_CM, NPC_REPATH_SECONDS,
)
from forest_generator.npc_strafe import (
    NPC_STRAFE_MAX_ANGLE_DEG, NPC_STRAFE_MAX_DISTANCE_CM,
    NPC_STRAFE_MIN_ANGLE_DEG, NPC_STRAFE_MIN_DISTANCE_CM,
)
from npc.monster_tuning import TUNED_VAR
from npc.paths import STRAFE_DIST_VAR, STRAFE_FOR_VAR, STRAFE_YAW_VAR

BESIDE_CM = 100.0     # well inside the touch range and the melee range
SAMPLE_S = 0.05
MAX_SAMPLES = 200     # 10 s of game time: several cooldowns
BACK_OFF_CM = 40.0    # further out than it swung from, by at least this
ROUND_DEG = 10.0      # ...and round the player by at least this
FACING_DOT = 0.7      # within 45 degrees of the player
MOVING_CMS = 50.0


def _zombies(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if c.get_class().get_name().startswith("BP_ForestWandererAI_Zombie")
            and c.get_controlled_pawn() is not None]


def _sample(p, npc, player):
    """(gap, bearing of the wanderer about the player, how squarely it faces
    them, how much of its movement is along its facing, speed, orient flag)."""
    at, to = npc.get_actor_location(), player.get_actor_location()
    dx, dy = at.x - to.x, at.y - to.y
    gap = math.hypot(dx, dy) or 1.0
    fwd, vel = npc.get_actor_forward_vector(), npc.get_velocity()
    speed = math.hypot(vel.x, vel.y)
    facing = (fwd.x * -dx + fwd.y * -dy) / gap
    along = (fwd.x * vel.x + fwd.y * vel.y) / speed if speed > 1.0 else 1.0
    orient = bool(npc.get_editor_property("character_movement")
                  .get_editor_property("orient_rotation_to_movement"))
    return gap, math.degrees(math.atan2(dy, dx)), facing, along, speed, orient


def _navmesh_under(p, actor):
    """Without a navmesh the step order finds no path, and the wanderer
    stands, as a patrol does."""
    return unreal.NavigationSystemV1.project_point_to_navigation(
        p.world(), actor.get_actor_location(), None, None,
        unreal.Vector(*NAV_REACHABLE_EXTENT_CM)) is not None


def _turn(a, b):
    return abs((b - a + 180.0) % 360.0 - 180.0)


def probe(p):
    yield lambda: len(_zombies(p)) > 0
    yield 0.5
    ctrl = _zombies(p)[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()

    # A headless -game run was found with no navmesh tiles at all, and none
    # being built; RebuildNavigation builds them in a few seconds.
    if not _navmesh_under(p, player):
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _navmesh_under(p, player)

    def armed():
        return float(p.get(ctrl, "NextAttackTime"))

    # Facing the player, as a wanderer that ran up to them would be: placed
    # with its back to them it would spend the step turning round.
    npc.set_actor_location_and_rotation(
        player.get_actor_location() + unreal.Vector(BESIDE_CM, 0.0, 0.0),
        unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0), False, True)
    yield lambda: armed() > 0.0
    first = armed()
    start = _sample(p, npc, player)
    samples = []
    while armed() == first and len(samples) < MAX_SAMPLES:
        yield SAMPLE_S
        samples.append(_sample(p, npc, player))
    p.check("beside the player a zombie swings, and swings again",
            armed() > first, f"{len(samples)} samples, armed {first:.2f} -> {armed():.2f}")

    yaw, dist = float(p.get(ctrl, STRAFE_YAW_VAR)), float(p.get(ctrl, STRAFE_DIST_VAR))
    # StrafeFor is the swing the last pick was made for: by now the second
    # swing's pick may not have been made, so it is one of the two.
    p.check("after the swing it picks a sidestep: an angle either way and a "
            "distance, inside the ranges",
            NPC_STRAFE_MIN_ANGLE_DEG <= abs(yaw) <= NPC_STRAFE_MAX_ANGLE_DEG
            and NPC_STRAFE_MIN_DISTANCE_CM <= dist <= NPC_STRAFE_MAX_DISTANCE_CM
            and float(p.get(ctrl, STRAFE_FOR_VAR)) in (first, armed()),
            f"{yaw:.0f} deg, {dist:.0f} cm")
    if not samples:
        return

    furthest = max(s[0] for s in samples)
    p.check(f"between the swings it backs off the player (by {BACK_OFF_CM:.0f} cm "
            f"or more)", furthest >= start[0] + BACK_OFF_CM,
            f"{start[0]:.0f} cm at the swing, {furthest:.0f} cm at the furthest")
    swung = max(_turn(start[1], s[1]) for s in samples)
    p.check(f"...and steps round them (by {ROUND_DEG:.0f} deg or more)",
            swung >= ROUND_DEG, f"{swung:.0f} deg")
    stepping = [s for s in samples if not s[5] and s[4] > MOVING_CMS]
    p.check("while it steps it faces the player",
            len(stepping) > 0 and min(s[2] for s in stepping) >= FACING_DOT,
            f"{len(stepping)} samples, facing dot "
            f"{min([s[2] for s in stepping] or [0.0]):.2f}")
    p.check("...which is not the way it is moving (a sidestep, not a turn and walk)",
            len(stepping) > 0 and min(s[3] for s in stepping) < FACING_DOT,
            f"movement along its facing: {min([s[3] for s in stepping] or [1.0]):.2f}")

    reach = float(p.get(ctrl, TUNED_VAR["melee_range_cm"]))
    interval = float(p.get(ctrl, TUNED_VAR["melee_interval_s"]))
    last = samples[-1]
    p.check("it is back in reach for the next swing, facing the way it runs",
            last[0] <= reach + 10.0 and last[5],
            f"{last[0]:.0f} cm of {reach:.0f}, orient to movement {last[5]}")
    p.check("...and the next swing is not late (within two of the tree's beats "
            "of the interval)",
            armed() - first <= interval + 2.0 * NPC_REPATH_SECONDS + 0.2,
            f"{armed() - first:.2f} s apart, interval {interval:g} s")
