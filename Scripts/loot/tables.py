"""The loot tables: what a killed creature may carry, and how likely each is.

Constants only. A table is a tuple of LootEntry; every entry is rolled on its
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

# item_bp: the item's Blueprint (a BP_WeaponItem child); chance: 0..1 per kill.
LootEntry = namedtuple("LootEntry", "item_bp chance")

WANDERER_LOOT = (
    # Water: half the wanderers carry a canteen.
    LootEntry(CANTEEN_BP_PATH, 0.5),
)
