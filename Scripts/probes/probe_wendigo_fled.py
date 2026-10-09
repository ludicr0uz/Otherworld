"""A wendigo hunts a player who stands their ground. One who runs too far from
where they stood when it roared is charged at once (npc/stalk.py's fled test,
TuneStalkFled, NPC_STALK_FLED_CM).

npc/verify_stalk.py reads the graph; this watches one wendigo do it. It is
stood where it can see the player and left to roar and start its hunt:

  - the roar noted where the player stood (StalkOrigin);
  - the player put half the range from there, away from it: the hunt goes on;
  - the player put past the range: within a pass or two StalkCharging is set,
    from well outside the charge range, and it comes straight at them at its
    run, not at the speed of a leg.

That the hunt itself is as it was is probes/probe_wendigo_stalk.py's.
"""

SYSTEMS = ('npc',)

import math

import unreal

from npc.monster_tuning import monster_specs
from npc.paths import (
    AGGRO_VAR, STALK_CHARGING_VAR, STALK_LEGS_VAR, STALK_ORIGIN_VAR,
    STALK_ROAR_UNTIL_VAR,
)
from probes.probe_wendigo_stalk import (
    START_CM, _about, _on_navmesh, _stand_in_sight, _walk_speed, _wendigos,
)

# The tuned numbers (the MONSTER SETTINGS tab's rows): monster_tuning.csv's, as built.
_SPEC = monster_specs("Wendigo")
STALK_FLED_CM = _SPEC["stalk_fled_cm"]
STALK_CHARGE_CM = _SPEC["stalk_charge_cm"]

SAMPLE_S = 0.1
BEAT_S = 0.7            # the tree's 0.5 s beat, and a sample or two
CHARGE_WAIT_S = 2.0     # a pass or two of the tree
WATCH_SAMPLES = 15      # 1.5 s of the charge
PAST_CM = 500.0         # how far past the range the player is put
ORIGIN_SLACK_CM = 50.0
SWINGS_DEG = (0.0, 30.0, -30.0, 60.0, -60.0, 90.0, -90.0)


def _spot(p, origin, bearing, reach):
    """The navmesh ``reach`` from ``origin`` (flat), on the first bearing near
    ``bearing`` that has any; None with none."""
    for swing in SWINGS_DEG:
        yaw = math.radians(bearing + swing)
        ground = _on_navmesh(p, origin + unreal.Vector(
            reach * math.cos(yaw), reach * math.sin(yaw), 0.0))
        if ground is not None:
            return ground
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

    stood = player.get_actor_location()
    yaw = _stand_in_sight(p, ctrl, npc, player)
    p.check(f"a wendigo is stood {START_CM / 100:.0f} m off, where it can see the player",
            yaw is not None, f"bearing {yaw}")
    if yaw is None:
        return
    yield lambda: bool(p.get(ctrl, AGGRO_VAR))
    yield lambda: int(p.get(ctrl, STALK_LEGS_VAR)) >= 1
    yield BEAT_S
    leg_speed = _walk_speed(npc)
    origin = p.get(ctrl, STALK_ORIGIN_VAR)
    off = _about(origin, stood)[0]
    p.check("it hunts (roared, on a leg, not charging), and the roar noted "
            "where the player stood",
            float(p.get(ctrl, STALK_ROAR_UNTIL_VAR)) > 0.0
            and not p.get(ctrl, STALK_CHARGING_VAR) and off < ORIGIN_SLACK_CM,
            f"StalkOrigin {off:.0f} cm from the player, {leg_speed:.0f} cm/s on the leg")

    # --- a little way off: still hunted ---------------------------------------
    away = _about(stood, npc.get_actor_location())[1]
    near = _spot(p, stood, away, STALK_FLED_CM * 0.5)
    far = _spot(p, stood, away, STALK_FLED_CM + PAST_CM)
    p.check("there is ground to run to, away from it, inside the range and past it",
            near is not None and far is not None)
    if near is None or far is None:
        return
    _put(player, near)
    yield 2 * BEAT_S
    ran = _about(player.get_actor_location(), origin)[0]
    p.check(f"the player {ran / 100:.0f} m from where they stood (the range is "
            f"{STALK_FLED_CM / 100:.0f} m): the hunt goes on, from the same spot",
            ran < STALK_FLED_CM and not p.get(ctrl, STALK_CHARGING_VAR)
            and _about(p.get(ctrl, STALK_ORIGIN_VAR), origin)[0] < 1.0,
            f"charging {bool(p.get(ctrl, STALK_CHARGING_VAR))}")

    # --- run off: charged -----------------------------------------------------
    _put(player, far)
    limit = p.time() + CHARGE_WAIT_S
    yield lambda: bool(p.get(ctrl, STALK_CHARGING_VAR)) or p.time() > limit
    ran = _about(player.get_actor_location(), origin)[0]
    gap = _about(npc.get_actor_location(), player.get_actor_location())[0]
    p.check(f"the player {ran / 100:.0f} m from where they stood: it charges, "
            f"from outside the charge range",
            ran > STALK_FLED_CM and bool(p.get(ctrl, STALK_CHARGING_VAR))
            and gap > STALK_CHARGE_CM + 500.0,
            f"charging {bool(p.get(ctrl, STALK_CHARGING_VAR))}, {gap / 100:.0f} m off")
    legs = int(p.get(ctrl, STALK_LEGS_VAR))
    yield BEAT_S                # the Chase step's first pass
    samples = []
    for _ in range(WATCH_SAMPLES):
        at, home = npc.get_actor_location(), player.get_actor_location()
        reach, _bearing = _about(at, home)
        vel = npc.get_velocity()
        speed = math.hypot(vel.x, vel.y)
        samples.append(dict(
            gap=reach, speed=speed, walk=_walk_speed(npc),
            towards=((vel.x * (home.x - at.x) + vel.y * (home.y - at.y))
                     / ((reach or 1.0) * (speed or 1.0)))))
        yield SAMPLE_S
    running = [s for s in samples if s["speed"] > 200.0]
    heading = sorted(s["towards"] for s in running)[len(running) // 2] if running else 0.0
    p.check("...it comes at them, picking no more trees",
            len(running) >= WATCH_SAMPLES // 2 and heading >= 0.7
            and samples[-1]["gap"] < samples[0]["gap"]
            and int(p.get(ctrl, STALK_LEGS_VAR)) == legs,
            f"{len(running)} of {len(samples)} samples running, median heading dot "
            f"{heading:.2f}, {samples[0]['gap'] / 100:.0f} -> "
            f"{samples[-1]['gap'] / 100:.0f} m")
    p.check("...at its run, not the speed of a leg",
            all(s["walk"] < leg_speed - 1.0 for s in samples),
            f"{samples[-1]['walk']:.0f} cm/s, {leg_speed:.0f} on a leg")
