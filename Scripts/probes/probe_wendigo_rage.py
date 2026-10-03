"""A wendigo the player has shot is enraged: it drops its hunt and charges.
And the way a hunt goes round the player turns about once its time is up
(npc/stalk.py, forest_generator/npc_stalk.py).

npc/verify_stalk.py reads the graph; probe_wendigo_stalk.py watches a whole
hunt, with whatever turns fall in it. This one makes both things happen:

  - a wendigo on its hunt, a leg picked: its time to turn is written to now,
    and the next leg it picks goes the other way round, with a new time to
    turn 4-9 s on;
  - it is then shot (DamagedByPlayer, as a pellet leaves it), still outside
    the charge range: within a beat of the tree it is Enraged, picks no more
    trees, runs straight at the player at its run speed and swings;
  - a second wendigo, shot while it patrols: it is enraged without ever
    roaring or picking a tree, and runs at the player.
"""

import math

import unreal

from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from npc.monster_tuning import TUNED_VAR, monster_specs
from npc.paths import (
    AGGRO_VAR, ENRAGED_VAR, NPC_DIR, STALK_CHARGING_VAR, STALK_LEGS_VAR,
    STALK_ROAR_UNTIL_VAR, STALK_SIDE_VAR, STALK_TURN_AT_VAR,
)
from probes.probe_wendigo_stalk import (
    START_CM, _about, _on_navmesh, _stand_in_sight, _walk_speed, _wendigos,
)

# The tuned numbers (the MONSTER SETTINGS tab's rows): monster_tuning.csv's, as built.
_SPEC = monster_specs("Wendigo")
STALK_CHARGE_CM = _SPEC["stalk_charge_cm"]
STALK_TURN_MAX_S = _SPEC["stalk_turn_max_s"]
STALK_TURN_MIN_S = _SPEC["stalk_turn_min_s"]

WENDIGO_AI = f"{NPC_DIR}/BP_ForestWandererAI_Wendigo"
WRITABLE = [(WENDIGO_AI, STALK_TURN_AT_VAR), (HEALTH_BP_PATH, "DamagedByPlayer")]

SAMPLE_S = 0.1
BEAT_S = 0.7          # the tree's 0.5 s beat, and a sample or two
CHARGE_SAMPLES = 300  # 30 s of game time: 30 m at its run is 5
LEG_WAIT_S = 20.0


def _sample(npc, player):
    at, home = npc.get_actor_location(), player.get_actor_location()
    gap, _bearing = _about(at, home)
    vel = npc.get_velocity()
    speed = math.hypot(vel.x, vel.y)
    return dict(gap=gap, speed=speed, walk=_walk_speed(npc),
                towards=((vel.x * (home.x - at.x) + vel.y * (home.y - at.y))
                         / ((gap or 1.0) * (speed or 1.0))))


