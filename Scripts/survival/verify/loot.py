"""The corpse loot table as build_survival.py wrote it onto BP_HealthComponent
(loot/install.py), against loot/tables.py. The roll itself is verify_weapons'
(combat/verify/loot.py)."""

from combat.paths import HEALTH_BP_PATH
from combat.verify.common import BEL, cdo, check, load
from loot.consts import (
    LOOT_CHANCES_VAR, LOOT_TABLE_ICONS_VAR, LOOT_TABLE_NAMES_VAR, LOOT_TABLE_TINTS_VAR,
    LOOT_TABLE_VAR,
)
from loot.tables import CLOTHING_LOOT, WANDERER_LOOT
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
    icons = list(health.get_editor_property(LOOT_TABLE_ICONS_VAR))
    tints = list(health.get_editor_property(LOOT_TABLE_TINTS_VAR))
    own = [cdo(load(e.item_bp)) for e in WANDERER_LOOT]
    check("...shown as the inventory shows the item: its Icon, tinted its SlotColor",
          len(icons) == len(tints) == len(own)
          and all(i is not None and i == o.get_editor_property("Icon")
                  and t.to_tuple() == o.get_editor_property("SlotColor").to_tuple()
                  for i, t, o in zip(icons, tints, own)),
          f"{[i.get_name() if i else None for i in icons]}")
    water = [e.chance for e in WANDERER_LOOT if e.item_bp == CANTEEN_BP_PATH]
    check("half the wanderers carry water (a canteen at 50%)", water == [0.5], str(water))
    worn = [e.chance for e in WANDERER_LOOT if e.item_bp in CLOTHING_LOOT]
    check("one wanderer in ten carries each of the jacket, the pants and the boots",
          worn == [0.1] * 3 and len(CLOTHING_LOOT) == 3, str(worn))
