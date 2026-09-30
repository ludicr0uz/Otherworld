"""The names and numbers of corpse loot, shared by the roll, the HUD and the
checks. Constants only: no unreal, and no item paths (tables.py names the
items), so combat can import this without naming a survival asset.

The table and the body's contents are parallel arrays on BP_HealthComponent,
because Python cannot author a Blueprint struct:

    LootTable[i]       an item class a body of this kind may carry
    LootChances[i]     the chance (0..1) it does, rolled once per counted kill
    LootTableNames[i]  what the loot window calls it

    Loot[j], LootNames[j]   what this body does carry, filled at the kill
"""

LOOT_TABLE_VAR = "LootTable"
LOOT_CHANCES_VAR = "LootChances"
LOOT_TABLE_NAMES_VAR = "LootTableNames"
LOOT_VAR = "Loot"
LOOT_NAMES_VAR = "LootNames"

# How close the player must stand to a body to search it: the E pick-up's
# reach (combat.tuning.PICKUP_RADIUS), measured to the ragdoll, not the capsule.
LOOT_RADIUS = 250.0
