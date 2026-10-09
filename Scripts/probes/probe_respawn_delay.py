"""A killed wanderer's replacement comes after RespawnDelay, not with the death.

One wanderer's Health is written to 0. The pack's spawn counter (the
GameMode's NpcSpawnCount, bumped by every wanderer's BeginPlay) must stay put
while the wait runs -- the body is already Dead and down -- and go up by one
once it is over.

The wait is shortened to PROBE_DELAY_S on that one wanderer: a headless
game's clock advances a tiny fixed step per frame, so the real ten seconds
would outlast the run. The default is the verifier's to check
(combat/verify/health.py); this proves the Delay reads the variable and
gates the spawn.

"No sooner than the delay" is measured in game time, from the frame the
component marks itself Dead to the frame the counter moves.
"""

SYSTEMS = ('health',)

import unreal

from combat.game_state import SPAWN_COUNT_VAR
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat.respawn import RESPAWN_BAND, RESPAWN_DELAY, RESPAWN_DELAY_VAR
from combat import health_vars as HV

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, RESPAWN_DELAY_VAR)]

PROBE_DELAY_S = 1.0
EARLY_FRACTION = 0.6     # how far into the wait "still none" is checked


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c.get_controlled_pawn() for c in ctrls
            if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def _navmesh(p):
    return unreal.NavigationSystemV1.get_random_location_in_navigable_radius(
        p.world(), p.pawn().get_actor_location(), RESPAWN_BAND[1]) is not None


def probe(p):
    yield lambda: len(_wanderers(p)) > 0
    yield 0.5
    # A headless -game run was found with no navmesh tiles at all, and none
    # being built (probe_npc_strafe.py); with none, a dead wanderer is
    # deliberately not replaced. RebuildNavigation builds them in a few seconds.
    if not _navmesh(p):
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh round the player: sent RebuildNavigation")
    yield lambda: _navmesh(p)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    mode = p.game_mode()
    victim = _wanderers(p)[0]
    theirs = p.component(victim, HEALTH_CLASS_PATH)
    p.check(f"a wanderer waits {RESPAWN_DELAY:.0f} s for its replacement by default",
            abs(p.get(theirs, RESPAWN_DELAY_VAR) - RESPAWN_DELAY) < 1e-6,
            f"{p.get(theirs, RESPAWN_DELAY_VAR)}")

    p.set(theirs, RESPAWN_DELAY_VAR, PROBE_DELAY_S)
    before = p.get(mode, SPAWN_COUNT_VAR)
    p.set(theirs, "Health", 0.0)
    yield lambda: p.get(theirs, "Dead")
    died = now()
    p.check("it dies at once", p.get(theirs, "Dead"))

    yield lambda: now() - died >= PROBE_DELAY_S * EARLY_FRACTION
    p.check("partway through the wait, no replacement has spawned",
            p.get(mode, SPAWN_COUNT_VAR) == before,
            f"{now() - died:.2f} s after the death, spawn count "
            f"{before} -> {p.get(mode, SPAWN_COUNT_VAR)}")

    yield lambda: (p.get(mode, SPAWN_COUNT_VAR) > before
                   or now() - died > PROBE_DELAY_S * 4)
    waited = now() - died
    p.check("once the wait is over, exactly one replacement spawns",
            p.get(mode, SPAWN_COUNT_VAR) == before + 1,
            f"spawn count {before} -> {p.get(mode, SPAWN_COUNT_VAR)}")
    p.check("...no sooner than the delay",
            waited >= PROBE_DELAY_S - 0.05, f"{waited:.2f} s after the death")
    p.check("...and the body is still there",
            unreal.SystemLibrary.is_valid(victim))
