"""Where things are put in a level, on the probes' 50 m level as on the 200 m
one: the forage (survival/forage_placement.py), the garments
(clothing/scatter.py) and the zombies (forest_generator/npc_placement.py).
Each keeps off the trunks, inside the edge and off the player start, and a
count per hectare never rounds to nothing on a quarter of one. Pure, so it is
held here without an editor; the fake forest is test_clothing_scatter.py's.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import math
import random
import types
import unittest

import _paths  # noqa: F401

from clothing import scatter as C
from forest_generator import npc_placement as N
from survival import forage_placement as F
from survival import tuning as ST

# (name, side in cm, trees, zombies asked for): Lvl_Probe_50m has 18 trees.
LEVELS = (("50 m", 5000.0, 18, 3), ("200 m", 20000.0, 400, N.NPC_COUNT))


def _forest(side_cm, trees, seed=3):
    rng = random.Random(seed)
    return [(rng.uniform(0.0, side_cm), rng.uniform(0.0, side_cm)) for _ in range(trees)]


def _nearest(x, y, points):
    return min(math.hypot(x - px, y - py) for px, py in points)


class _Scattered(unittest.TestCase):
    """The three rules of a scatter over (0, side): subclasses say how."""

    def scatter(self, side, trunks, start):
        raise NotImplementedError

    def trunk_clear(self, kind):
        raise NotImplementedError

    edge_margin = start_clear = None

    def _levels(self):
        for name, side, trees, _zombies in LEVELS:
            trunks, start = _forest(side, trees), (side / 2.0, side / 2.0)
            spots = self.scatter(side, trunks, start)
            self.assertTrue(spots, f"{name}: nothing was placed")
            yield name, side, trunks, start, spots

    def test_clear_of_every_trunk(self):
        for name, _side, trunks, _start, spots in self._levels():
            for kind, x, y in spots:
                with self.subTest(level=name, item=kind):
                    self.assertGreaterEqual(
                        _nearest(x, y, trunks), self.trunk_clear(kind),
                        f"{name}: {kind} at ({x:.0f}, {y:.0f}) is inside its trunk clearance")

    def test_inside_the_edge_margin(self):
        for name, side, _trunks, _start, spots in self._levels():
            margin = min(self.edge_margin, 0.1 * side)
            for kind, x, y in spots:
                with self.subTest(level=name, item=kind):
                    self.assertTrue(
                        margin <= x <= side - margin and margin <= y <= side - margin,
                        f"{name}: {kind} at ({x:.0f}, {y:.0f}) is in the {margin:.0f} cm edge margin")

    def test_off_the_player_start(self):
        for name, side, _trunks, start, spots in self._levels():
            clear = min(self.start_clear, 0.12 * side)
            for kind, x, y in spots:
                with self.subTest(level=name, item=kind):
                    self.assertGreaterEqual(
                        math.hypot(x - start[0], y - start[1]), clear,
                        f"{name}: {kind} at ({x:.0f}, {y:.0f}) is within {clear:.0f} cm of the start")


class ForageCounts(unittest.TestCase):
    def test_at_least_one_of_each_on_both_levels(self):
        for name, side, _trees, _zombies in LEVELS:
            mushrooms, canteens = F.forage_counts(side, side)
            with self.subTest(level=name):
                self.assertGreaterEqual(mushrooms, 1, f"{name}: forage_counts gives no Mushroom")
                self.assertGreaterEqual(canteens, 1, f"{name}: forage_counts gives no Canteen")

    def test_per_hectare_and_capped(self):
        self.assertEqual(F.forage_counts(20000.0, 20000.0),
                         (round(4 * ST.MUSHROOMS_PER_HECTARE), round(4 * ST.CANTEENS_PER_HECTARE)),
                         "200 m is 4 ha: Mushroom and Canteen per hectare")
        self.assertEqual(F.forage_counts(1e6, 1e6), (ST.MAX_MUSHROOMS, ST.MAX_CANTEENS),
                         "a huge level: MAX_MUSHROOMS and MAX_CANTEENS")


class Forage(_Scattered):
    edge_margin = ST.FORAGE_EDGE_MARGIN_CM
    start_clear = ST.FORAGE_START_CLEAR_CM

    def scatter(self, side, trunks, start):
        return F.scatter_forage((0.0, side), (0.0, side), trunks, start)

    def trunk_clear(self, kind):
        # A mushroom grows at the foot of its tree, in MUSHROOM_TRUNK_RING_CM;
        # anything else is never closer than TRUNK_CLEAR_CM.
        return 0.8 * ST.MUSHROOM_TRUNK_RING_CM[0] if kind == "Mushroom" else F.TRUNK_CLEAR_CM

    def test_every_one_counted_is_placed(self):
        for name, side, _trunks, _start, spots in self._levels():
            kinds = [k for k, _x, _y in spots]
            with self.subTest(level=name):
                self.assertEqual((kinds.count("Mushroom"), kinds.count("Canteen")),
                                 F.forage_counts(side, side),
                                 f"{name}: Mushroom and Canteen placed against forage_counts")

    def test_a_mushroom_is_at_the_foot_of_a_tree(self):
        for name, _side, trunks, _start, spots in self._levels():
            for kind, x, y in spots:
                if kind == "Mushroom":
                    with self.subTest(level=name):
                        self.assertLessEqual(
                            _nearest(x, y, trunks), ST.MUSHROOM_TRUNK_RING_CM[1],
                            f"{name}: Mushroom at ({x:.0f}, {y:.0f}) is outside "
                            "MUSHROOM_TRUNK_RING_CM of any tree")

    def test_apart_from_each_other(self):
        for name, _side, _trunks, _start, spots in self._levels():
            pts = [(x, y) for _k, x, y in spots]
            for i, (x, y) in enumerate(pts[:-1]):
                with self.subTest(level=name, item=spots[i][0]):
                    self.assertGreaterEqual(
                        _nearest(x, y, pts[i + 1:]), ST.FORAGE_MIN_SPACING_CM,
                        f"{name}: {spots[i][0]} at ({x:.0f}, {y:.0f}) is within "
                        "FORAGE_MIN_SPACING_CM of another")


class Clothing(_Scattered):
    edge_margin = C.EDGE_MARGIN_CM
    start_clear = C.START_CLEAR_CM

    def scatter(self, side, trunks, start):
        return C.scatter_clothing((0.0, side), (0.0, side), trunks, start)

    def trunk_clear(self, kind):
        return C.TRUNK_CLEAR_CM

    def test_every_one_counted_is_placed(self):
        for name, side, _trunks, _start, spots in self._levels():
            with self.subTest(level=name):
                self.assertGreaterEqual(C.garment_count(side, side), 1,
                                        f"{name}: garment_count gives no garment")
                self.assertEqual(len(spots), C.garment_count(side, side),
                                 f"{name}: garments placed against garment_count")


class Zombies(unittest.TestCase):
    """place_npcs works about the origin, the player start at it, and its
    trunk clearance is from the trunk's surface."""

    def _levels(self):
        for name, side, trees, count in LEVELS:
            half = side / 2.0
            forest = [types.SimpleNamespace(x=x - half, y=y - half, scale=1.0)
                      for x, y in _forest(side, trees)]
            lo, hi, _clamped = N.spawn_band(side)
            placed = N.place_npcs(side, [[0.0] * 3 for _ in range(3)], 2,
                                  placed_trees=forest, count=count,
                                  min_distance_cm=lo, max_distance_cm=hi)
            yield name, side, forest, count, (lo, hi), placed

    def test_every_one_asked_for_is_placed(self):
        for name, _side, _forest_, count, _band, placed in self._levels():
            with self.subTest(level=name):
                self.assertEqual(len(placed), count,
                                 f"{name}: zombies placed against the {count} asked for")

    def test_clear_of_every_trunk(self):
        for name, _side, forest, _count, _band, placed in self._levels():
            for i, npc in enumerate(placed, start=1):
                gap = min(math.hypot(npc.x - t.x, npc.y - t.y)
                          - N.NOMINAL_TRUNK_RADIUS_PER_SCALE_CM * t.scale for t in forest)
                with self.subTest(level=name, zombie=i):
                    self.assertGreaterEqual(
                        gap, N.TRUNK_CLEARANCE_CM,
                        f"{name}: zombie {i} at ({npc.x:.0f}, {npc.y:.0f}) is inside "
                        "TRUNK_CLEARANCE_CM of a trunk")

    def test_inside_the_edge_margin(self):
        for name, side, _forest_, _count, _band, placed in self._levels():
            usable = N.npc_usable_radius(side)
            self.assertLessEqual(usable, N.EDGE_MARGIN_FRACTION * side / 2.0)
            for i, npc in enumerate(placed, start=1):
                with self.subTest(level=name, zombie=i):
                    self.assertTrue(
                        abs(npc.x) <= usable and abs(npc.y) <= usable,
                        f"{name}: zombie {i} at ({npc.x:.0f}, {npc.y:.0f}) is outside "
                        f"the usable {usable:.0f} cm (EDGE_MARGIN_FRACTION)")

    def test_off_the_player_start(self):
        for name, side, _forest_, _count, (lo, hi), placed in self._levels():
            self.assertGreaterEqual(lo, N.MIN_PLAYER_DISTANCE_FRACTION * N.npc_usable_radius(side),
                                    f"{name}: the spawn band starts too near the start")
            for i, npc in enumerate(placed, start=1):
                away = math.hypot(npc.x, npc.y)
                with self.subTest(level=name, zombie=i):
                    self.assertTrue(
                        lo - 1e-6 <= away <= hi + 1e-6,
                        f"{name}: zombie {i} is {away:.0f} cm from the start, outside "
                        f"the spawn band {lo:.0f}-{hi:.0f}")

    def test_apart_from_each_other(self):
        for name, _side, _forest_, _count, _band, placed in self._levels():
            for i, a in enumerate(placed, start=1):
                for b in placed[i:]:
                    with self.subTest(level=name, zombie=i):
                        self.assertGreaterEqual(
                            math.hypot(a.x - b.x, a.y - b.y), N.NPC_MIN_SEPARATION_CM,
                            f"{name}: zombie {i} is within NPC_MIN_SEPARATION_CM of another")


del _Scattered      # the base holds no level of its own: not a test case to run


if __name__ == "__main__":
    unittest.main()
