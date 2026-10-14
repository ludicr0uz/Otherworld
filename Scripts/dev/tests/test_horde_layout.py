"""The Horde Survival level's layout (forest_generator/horde_layout.py), on
flat ground: the ring as dense as the 1 km map's middle, a scarce clearing
with nothing in the fort, and a fort wall of chest-high rocks closed but for
three openings, each as wide as the layout asks. The same offline checks the
generator runs (horde_checks.py) must all pass on it."""

import math
import unittest

import _paths  # noqa: F401

from forest_generator import horde_layout as H
from forest_generator.horde_checks import run_horde_checks

WORLD_CM = 400 * 100.0
GRID = 10
FLAT = [[0.0] * (GRID + 1) for _ in range(GRID + 1)]


class HordeLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = H.layout_for("Lvl_Horde_Survival")
        cls.trees = H.scatter_horde_trees(cls.layout, WORLD_CM, FLAT, GRID)
        cls.rocks = H.fort_rocks(cls.layout, WORLD_CM, FLAT, GRID)

    def test_only_the_horde_level_has_a_layout(self):
        self.assertIsNotNone(self.layout)
        for level in ("Lvl_Probe_50m", "Lvl_Forest_200m", "Lvl_Forest_1000m", "Lvl_Title"):
            self.assertIsNone(H.layout_for(level))

    def test_the_offline_checks_pass(self):
        results = run_horde_checks(self.layout, self.trees, self.rocks, [], WORLD_CM)
        self.assertEqual([r.name for r in results if not r.passed], [])

    def test_nothing_grows_in_the_fort(self):
        self.assertFalse([t for t in self.trees
                          if math.hypot(t.x, t.y) < self.layout.keep_out_cm])

    def test_three_openings_each_wide_enough(self):
        widths = H.opening_widths_cm(self.rocks)
        self.assertEqual(len(widths), 3)
        self.assertGreaterEqual(min(widths), self.layout.opening_box_cm)

    def test_the_rocks_are_chest_high(self):
        lo, hi = self.layout.rock_visible_cm
        for r in self.rocks:
            self.assertTrue(lo - 1.0 <= r.top_z - r.terrain_z <= hi + 1.0, r)

    def test_the_layout_is_deterministic(self):
        again = H.fort_rocks(self.layout, WORLD_CM, FLAT, GRID)
        self.assertEqual(H.fort_rock_data(again), H.fort_rock_data(self.rocks))


if __name__ == "__main__":
    unittest.main()
