"""Writing the loot tables onto BP_HealthComponent's defaults.

Run by build_survival.py, the last builder to make an item, so every class a
table names exists. build_weapons_and_combat.py re-declares the variables and
so empties the table: re-run build_survival.py after it (the documented order).
The name, the icon and its tint come off each item's own DisplayName, Icon and
SlotColor, so the loot window shows what the inventory will.
"""

import unreal

from combat.log import _log
from uebp.graph import BEL, _apply_defaults, _must_load
from combat.paths import HEALTH_BP_PATH
from loot.consts import (
    LOOT_CHANCES_VAR, LOOT_TABLE_ICONS_VAR, LOOT_TABLE_NAMES_VAR, LOOT_TABLE_TINTS_VAR,
    LOOT_TABLE_VAR,
)
from loot.tables import WANDERER_LOOT


def table_rows(table=WANDERER_LOOT):
    """(class, chance, name, icon, tint) per entry, each class loaded or
    raising; so does an item without an icon, which the window could not show."""
    rows = []
    for entry in table:
        if not 0.0 <= entry.chance <= 1.0:
            raise ValueError(f"loot chance {entry.chance} for {entry.item_bp} is not 0..1")
        cls = BEL.generated_class(_must_load(entry.item_bp))
        item = unreal.get_default_object(cls)
        icon = item.get_editor_property("Icon")
        if icon is None:
            raise RuntimeError(f"{entry.item_bp} has no Icon for the loot window")
        rows.append((cls, float(entry.chance), str(item.get_editor_property("DisplayName")),
                     icon, item.get_editor_property("SlotColor")))
    return rows


def fill_loot_tables():
    rows = table_rows()
    health_bp = _must_load(HEALTH_BP_PATH)
    _apply_defaults(health_bp, {
        LOOT_TABLE_VAR: [r[0] for r in rows],
        LOOT_CHANCES_VAR: [r[1] for r in rows],
        LOOT_TABLE_NAMES_VAR: [r[2] for r in rows],
        LOOT_TABLE_ICONS_VAR: [r[3] for r in rows],
        LOOT_TABLE_TINTS_VAR: [r[4] for r in rows],
    })
    _log(f"{HEALTH_BP_PATH}.{LOOT_TABLE_VAR} -> "
         f"{', '.join(f'{r[2]} {r[1] * 100:.0f}%' for r in rows)}")
    return health_bp
