"""The corpse loot table as build_survival.py wrote it onto BP_HealthComponent
(loot/install.py), against loot/tables.py. The roll itself is verify_weapons'
(combat/verify/loot.py)."""

from combat.paths import HEALTH_BP_PATH
from combat.verify.common import BEL, cdo, check, load
from loot.consts import LOOT_CHANCES_VAR, LOOT_TABLE_NAMES_VAR, LOOT_TABLE_VAR
from loot.tables import WANDERER_LOOT
from survival.paths import CANTEEN_BP_PATH


def run():
    health = cdo(load(HEALTH_BP_PATH))
    items = list(health.get_editor_property(LOOT_TABLE_VAR))
    chances = [float(c) for c in health.get_editor_property(LOOT_CHANCES_VAR)]
    names = [str(n) for n in health.get_editor_property(LOOT_TABLE_NAMES_VAR)]
    want = [BEL.generated_class(load(e.item_bp)).get_path_name() for e in WANDERER_LOOT]
    got = [c.get_path_name() if c else None for c in items]
    check(f"the wanderers' loot table holds its {len(WANDERER_LOOT)} entries, in order",
          got == want, f"{got} vs {want}")
    check("...one chance and one name per entry",
          len(chances) == len(items) == len(names), f"{len(chances)}, {len(names)}")
    check("...each chance the table's", chances == [e.chance for e in WANDERER_LOOT],
          str(chances))
    shown = [str(cdo(load(e.item_bp)).get_editor_property("DisplayName"))
             for e in WANDERER_LOOT]
    check("...named as the inventory names the item", names == shown,
          f"{names} vs {shown}")
    water = [e.chance for e in WANDERER_LOOT if e.item_bp == CANTEEN_BP_PATH]
    check("half the wanderers carry water (a canteen at 50%)", water == [0.5], str(water))
