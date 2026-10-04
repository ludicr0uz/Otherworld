"""The sounds of a state, in the running game (Sound/sound_world.py).

A sound can't be heard in a headless game; this reads what would play it:

  - the player's and a wanderer's footstep component found the level's bushes
    at BeginPlay, and hold the rustle's takes;
  - walked in the open a footfall is not InBush, and walked from inside a bush
    it is (the stride is shortened to a centimetre, so a short walk is many
    footfalls);
  - at full health the heartbeat never comes due; badly hurt, it is played and
    next due HEARTBEAT_S on, and not before;
  - with the run key up the breath never comes due (no key can be injected, so
    the spent sprint itself is verify/sound_states.py's).
"""

import time

import unreal

from combat import footstep_vars as FV
from combat import health_vars as HV
from combat.paths import (
    FOOTSTEP_BP_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH)
from combat.weapon_component import vars as WV
from forest_generator.bush_placement import DEFAULT_BUSH_SPECS
from probes.probe_wendigo_quiet import _zombies
from Sound.sound_world import GRASS_RUSTLE, HEARTBEAT_S, LOW_HEALTH_FRACTION

WRITABLE = [(FOOTSTEP_BP_PATH, FV.StrideCm), (HEALTH_BP_PATH, HV.Health)]

# Short walks from spots known to be on the ground, on a centimetre's stride:
# a 10 m walk up to a bush from a point set down beside it went 3 cm in 2000
# frames on the 1 km map (the start was not on the ground there).
STRIDE_CM = 1.0
WALK_CM = 25.0
WALL_S = 20.0
STAND_CM = 96.0        # the capsule's centre over a bush's foot (it is sunk 6 cm)


def _feet(pawn):
    found = [c for c in pawn.get_components_by_class(unreal.ActorComponent)
             if c.get_class().get_name().startswith("BP_FootstepComponent")]
    return found[0] if found else None


def _bush_points(feet, p):
    """Where every bush of the level stands (world space)."""
    points = []
    for comp in p.get(feet, FV.Bushes):
        for i in range(comp.get_instance_count()):
            points.append(comp.get_instance_transform(i, True).translation)
    return points


def _walk(p, player, feet, seen):
    """Walk the player forward from where they stand until they have gone
    WALK_CM or WALL_S is up, noting InBush after each frame in ``seen``."""
    start = player.get_actor_location()
    end = time.time() + WALL_S
    while time.time() < end:
        player.add_movement_input(player.get_actor_forward_vector(), 1.0)
        yield 0.0
        seen.append(p.get(feet, FV.InBush))
        if (player.get_actor_location() - start).length() >= WALK_CM:
            return


def probe(p):
    yield 0.5
    player = p.pawn()
    feet = _feet(player)
    p.check("the player wears a footstep component", feet is not None)
    if feet is None:
        return
    meshes = {s.mesh_path.split(".")[0] for s in DEFAULT_BUSH_SPECS}
    bushes = list(p.get(feet, FV.Bushes))
    p.check("it found the level's bushes at BeginPlay, and nothing that is not one",
            bool(bushes) and all(
                c.static_mesh.get_path_name().split(".")[0] in meshes for c in bushes),
            f"{len(bushes)} component(s)")
    got = [s.get_name() for s in p.get(feet, FV.RustleSounds) if s]
    p.check("...and holds the rustle's takes", got == list(GRASS_RUSTLE.names), str(got))
    yield lambda: _zombies(p)
    theirs = _feet(_zombies(p)[0].get_controlled_pawn())
    p.check("a wanderer's does too: its bushes and its takes",
            theirs is not None and len(p.get(theirs, FV.Bushes)) == len(bushes)
            and [s.get_name() for s in p.get(theirs, FV.RustleSounds) if s]
            == list(GRASS_RUSTLE.names))
    if not bushes:
        return

    # --- a walk in the open, and one from inside a bush --------------------------
    # The player starts clear of every bush (bush_placement's spawn clearing).
    points = _bush_points(feet, p)
    home = player.get_actor_location()
    bush = min(points, key=lambda b: (b - home).length())
    p.set(feet, FV.StrideCm, STRIDE_CM)
    seen = []
    yield from _walk(p, player, feet, seen)
    gone = (player.get_actor_location() - home).length()
    p.check("walked in the open, no footfall is InBush",
            gone > 2 * STRIDE_CM and not any(seen),
            f"{sum(seen)} of {len(seen)} frames, {gone:.1f} cm walked, the nearest bush "
            f"{(bush - home).length():.0f} cm off")
    player.set_actor_location(bush + unreal.Vector(0.0, 0.0, STAND_CM), False, True)
    at = player.get_actor_location()
    seen = []
    yield from _walk(p, player, feet, seen)
    gone = (player.get_actor_location() - at).length()
    p.check("walked from inside a bush, a footfall is InBush",
            any(seen), f"{sum(seen)} of {len(seen)} frames, {gone:.1f} cm walked")

    # --- the heartbeat -----------------------------------------------------------
    health = p.component(player, HEALTH_CLASS_PATH)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("at full health the heartbeat has never come due, and with the run key up "
            "neither has the breath",
            p.get(health, HV.HeartbeatNextTime) == 0.0 and p.get(wc, WV.BreathNextTime) == 0.0,
            f"{p.get(health, HV.HeartbeatNextTime)}, {p.get(wc, WV.BreathNextTime)}")
    p.set(health, HV.Health, p.get(health, HV.MaxHealth) * LOW_HEALTH_FRACTION * 0.5)
    yield lambda: p.get(health, HV.HeartbeatNextTime) > 0.0
    due = p.get(health, HV.HeartbeatNextTime)
    now = unreal.GameplayStatics.get_time_seconds(player)
    p.check(f"badly hurt, it is played: next due {HEARTBEAT_S:g} s on",
            abs(due - now - HEARTBEAT_S) < 0.5, f"due {due:.2f}, now {now:.2f}")
    yield 0.3
    p.check("...and not again before then",
            p.get(health, HV.HeartbeatNextTime) == due)
    p.check("the player holds the heartbeat's take",
            len([s for s in p.get(health, HV.HeartbeatSounds) if s]) == 1)
