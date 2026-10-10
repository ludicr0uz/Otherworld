"""clothing/scatter.py: where the garments found in the forest go. Pure, so
its count, its seed and its spacing are held here, without an editor.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import math
import random
import unittest

import _paths  # noqa: F401

from clothing import scatter as S


def _forest(side_cm, trees, seed=3):
    rng = random.Random(seed)
    return [(rng.uniform(0.0, side_cm), rng.uniform(0.0, side_cm)) for _ in range(trees)]


def _scatter(side_cm, trees=400, **kw):
    trunks = _forest(side_cm, trees)
    start = (side_cm / 2.0, side_cm / 2.0)
    return trunks, start, S.scatter_clothing((0.0, side_cm), (0.0, side_cm),
                                             trunks, start, **kw)


class Count(unittest.TestCase):
    def test_one_a_hectare(self):
        self.assertEqual(S.garment_count(20000.0, 20000.0), 4)
        self.assertEqual(S.garment_count(100000.0, 100000.0), 100)

    def test_a_small_level_still_has_one(self):
        self.assertEqual(S.garment_count(5000.0, 5000.0), 1)
        self.assertEqual(len(_scatter(5000.0, trees=18)[2]), 1)

    def test_capped(self):
        self.assertEqual(S.garment_count(1e6, 1e6), S.MAX_GARMENTS)

    def test_every_spot_asked_for_is_placed(self):
        self.assertEqual(len(_scatter(20000.0)[2]), 4)
        self.assertEqual(len(_scatter(100000.0, trees=9000)[2]), 100)

    def test_only_the_three_drawn_garments_each_in_turn(self):
        self.assertEqual(S.SCATTER_KINDS, ("Jacket", "Pants", "Boots"))
        kinds = [k for k, _x, _y in _scatter(20000.0)[2]]
        self.assertEqual(kinds, ["Jacket", "Pants", "Boots", "Jacket"])


class Seed(unittest.TestCase):
    def test_the_same_seed_places_the_same(self):
        self.assertEqual(_scatter(20000.0)[2], _scatter(20000.0)[2])

    def test_another_seed_places_elsewhere(self):
        self.assertNotEqual(_scatter(20000.0)[2],
                            _scatter(20000.0, seed=S.SCATTER_SEED + 1)[2])


class Spacing(unittest.TestCase):
    def setUp(self):
        self.side = 100000.0
        self.trunks, self.start, self.spots = _scatter(self.side, trees=9000)

    def test_apart_from_each_other(self):
        pts = [(x, y) for _k, x, y in self.spots]
        nearest = min(math.hypot(ax - bx, ay - by)
                      for i, (ax, ay) in enumerate(pts) for bx, by in pts[i + 1:])
        self.assertGreaterEqual(nearest, S.MIN_SPACING_CM)

    def test_never_inside_a_trunk(self):
        for _k, x, y in self.spots:
            self.assertGreaterEqual(
                min(math.hypot(x - tx, y - ty) for tx, ty in self.trunks),
                S.TRUNK_CLEAR_CM)

    def test_inside_the_edge_and_off_the_start(self):
        for _k, x, y in self.spots:
            self.assertTrue(S.EDGE_MARGIN_CM <= x <= self.side - S.EDGE_MARGIN_CM)
            self.assertTrue(S.EDGE_MARGIN_CM <= y <= self.side - S.EDGE_MARGIN_CM)
            self.assertGreaterEqual(math.hypot(x - self.start[0], y - self.start[1]),
                                    S.START_CLEAR_CM)

    def test_keeps_off_what_already_lies_there(self):
        taken = [(x, y) for _k, x, y in self.spots]
        again = S.scatter_clothing((0.0, self.side), (0.0, self.side), self.trunks,
                                   self.start, avoid=taken)
        for _k, x, y in again:
            self.assertGreaterEqual(min(math.hypot(x - ax, y - ay) for ax, ay in taken),
                                    S.AVOID_CLEAR_CM)


if __name__ == "__main__":
    unittest.main()
