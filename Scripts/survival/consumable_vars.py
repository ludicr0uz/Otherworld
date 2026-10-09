"""BP_ConsumableItem's member variables (what it adds to BP_WeaponItem's,
combat/item_vars.py), named once: each row is the name, the pin type and the
default (uebp/vars.py). consumables.py declares TABLE; each consumable's own
numbers are its spec's (consumable_specs.py).
"""

from uebp.vars import FLOAT, Var

HungerRestore = Var("HungerRestore", FLOAT, 0.0)
ThirstRestore = Var("ThirstRestore", FLOAT, 0.0)
# Onto Health, on the EASY difficulty only (easy_heal.py).
HealthRestoreEasy = Var("HealthRestoreEasy", FLOAT, 0.0)

TABLE = (HungerRestore, ThirstRestore, HealthRestoreEasy)
