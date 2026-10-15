"""The hip burst's bloom (Scripts/combat/bloom_tuning.py): a burst of either
automatic grows the cloud to its cap, holds between its own rounds, and a
brief stop brings it back down smoothly.
"""

import unittest

import _paths  # noqa: F401

from combat import bloom_tuning as B
from combat.tuning import RIFLE_FIRE_INTERVAL, SMG_FIRE_INTERVAL

DT = 1.0 / 60.0


def _burst(bloom, interval, rounds):
    """``rounds`` rounds ``interval`` apart, frame by frame."""
    since = 0.0
    for _ in range(rounds):
        bloom = B.bloom_shot(bloom)
        since = 0.0
        t = 0.0
        while t + DT <= interval:
            since += DT
            t += DT
            bloom = B.bloom_rest(bloom, since, DT)
    return bloom


def _rest(bloom, seconds):
    since, trace = 0.0, [bloom]
    for _ in range(int(round(seconds / DT))):
        since += DT
        bloom = B.bloom_rest(bloom, since, DT)
        trace.append(bloom)
    return bloom, trace


class BloomTuning(unittest.TestCase):
    def test_each_round_widens_the_cloud_up_to_the_cap(self):
        for interval in (SMG_FIRE_INTERVAL, RIFLE_FIRE_INTERVAL):
            one, five = _burst(0.0, interval, 1), _burst(0.0, interval, 5)
            self.assertAlmostEqual(one, B.BLOOM_PER_SHOT)
            self.assertAlmostEqual(five, 5 * B.BLOOM_PER_SHOT)
            self.assertAlmostEqual(_burst(0.0, interval, 60), B.BLOOM_MAX)
            self.assertAlmostEqual(B.spread_scale(B.BLOOM_MAX), 1.0 + B.BLOOM_MAX)

    def test_a_burst_does_not_settle_between_its_own_rounds(self):
        self.assertGreater(B.BLOOM_HOLD_S, max(SMG_FIRE_INTERVAL, RIFLE_FIRE_INTERVAL))

    def test_a_brief_stop_settles_it_smoothly(self):
        bloom, trace = _rest(B.BLOOM_MAX, B.BLOOM_HOLD_S + 0.5)
        self.assertLess(bloom, 0.1 * B.BLOOM_MAX)
        steps = [a - b for a, b in zip(trace, trace[1:])]
        self.assertTrue(all(s >= 0.0 for s in steps))
        # No step takes more than a tenth of what was there: a fall, not a cut.
        self.assertTrue(all(s <= 0.1 * a + 1e-12 for s, a in zip(steps, trace)))
        held, _ = _rest(B.BLOOM_MAX, B.BLOOM_HOLD_S - DT)
        self.assertEqual(held, B.BLOOM_MAX)


if __name__ == "__main__":
    unittest.main()
