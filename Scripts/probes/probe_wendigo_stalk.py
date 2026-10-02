"""A wendigo hunts: it roars, comes in round the player from tree to tree,
and charges once it is close (npc/stalk.py, stalk_cover.py).

npc/verify_stalk.py reads the graph; this watches one wendigo do it. It is
stood where it can see the player, a hunt's length off, and sampled from the
moment it goes aggro until it has swung at them:

  - it roars first: the scream clip plays, and it stands, facing the player,
    until the roar is over;
  - then it runs legs, faster than it chases, each to a spot closer to the
    player and round them, the way its side says; the side is turned about
    only once its time is up, and the next turn is then 4-9 s on;
  - a spot it took for cover has a tree between it and the player, and it
    waits there;
  - inside the charge range it stops picking trees, runs at the player and
    swings.
"""

import math

import unreal

from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from forest_generator.npc_stalk import (
    NPC_STALK_CHARGE_CM, NPC_STALK_HIDE_MIN_S, NPC_STALK_ROAR, NPC_STALK_ROAR_S,
    NPC_STALK_RUN_SCALE, NPC_STALK_TURN_MAX_S, NPC_STALK_TURN_MIN_S,
)
from npc.monster_tuning import TUNED_VAR
from npc.paths import (
    AGGRO_VAR, STALK_ARRIVED_VAR, STALK_CHARGING_VAR, STALK_COVER_VAR,
    STALK_HIDDEN_VAR, STALK_LEGS_VAR, STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR,
    STALK_TURN_AT_VAR,
)

START_CM = 3200.0     # inside the wendigo's sight, a few legs outside the charge
SAMPLE_S = 0.1
MAX_SAMPLES = 450     # 45 s of game time
ROAR_DRIFT_CM = 80.0  # what it may slide while it brakes into the roar
FACING_DOT = 0.7      # within 45 degrees of the player
STILL_CMS = 30.0
CENTRE_CM = 88.0      # a spot is on the ground; the pawn's centre is this far up
BEAT_S = 0.7          # the tree's 0.5 s beat, and a sample or two
ROAR_CLIP = NPC_STALK_ROAR["Wendigo"].rsplit("/", 1)[-1]


def _wendigos(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls
            if c.get_class().get_name().startswith("BP_ForestWandererAI_Wendigo")
            and c.get_controlled_pawn() is not None]


def _on_navmesh(p, point):
    return unreal.NavigationSystemV1.project_point_to_navigation(
        p.world(), point, None, None, unreal.Vector(*NAV_REACHABLE_EXTENT_CM))


def _montage_clips(montage):
    names = []
    for track in montage.get_editor_property("slot_anim_tracks"):
        for seg in track.get_editor_property("anim_track").get_editor_property("anim_segments"):
            ref = seg.get_editor_property("anim_reference")
            if ref:
                names.append(ref.get_name())
    return names


def _tree_between(npc, spot, player):
    """Does a line from ``spot`` to the player strike a tree first?"""
    hit = unreal.SystemLibrary.line_trace_single(
        npc, spot + unreal.Vector(0.0, 0.0, CENTRE_CM), player.get_actor_location(),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [npc],
        unreal.DrawDebugTrace.NONE, True)
    comp = hit.to_tuple()[10] if hit else None
    return isinstance(comp, unreal.InstancedStaticMeshComponent)


def _about(point, centre):
    """(flat distance, bearing in degrees) of ``point`` about ``centre``."""
    dx, dy = point.x - centre.x, point.y - centre.y
    return math.hypot(dx, dy), math.degrees(math.atan2(dy, dx))


