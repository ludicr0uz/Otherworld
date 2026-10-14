"""Where each grass type grows (forest_generator/grass_regions.py): the same
for a seed, stretches held by one type, seams where types mix, and every
type leading somewhere."""

import unittest

import _paths  # noqa: F401

from forest_generator import grass_regions as R

TYPES = 7
SEED = 42


def _sample(mix, size_cm=100000, step_cm=1000):
    """The shares at each point of a grid over a 1 km map."""
    half = size_cm // 2
    return [mix.shares(x, y) for x in range(-half, half, step_cm)
            for y in range(-half, half, step_cm)]


class Fields(unittest.TestCase):
    def test_the_noise_is_in_range_and_fixed(self):
        for x, y in ((0, 0), (1234.5, -9876.0), (-50000, 50000)):
            v = R.field(7, x, y)
            self.assertTrue(0.0 <= v < 1.0, v)
            self.assertEqual(v, R.field(7, x, y))
        # A fixed integer hash, not Python's: these never move between runs.
        self.assertAlmostEqual(R.value_noise(1, 0, 0, 100), R._lattice(1, 0, 0))

    def test_the_noise_is_smooth(self):
        a = R.field(3, 10000, 10000)
        b = R.field(3, 10000 + R.SAMPLE_STEP_CM, 10000)
        self.assertLess(abs(a - b), 0.1)


class Mix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shares = _sample(R.RegionMix(SEED, [1.0] * TYPES))

    def test_the_shares_sum_to_one(self):
        for s in self.shares[::50]:
            self.assertAlmostEqual(sum(s), 1.0)
            self.assertEqual(len(s), TYPES)

    def test_the_same_seed_gives_the_same_ground(self):
        again = R.RegionMix(SEED, [1.0] * TYPES)
        other = R.RegionMix(SEED + 1, [1.0] * TYPES)
        self.assertEqual(again.shares(1500, -2500),
                         R.RegionMix(SEED, [1.0] * TYPES).shares(1500, -2500))
        diff = sum(abs(a - b) for a, b in zip(again.shares(1500, -2500),
                                              other.shares(1500, -2500)))
        self.assertGreater(diff, 0.0)

    def test_most_of_the_ground_is_held_by_one_type(self):
        held = sum(max(s) > 0.7 for s in self.shares) / len(self.shares)
        self.assertTrue(0.35 <= held <= 0.75, held)

    def test_some_of_the_ground_is_mixed(self):
        mixed = sum(max(s) < 0.5 for s in self.shares) / len(self.shares)
        self.assertTrue(0.05 <= mixed <= 0.35, mixed)

    def test_every_type_leads_somewhere(self):
        leads = [0] * TYPES
        for s in self.shares:
            leads[s.index(max(s))] += 1
        for n in leads:
            self.assertTrue(0.07 <= n / len(self.shares) <= 0.25, leads)

    def test_a_base_weight_scales_its_type(self):
        heavy = _sample(R.RegionMix(SEED, [3.0] + [1.0] * (TYPES - 1)), step_cm=2500)
        even = _sample(R.RegionMix(SEED, [1.0] * TYPES), step_cm=2500)
        self.assertGreater(sum(s[0] for s in heavy), sum(s[0] for s in even))


if __name__ == "__main__":
    unittest.main()