def _median(values):
    return sorted(values)[len(values) // 2] if values else 0.0


def probe(p):
    yield lambda: len(_wendigos(p)) > 1
    yield 0.5
    ctrl, other = _wendigos(p)[:2]
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
    p.check("it hunts: roared, on its first leg, and not enraged",
            float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) > 0.0
            and not p.get(ctrl, ENRAGED_VAR) and not p.get(ctrl, STALK_CHARGING_VAR))

    # --- the turn: its time is up, so the next leg goes the other way ---------
    side, legs = float(p.get(ctrl, STALK_SIDE_VAR)), int(p.get(ctrl, STALK_LEGS_VAR))
    p.set(ctrl, STALK_TURN_AT_VAR, p.time())
    limit = p.time() + LEG_WAIT_S
    yield lambda: (int(p.get(ctrl, STALK_LEGS_VAR)) > legs
                   or p.get(ctrl, STALK_CHARGING_VAR) or p.time() > limit)
    ahead = float(p.get(ctrl, STALK_TURN_AT_VAR)) - p.time()
    p.check("its time to turn up, the next leg it picks goes the other way round",
            int(p.get(ctrl, STALK_LEGS_VAR)) == legs + 1
            and float(p.get(ctrl, STALK_SIDE_VAR)) == -side,
            f"side {side:+.0f} -> {float(p.get(ctrl, STALK_SIDE_VAR)):+.0f}, "
            f"{int(p.get(ctrl, STALK_LEGS_VAR)) - legs} more legs")
    p.check(f"...and the turn after that is {STALK_TURN_MIN_S:g}-"
            f"{STALK_TURN_MAX_S:g} s on",
            STALK_TURN_MIN_S - BEAT_S <= ahead <= STALK_TURN_MAX_S + BEAT_S,
            f"{ahead:.1f} s")

    # --- the shot ---------------------------------------------------------------
    before = _sample(npc, player)
    legs, shot_at = int(p.get(ctrl, STALK_LEGS_VAR)), p.time()
    p.check("it is shot outside the charge range, still hunting",
            before["gap"] > STALK_CHARGE_CM + 200.0
            and not p.get(ctrl, STALK_CHARGING_VAR) and not p.get(ctrl, ENRAGED_VAR),
            f"{before['gap'] / 100:.1f} m off")
    p.set(p.component(npc, HEALTH_CLASS_PATH), "DamagedByPlayer", True)
    yield lambda: bool(p.get(ctrl, ENRAGED_VAR)) or p.time() > shot_at + 5.0
    p.check("shot, it is enraged within a beat of its tree",
            bool(p.get(ctrl, ENRAGED_VAR)) and p.time() - shot_at <= BEAT_S,
            f"{p.time() - shot_at:.2f} s")
    samples, reach = [], float(p.get(ctrl, TUNED_VAR["melee_range_cm"]))
    while len(samples) < CHARGE_SAMPLES:
        samples.append(dict(_sample(npc, player), legs=int(p.get(ctrl, STALK_LEGS_VAR)),
                            swung=float(p.get(ctrl, "NextAttackTime")) > 0.0))
        if samples[-1]["swung"]:
            break
        yield SAMPLE_S
    running = [s for s in samples if s["speed"] > 200.0 and s["gap"] > reach + 100.0]
    p.check("...picks no more trees and runs straight at the player",
            samples[-1]["legs"] == legs and len(running) > 0
            and _median([s["towards"] for s in running]) >= 0.9,
            f"{len(running)} samples running, median heading dot "
            f"{_median([s['towards'] for s in running]):.2f}")
    p.check("...at its run speed, not the hunt's",
            len(running) > 0
            and _median([s["walk"] for s in running]) < before["walk"] - 50.0,
            f"{_median([s['walk'] for s in running]):.0f} cm/s, "
            f"{before['walk']:.0f} on the leg")
    p.check("...until it reaches them and swings",
            samples[-1]["swung"] and samples[-1]["gap"] <= reach + 50.0,
            f"{samples[-1]['gap']:.0f} cm of {reach:.0f}")

    # --- shot on patrol: enraged from the start, no roar ------------------------
    prowler = other.get_controlled_pawn()
    p.check("a second wendigo patrols: not aggro, not enraged",
            not p.get(other, AGGRO_VAR) and not p.get(other, ENRAGED_VAR))
    shot_at = p.time()
    p.set(p.component(prowler, HEALTH_CLASS_PATH), "DamagedByPlayer", True)
    yield lambda: bool(p.get(other, ENRAGED_VAR)) or p.time() > shot_at + 5.0
    yield 1.5
    after = _sample(prowler, player)
    p.check("shot, it is aggro and enraged without a roar or a tree",
            bool(p.get(other, AGGRO_VAR)) and bool(p.get(other, ENRAGED_VAR))
            and float(p.get(other, STALK_ROAR_UNTIL_VAR)) == 0.0
            and int(p.get(other, STALK_LEGS_VAR)) == 0)
    p.check("...and runs at the player",
            after["speed"] > 200.0 and after["towards"] >= 0.7,
            f"{after['speed']:.0f} cm/s, heading dot {after['towards']:.2f}, "
            f"{after['gap'] / 100:.0f} m off")
