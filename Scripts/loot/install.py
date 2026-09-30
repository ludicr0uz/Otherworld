"""Writing the loot tables onto BP_HealthComponent's defaults.

Run by build_survival.py, the last builder to make an item, so every class a
table names exists. build_weapons_and_combat.py re-declares the variables and
so empties the table: re-run build_survival.py after it (the documented order).
The names come off each item's own DisplayName, so the loot window says what
the inventory will.
"""

import unreal

from combat.graph import BEL, _apply_defaults, _log, _must_load
from combat.paths import HEALTH_BP_PATH
from loot.consts import LOOT_CHANCES_VAR, LOOT_TABLE_NAMES_VAR, LOOT_TABLE_VAR
from loot.tables import WANDERER_LOOT


def table_rows(table=WANDERER_LOOT):
    """(class, chance, name) per entry, each class loaded or raising."""
    rows = []
    for entry in table:
        if not 0.0 <= entry.chance <= 1.0:
            raise ValueError(f"loot chance {entry.chance} for {entry.item_bp} is not 0..1")
        cls = BEL.generated_class(_must_load(entry.item_bp))
        name = str(unreal.get_default_object(cls).get_editor_property("DisplayName"))
        rows.append((cls, float(entry.chance), name))
    return rows


def fill_loot_tables():
    rows = table_rows()
    health_bp = _must_load(HEALTH_BP_PATH)
    _apply_defaults(health_bp, {
        LOOT_TABLE_VAR: [c for c, _p, _n in rows],
        LOOT_CHANCES_VAR: [p for _c, p, _n in rows],
        LOOT_TABLE_NAMES_VAR: [n for _c, _p, n in rows],
    })
    _log(f"{HEALTH_BP_PATH}.{LOOT_TABLE_VAR} -> "
         f"{', '.join(f'{n} {p * 100:.0f}%' for _c, p, n in rows)}")
    return health_bp