def _turn(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


def _walk_speed(npc):
    return float(npc.get_editor_property("character_movement")
                 .get_editor_property("max_walk_speed"))


def _turned_on_time(before, leg):
    """Did ``leg``'s pick turn the side about only if the time was up, and
    then throw the next turn 4-9 s on?"""
    if leg["side"] == before["side"]:
        return leg["t"] < before["turn_at"] + BEAT_S
    return (leg["side"] == -before["side"] and leg["t"] >= before["turn_at"] - BEAT_S
            and NPC_STALK_TURN_MIN_S - BEAT_S <= leg["turn_at"] - leg["t"]
            <= NPC_STALK_TURN_MAX_S + BEAT_S)


def _stand_in_sight(p, ctrl, npc, player):
    """Put the wendigo START_CM from the player, facing them, on the first
    bearing where it stands on the navmesh and nothing hides the player."""
    home = player.get_actor_location()
    for yaw in range(0, 360, 30):
        at = home + unreal.Vector(START_CM * math.cos(math.radians(yaw)),
                                  START_CM * math.sin(math.radians(yaw)), 0.0)
        ground = _on_navmesh(p, at)
        if ground is None:
            continue
        npc.set_actor_location_and_rotation(
            ground + unreal.Vector(0.0, 0.0, 95.0),
            unreal.Rotator(pitch=0.0, yaw=yaw + 180.0, roll=0.0), False, True)
        if ctrl.line_of_sight_to(player):
            return yaw
    return None


def probe(p):
    yield lambda: len(_wendigos(p)) > 0
    yield 0.5
    ctrl = _wendigos(p)[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    anim = npc.get_editor_property("mesh").get_anim_instance()

    # A headless -game run was found with no navmesh tiles at all, and none
    # being built; RebuildNavigation builds them in a few seconds.
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None

    p.check("a patrolling wendigo has not hunted: no roar, no leg, no charge",
            float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) == 0.0
            and int(p.get(ctrl, STALK_LEGS_VAR)) == 0
            and not p.get(ctrl, STALK_CHARGING_VAR))
    yaw = _stand_in_sight(p, ctrl, npc, player)
    p.check(f"a wendigo is stood {START_CM / 100:.0f} m off, where it can see the player",
            yaw is not None, f"bearing {yaw}")
    if yaw is None:
        return
    yield lambda: bool(p.get(ctrl, AGGRO_VAR))
    yield lambda: float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) > 0.0
    roar_until = float(p.get(ctrl, STALK_ROAR_UNTIL_VAR))
    roared_at = npc.get_actor_location()
    p.check(f"aggro, its first act is the roar ({NPC_STALK_ROAR_S:g} s)",
            abs(roar_until - p.time() - NPC_STALK_ROAR_S) < 0.5
            and int(p.get(ctrl, STALK_LEGS_VAR)) == 0,
            f"{roar_until - p.time():.2f} s to go")
    side = float(p.get(ctrl, STALK_SIDE_VAR))
    turn_at = float(p.get(ctrl, STALK_TURN_AT_VAR))
    p.check("...and it has picked a side to come round, and when to turn about",
            side in (1.0, -1.0) and NPC_STALK_TURN_MIN_S <= turn_at - roar_until
            <= NPC_STALK_TURN_MAX_S,
            f"side {side:+.0f}, the turn {turn_at - roar_until:.1f} s after the roar")
    yield lambda: anim.get_current_active_montage() is not None or p.time() > roar_until
    montage = anim.get_current_active_montage()
    clips = _montage_clips(montage) if montage else []
    p.check("...playing the zombie scream, on its own skeleton", ROAR_CLIP in clips,
            f"{clips}")

    # --- the hunt, sampled ----------------------------------------------------
    samples, legs = [], []
    reach = float(p.get(ctrl, TUNED_VAR["melee_range_cm"]))
    while len(samples) < MAX_SAMPLES:
        at, home = npc.get_actor_location(), player.get_actor_location()
        gap, bearing = _about(at, home)
        vel, fwd = npc.get_velocity(), npc.get_actor_forward_vector()
        count = int(p.get(ctrl, STALK_LEGS_VAR))
        if count > len(legs):
            spot = p.get(ctrl, STALK_COVER_VAR)
            legs.append(dict(gap=gap, bearing=bearing, spot=spot, about=_about(spot, home),
                             t=p.time(), side=float(p.get(ctrl, STALK_SIDE_VAR)),
                             turn_at=float(p.get(ctrl, STALK_TURN_AT_VAR)),
                             hidden=bool(p.get(ctrl, STALK_HIDDEN_VAR)),
                             shaded=_tree_between(npc, spot, player)))
        samples.append(dict(
            t=p.time(), at=at, gap=gap, speed=math.hypot(vel.x, vel.y),
            facing=(fwd.x * (home.x - at.x) + fwd.y * (home.y - at.y)) / (gap or 1.0),
            towards=((vel.x * (home.x - at.x) + vel.y * (home.y - at.y))
                     / ((gap or 1.0) * (math.hypot(vel.x, vel.y) or 1.0))),
            walk=_walk_speed(npc),
            legs=count, arrived=bool(p.get(ctrl, STALK_ARRIVED_VAR)),
            hidden=bool(p.get(ctrl, STALK_HIDDEN_VAR)),
            charging=bool(p.get(ctrl, STALK_CHARGING_VAR)),
            swung=float(p.get(ctrl, "NextAttackTime")) > 0.0))
        if samples[-1]["swung"]:
            break
        yield SAMPLE_S

    roaring = [s for s in samples if s["t"] < roar_until]
    drift = max([_about(s["at"], roared_at)[0] for s in roaring] or [0.0])
    p.check("while it roars it stands, facing the player, and picks no tree",
            len(roaring) > 0 and drift <= ROAR_DRIFT_CM
            and roaring[-1]["facing"] >= FACING_DOT
            and all(s["legs"] == 0 for s in roaring),
            f"{len(roaring)} samples, drifted {drift:.0f} cm, facing dot "
            f"{roaring[-1]['facing'] if roaring else 0.0:.2f}")

    p.check("then it comes in by legs", len(legs) >= 2,
            f"{len(legs)} legs: " + ", ".join(
                f"{leg['gap'] / 100:.0f}->{leg['about'][0] / 100:.0f} m "
                f"{'tree' if leg['hidden'] else 'open'}" for leg in legs))
    if not legs:
        return
    p.check("...each to a spot closer to the player than it stood",
            all(leg["about"][0] < leg["gap"] for leg in legs))
    turns = [_turn(leg["bearing"], leg["about"][1]) for leg in legs]
    p.check("...and round them, every leg the way its side says",
            all(abs(t) > 3.0 for t in turns)
            and len({(t > 0.0) == (leg["side"] > 0.0) for t, leg in zip(turns, legs)}) == 1,
            f"{[round(t) for t in turns]} deg, sides {[int(leg['side']) for leg in legs]}")
    picks = [dict(side=side, turn_at=turn_at)] + legs
    p.check("...the side turned about only once its time was up, the next "
            f"turn then {NPC_STALK_TURN_MIN_S:g}-{NPC_STALK_TURN_MAX_S:g} s on",
            all(_turned_on_time(a, b) for a, b in zip(picks, picks[1:])),
            f"{sum(a['side'] != b['side'] for a, b in zip(picks, picks[1:]))} turns "
            f"in {len(legs)} legs")
    covers = [leg for leg in legs if leg["hidden"]]
    p.check("a spot taken for cover has a tree between it and the player",
            len(covers) > 0 and all(leg["shaded"] for leg in covers),
            f"{sum(leg['shaded'] for leg in covers)} of {len(covers)} covers; "
            f"{len(legs) - len(covers)} legs in the open")
    waits = [s for s in samples if s["arrived"] and s["hidden"] and not s["charging"]]
    held = len([s for s in waits if s["speed"] <= STILL_CMS]) * SAMPLE_S
    p.check("...and behind it the wendigo waits, facing the player",
            held >= NPC_STALK_HIDE_MIN_S * 0.5
            and max([s["facing"] for s in waits] or [0.0]) >= FACING_DOT,
            f"{held:.1f} s still over {len({s['legs'] for s in waits})} covers")

    charge = [s for s in samples if s["charging"]]
    p.check(f"inside {NPC_STALK_CHARGE_CM / 100:.0f} m it charges",
            len(charge) > 0 and charge[0]["gap"] <= NPC_STALK_CHARGE_CM
            and all(not s["charging"] for s in samples if s["gap"] > NPC_STALK_CHARGE_CM + 50.0),
            f"at {charge[0]['gap'] / 100:.1f} m" if charge else "never")
    if not charge:
        return
    running = [s for s in charge if s["speed"] > 200.0 and s["gap"] > reach + 100.0]
    hunted = [s["walk"] for s in samples
              if s["legs"] > 0 and not s["arrived"] and not s["charging"]
              and s["speed"] > 200.0]
    chased = sorted(s["walk"] for s in running)
    p.check(f"it ran its legs at {NPC_STALK_RUN_SCALE:.0%} of the speed it charges at",
            len(hunted) > 0 and len(chased) > 0
            and abs(sorted(hunted)[len(hunted) // 2]
                    / chased[len(chased) // 2] - NPC_STALK_RUN_SCALE) < 0.02,
            f"{sorted(hunted)[len(hunted) // 2] if hunted else 0:.0f} cm/s on a leg, "
            f"{chased[len(chased) // 2] if chased else 0:.0f} on the charge")
    p.check("...picking no more trees, straight at the player",
            charge[-1]["legs"] == charge[0]["legs"] and len(running) > 0
            and sorted(s["towards"] for s in running)[len(running) // 2] >= 0.9,
            f"{len(running)} samples running, median heading dot "
            f"{sorted(s['towards'] for s in running)[len(running) // 2] if running else 0:.2f}")
    p.check("...until it reaches them and swings",
            samples[-1]["swung"] and samples[-1]["gap"] <= reach + 50.0,
            f"{samples[-1]['gap']:.0f} cm of {reach:.0f}")
