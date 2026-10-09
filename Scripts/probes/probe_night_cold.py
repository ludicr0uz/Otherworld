"""The night is cold: the player's Temperature falls at night by the cycle's
NightTemperatureDropPerSecond, and not by day.

Clock is written to jump to noon and to midnight. The rate is raised for the
run (a headless game's time moves in tiny steps, and the built 0.1 a second
would not show in a probe's fraction of a second), and the fall is measured
against game time, not wall clock.

  - the built rate is world_config's;
  - at noon the Temperature holds;
  - at midnight it falls by rate x the game time that passed;
  - at rate 0 it holds at midnight too (the rate is the magnitude);
  - a huge rate stops at 0, not below.
"""

SYSTEMS = ('survival',)

from survival.paths import SURVIVAL_CLASS_PATH
from world import world_config as cfg
from world.day_night_blueprint import NIGHT_COLD_VAR
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world import day_night_vars as DV

WRITABLE = [(DAY_NIGHT_BP_PATH, DV.Clock), (DAY_NIGHT_BP_PATH, NIGHT_COLD_VAR)]

RATE = 20.0
SETTLE = 0.1
WATCH = 0.3


def _watch(p, survival):
    """(Temperature lost, game seconds passed) over WATCH."""
    import unreal
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    temp0 = p.get(survival, "Temperature")
    yield WATCH
    return (temp0 - p.get(survival, "Temperature"),
            unreal.GameplayStatics.get_time_seconds(p.world()) - t0)


def probe(p):
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    survival = p.component(p.pawn(), SURVIVAL_CLASS_PATH)
    built = p.get(cycle, NIGHT_COLD_VAR)
    p.check("the cycle's night cold is world_config's",
            abs(built - cfg.NIGHT_TEMPERATURE_DROP_PER_S) < 1e-6,
            f"{built} vs {cfg.NIGHT_TEMPERATURE_DROP_PER_S}")
    noon, midnight = cfg.DAY_LENGTH_S / 2, cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S / 2

    p.set(cycle, NIGHT_COLD_VAR, RATE)
    p.set(cycle, "Clock", noon)
    yield SETTLE
    lost, dt = yield from _watch(p, survival)
    p.check("noon: the Temperature holds", lost == 0.0 and p.get(cycle, "IsDay"),
            f"lost {lost} in {dt:.3f} s at {p.get(survival, 'Temperature')}")

    p.set(cycle, "Clock", midnight)
    yield SETTLE
    lost, dt = yield from _watch(p, survival)
    p.check("midnight: it falls by the rate x the game time that passed",
            dt > 0 and lost > 0 and abs(lost - RATE * dt) <= 0.25 * RATE * dt + 1e-3,
            f"lost {lost:.4f} in {dt:.4f} s, {RATE} a second wants {RATE * dt:.4f}")

    p.set(cycle, NIGHT_COLD_VAR, 0.0)
    yield SETTLE
    lost, dt = yield from _watch(p, survival)
    p.check("midnight, rate 0: it holds", lost == 0.0 and not p.get(cycle, "IsDay"),
            f"lost {lost} in {dt:.3f} s")

    p.set(cycle, NIGHT_COLD_VAR, 1.0e7)
    yield lambda: p.get(survival, "Temperature") <= 0.0
    yield SETTLE
    p.check("a huge rate stops at 0, not below", p.get(survival, "Temperature") == 0.0,
            repr(p.get(survival, "Temperature")))
