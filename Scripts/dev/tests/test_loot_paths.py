"""loot/tables.py names the garments it drops without importing `clothing`
(which imports combat, so neither loot nor combat may import it back). The
paths are written twice; this holds the two together.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import unittest

import _paths  # noqa: F401

from clothing.specs import GARMENTS
from loot.tables import CLOTHING_LOOT, WANDERER_LOOT


class LootPaths(unittest.TestCase):
    def test_each_garment_dropped_is_one_clothing_builds(self):
        built = {g.path for g in GARMENTS}
        self.assertEqual([p for p in CLOTHING_LOOT if p not in built], [])

    def test_only_garments_drawn_when_worn_are_dropped(self):
        drawn = {g.path for g in GARMENTS if g.worn is not None}
        self.assertEqual(set(CLOTHING_LOOT), drawn)

    def test_the_table_carries_them(self):
        rows = [e.item_bp for e in WANDERER_LOOT]
        self.assertEqual([p for p in CLOTHING_LOOT if p not in rows], [])


if __name__ == "__main__":
    unittest.main()
