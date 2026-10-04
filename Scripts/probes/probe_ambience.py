"""The forest's sound follows the light: the cycle's three beds are playing,
and the day's and the night's swap as the clock goes round.

Clock is written to jump to noon and to midnight, as probe_night_cold does.
A headless game has no audio device to listen to, so what is read is what
the Tick wrote: each bed component's volume multiplier.

  - the three beds are on the cycle, each with its wave, and playing;
  - at noon the day's bed is at 1 and the night's at 0;
  - at midnight the night's is at 1 and the day's at 0;
  - the wind is at 1 at both.
"""

from world import world_config as cfg
from Sound.sound_world import BEDS, BED_DAY_COMP, BED_NIGHT_COMP, BED_WIND_COMP
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world import day_night_vars as DV

WRITABLE = [(DAY_NIGHT_BP_PATH, DV.Clock)]

SETTLE = 0.2


def _volumes(cycle):
    import unreal
    found = {c.get_name(): c for c in cycle.get_components_by_class(unreal.AudioComponent)}
    return found, {name: found[name].get_editor_property("volume_multiplier")
                   for name, _wave in BEDS if name in found}


def probe(p):
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    found, _ = _volumes(cycle)
    waves = {name: (found[name].get_editor_property("sound").get_name()
                    if name in found and found[name].get_editor_property("sound") else None)
             for name, _wave in BEDS}
    p.check("the cycle carries the three beds, each with its wave",
            all(waves[name] == wave for name, wave in BEDS), str(waves))
    p.check("...and each is active from the level's start",
            all(name in found and found[name].is_active() for name, _wave in BEDS),
            str({name: found[name].is_active() for name in found}))

    noon, midnight = cfg.DAY_LENGTH_S / 2, cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S / 2
    p.set(cycle, "Clock", noon)
    yield SETTLE
    _, at_noon = _volumes(cycle)
    p.check("noon: the day's bed is at 1, the night's at 0",
            abs(at_noon[BED_DAY_COMP] - 1.0) < 1e-3 and abs(at_noon[BED_NIGHT_COMP]) < 1e-3,
            str(at_noon))

    p.set(cycle, "Clock", midnight)
    yield SETTLE
    _, at_midnight = _volumes(cycle)
    p.check("midnight: the night's bed is at 1, the day's at 0",
            abs(at_midnight[BED_NIGHT_COMP] - 1.0) < 1e-3 and abs(at_midnight[BED_DAY_COMP]) < 1e-3,
            str(at_midnight))
    p.check("the wind plays on at 1, noon and midnight",
            abs(at_noon[BED_WIND_COMP] - 1.0) < 1e-3 and abs(at_midnight[BED_WIND_COMP] - 1.0) < 1e-3,
            f"{at_noon[BED_WIND_COMP]} / {at_midnight[BED_WIND_COMP]}")
