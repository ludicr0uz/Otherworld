"""GE_Bleeding: a debuff that lasts, and what it costs while it does."""

import unreal

from combat.tuning import (
    BLEED_DURATION_S, BLEED_HP_PER_S, BLEED_TOTAL_HP, BLEEDING_TAG, HEALTH_DRAINS,
)
from combat.verify.common import cdo, check, load
from survival.effects import TIMED_EFFECT_PATHS, effect_duration_s
from survival.on_hit import BLEEDING, ON_HIT
from survival.paths import BLEEDING_GE_PATH


def run():
    for path, seconds in TIMED_EFFECT_PATHS.items():
        ge = load(path)
        check(f"{path} exists", ge is not None)
        if not ge:
            continue
        d = cdo(ge)
        check(f"{path} wears off: it has a duration, {seconds:g} s",
              d.get_editor_property("duration_policy")
              == unreal.GameplayEffectDurationType.HAS_DURATION
              and abs(effect_duration_s(d) - seconds) < 1e-3,
              f"{d.get_editor_property('duration_policy')}, {effect_duration_s(d)} s")
    check("bleeding lasts 3 minutes and takes 50 HP in all",
          TIMED_EFFECT_PATHS.get(BLEEDING_GE_PATH) == BLEED_DURATION_S == 180.0
          and BLEED_TOTAL_HP == 50.0
          and abs(BLEED_HP_PER_S * BLEED_DURATION_S - BLEED_TOTAL_HP) < 1e-3,
          f"{BLEED_HP_PER_S} HP/s x {BLEED_DURATION_S} s")
    check(f"the health component drains {BLEEDING_TAG} at that rate, and it is "
          f"the tag the on-hit effect grants",
          dict(HEALTH_DRAINS).get(BLEEDING_TAG) == BLEED_HP_PER_S
          and BLEEDING.tags == (BLEEDING_TAG,)
          and BLEEDING.effect_path == BLEEDING_GE_PATH)
    check("every on-hit effect's GameplayEffect exists",
          all(load(e.effect_path) is not None for row in ON_HIT.values() for e in row))
