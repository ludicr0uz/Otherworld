"""The loot tables: what a killed creature may carry, and how likely each is.

Constants, and the one list a probe forces a roll with. A table is a tuple of LootEntry; every entry is rolled on its
own, once per counted kill, so a body can carry several things or nothing.
Adding a drop is a row here; install.py writes the rows onto
BP_HealthComponent's defaults, where the roll (roll.py) reads them.

One table for now: every wanderer shares BP_HealthComponent's defaults, and a
child Blueprint's override of an inherited component is out of Python's reach
(npc/CLAUDE.md), so a per-creature table would have to travel on the AI
controller the way the hit-reaction clips do.

The gun drop is not here: it predates corpse loot and still lands on the
ground, picked up with E (combat/gun_drop.py, GUN_LOOT_TABLE in combat.tuning).
"""

from collections import namedtuple

from survival.paths import CANTEEN_BP_PATH

# The garments are named here, not imported: `clothing` imports combat, and
# neither loot nor combat may import it back. build_clothing.py makes them
# (clothing/specs.py holds the same paths; the dev unit tests compare them).
CLOTHING_DIR = "/Game/Clothing"
JACKET_BP_PATH = f"{CLOTHING_DIR}/BP_Jacket"
PANTS_BP_PATH = f"{CLOTHING_DIR}/BP_Pants"
BOOTS_BP_PATH = f"{CLOTHING_DIR}/BP_Boots"
CLOTHING_LOOT = (JACKET_BP_PATH, PANTS_BP_PATH, BOOTS_BP_PATH)
CLOTHING_CHANCE = 0.10

# item_bp: the item's Blueprint (a BP_WeaponItem child); chance: 0..1 per kill.
LootEntry = namedtuple("LootEntry", "item_bp chance")

WANDERER_LOOT = (
    # Water: half the wanderers carry a canteen.
    LootEntry(CANTEEN_BP_PATH, 0.5),
    # Clothing: one wanderer in ten carries each of the three real garments.
    *(LootEntry(path, CLOTHING_CHANCE) for path in CLOTHING_LOOT),
)


def forced_chances(*item_bps, table=WANDERER_LOOT):
    """A LootChances for one body that decides its roll: 1.0 for each entry
    named, 0.0 for the rest, one per entry (the roll reads a chance per row of
    the table, so a probe that forces a roll writes the whole list)."""
    missing = [b for b in item_bps if b not in [e.item_bp for e in table]]
    if missing:
        raise ValueError(f"not in the loot table: {missing}")
    return [1.0 if e.item_bp in item_bps else 0.0 for e in table]
