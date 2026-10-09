"""A wendigo that is too far from the player to stalk them runs straight at
them (npc/stalk.py, NPC_STALK_CATCH_UP_CM), at the speed of a leg, and hunts
again once it is near.

npc/verify_stalk.py reads the graph; this watches one wendigo do it. It is
stood where it can see the player and left to roar and start its hunt. Then
the two are put in opposite corners of the map, further apart than the
catch-up range, and its StalkOrigin written to the player's corner (a player
who has run that far from where they stood is charged instead:
probes/probe_wendigo_fled.py):

  - it picks no tree and does not charge: it runs at the player, at the speed
    it ran its leg at;
  - put back where they began, near each other, the next pass picks a leg:
    the hunt goes on.

That the hunt itself is as it was is probes/probe_wendigo_stalk.py's.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('npc',)

import math

import unreal

from npc.monster_tuning import monster_specs
from npc.paths import (
    AGGRO_VAR, NPC_DIR, STALK_CHARGING_VAR, STALK_LEGS_VAR, STALK_ORIGIN_VAR,
    STALK_ROAR_UNTIL_VAR,
)
from probes.probe_wendigo_stalk import (
    START_CM, _about, _on_navmesh, _stand_in_sight, _walk_speed, _wendigos,
)

# The tuned numbers (the MONSTER SETTINGS tab's rows): monster_tuning.csv's, as built.
_SPEC = monster_specs("Wendigo")
STALK_CATCH_UP_CM = _SPEC["stalk_catch_up_cm"]

WRITABLE = [(f"{NPC_DIR}/BP_ForestWandererAI_Wendigo", STALK_ORIGIN_VAR)]

SAMPLE_S = 0.1
BEAT_S = 0.7            # the tree's 0.5 s beat, and a sample or two
WATCH_SAMPLES = 40      # 4 s of running
CORNERS_CM = (9000.0, 8000.0, 7000.0, 6000.0)   # tried in turn, each way
LEG_WAIT_S = 10.0
TERRAIN_MID_CM, TERRAIN_HALF_CM = 2000.0, 6000.0    # every height a map has


def _ground(p, x, y):
    """The navmesh under (x, y), whatever its height: the terrain rises tens
    of metres across a map, so the box is as tall as one."""
    return unreal.NavigationSystemV1.project_point_to_navigation(
        p.world(), unreal.Vector(x, y, TERRAIN_MID_CM), None, None,
        unreal.Vector(200.0, 200.0, TERRAIN_HALF_CM))


def _corners(p):
    """Two spots on the navmesh, in opposite corners of the map, further
    apart than the catch-up range; None when the map has none."""
    for reach in CORNERS_CM:
        for sx, sy in ((1.0, 1.0), (1.0, -1.0)):
            a, b = _ground(p, reach * sx, reach * sy), _ground(p, -reach * sx, -reach * sy)
            if a and b and _about(a, b)[0] > STALK_CATCH_UP_CM + 1000.0:
                return a, b
    return None


def _put(actor, ground):
    actor.set_actor_location(ground + unreal.Vector(0.0, 0.0, 95.0), False, True)


def probe(p):
    yield lambda: len(_wendigos(p)) > 0
    yield 0.5
    ctrl = _wendigos(p)[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None

    yaw = _stand_in_sight(p, ctrl, npc, player)
    p.check(f"a wendigo is stood {START_CM / 100:.0f} m off, where it can see the player",
            yaw is not None, f"bearing {yaw}")
    if yaw is None:
        return
    yield lambda: bool(p.get(ctrl, AGGRO_VAR))
    yield lambda: int(p.get(ctrl, STALK_LEGS_VAR)) >= 1
    yield BEAT_S
    leg_speed = _walk_speed(npc)
    p.check("it hunts: roared, on a leg, not charging",
            float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) > 0.0
            and not p.get(ctrl, STALK_CHARGING_VAR), f"{leg_speed:.0f} cm/s on the leg")

    # --- far apart: no stalking ------------------------------------------------
    corners = _corners(p)
    p.check(f"the map has two corners over {STALK_CATCH_UP_CM / 100:.0f} m apart "
            f"to stand them in", corners is not None)
    if corners is None:
        return
    spawn = player.get_actor_location()
    _put(player, corners[0])
    _put(npc, corners[1])
    # The player it hunts stood there all along: they have not run off.
    p.set(ctrl, STALK_ORIGIN_VAR, player.get_actor_location())
    yield BEAT_S                # a pass of the tree
    legs = int(p.get(ctrl, STALK_LEGS_VAR))
    samples = []
    for _ in range(WATCH_SAMPLES):
        at, home = npc.get_actor_location(), player.get_actor_location()
        gap, _bearing = _about(at, home)
        vel = npc.get_velocity()
        speed = math.hypot(vel.x, vel.y)
        samples.append(dict(
            gap=gap, speed=speed, walk=_walk_speed(npc),
            towards=((vel.x * (home.x - at.x) + vel.y * (home.y - at.y))
                     / ((gap or 1.0) * (speed or 1.0))),
            legs=int(p.get(ctrl, STALK_LEGS_VAR)),
            charging=bool(p.get(ctrl, STALK_CHARGING_VAR))))
        yield SAMPLE_S
    p.check(f"{samples[0]['gap'] / 100:.0f} m from the player it picks no tree "
            f"and does not charge",
            samples[0]["gap"] > STALK_CATCH_UP_CM
            and all(s["legs"] == legs and not s["charging"] for s in samples),
            f"{samples[-1]['legs'] - legs} legs picked")
    running = [s for s in samples if s["speed"] > 200.0]
    heading = sorted(s["towards"] for s in running)[len(running) // 2] if running else 0.0
    p.check("...it runs straight at them",
            len(running) >= WATCH_SAMPLES // 2 and heading >= 0.9
            and samples[-1]["gap"] < samples[0]["gap"] - 1000.0,
            f"{len(running)} of {len(samples)} samples running, median heading dot "
            f"{heading:.2f}, {samples[0]['gap'] / 100:.0f} -> "
            f"{samples[-1]['gap'] / 100:.0f} m")
    p.check("...at the speed of a leg",
            all(abs(s["walk"] - leg_speed) < 1.0 for s in samples),
            f"{samples[-1]['walk']:.0f} cm/s, {leg_speed:.0f} on the leg")

    # --- near again: the hunt goes on. Back where the player began, on the
    # flat of the spawn clearing, where a spot in their sight is found. ----------
    player.set_actor_location(spawn, False, True)
    p.set(ctrl, STALK_ORIGIN_VAR, spawn)
    yaw = _stand_in_sight(p, ctrl, npc, player)
    limit = p.time() + LEG_WAIT_S
    yield lambda: (int(p.get(ctrl, STALK_LEGS_VAR)) > legs
                   or p.get(ctrl, STALK_CHARGING_VAR) or p.time() > limit)
    p.check(f"stood {START_CM / 100:.0f} m off again, it picks its next leg: the "
            f"hunt goes on, with no second roar",
            yaw is not None and int(p.get(ctrl, STALK_LEGS_VAR)) > legs
            and not p.get(ctrl, STALK_CHARGING_VAR),
            f"bearing {yaw}, {int(p.get(ctrl, STALK_LEGS_VAR)) - legs} more legs, "
            f"charging {bool(p.get(ctrl, STALK_CHARGING_VAR))}, "
            f"{_about(npc.get_actor_location(), player.get_actor_location())[0] / 100:.0f} m off")
