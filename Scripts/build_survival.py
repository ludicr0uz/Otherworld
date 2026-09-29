"""
build_survival.py -- hunger, thirst, food, water and debuffs.

Run inside the editor, AFTER build_weapons_and_combat.py:
    python3 Scripts/dev/uepy.py Scripts/build_survival.py

This file is only the entry point: main() runs the steps in dependency order.
The code is the ``survival`` package next to it -- Scripts/survival/__init__.py
maps which module owns what. Checked by verify_survival.py.

WHAT THIS BUILDS
----------------
/Game/Survival
  GE_Starving, GE_Dehydrated   infinite GameplayEffects (the debuffs)
  M_MushroomCap, M_MushroomStem, M_Canteen
  BP_ConsumableItem            child of BP_WeaponItem: Consumable, restores
  BP_Mushroom, BP_WaterCanteen the food and the water
  BP_SurvivalComponent         Hunger/Thirst/Temperature, decay, debuffs
  GA_ConsumeItem               GameplayAbility, triggered by Event.Item.Consume
and installs an AbilitySystemComponent on the player and the wanderer, plus
BP_SurvivalComponent on the player.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# A live editor keeps imported modules between runs: drop both packages so an
# edit to any of their modules is what actually runs.
for _name in [m for m in sys.modules if m.split(".")[0] in ("combat", "survival")]:
    del sys.modules[_name]

from combat.graph import BEL, _apply_defaults, _log                 # noqa: E402
from survival.consumables import build_consumables                 # noqa: E402
from survival.consume_ability import build_consume_ability         # noqa: E402
from survival.effects import build_debuff_effects                  # noqa: E402
from survival.install import install_survival                      # noqa: E402
from survival.survival_component import build_survival_component   # noqa: E402


def main():
    effects = build_debuff_effects()
    _base, items = build_consumables()
    survival_bp = build_survival_component()
    # After the component: the ability casts to it.
    ability_bp = build_consume_ability()
    # ...which is why these are written afterwards rather than at build time,
    # the same way combat writes BP_HealthComponent.AmmoClass.
    _apply_defaults(survival_bp, {
        **{var: BEL.generated_class(bp) for var, bp in effects.items()},
        "ConsumeAbility": BEL.generated_class(ability_bp),
    })
    install_survival(survival_bp)
    _log(f"done -- {', '.join(items)}, hunger, thirst, temperature, "
         f"{len(effects)} debuffs and GA_ConsumeItem")


if __name__ == "__main__":
    main()
