"""The crawl's legs drawn in toward the body's line (Scripts/asset_pipeline/
leg_spread.py): the angle a segment keeps, and the turn that gets it there."""

import math
import unittest

import _paths  # noqa: F401

from asset_pipeline.leg_spread import LEG_SPREAD, narrowed_turn, yaw_off_back


class LegSpread(unittest.TestCase):
    def test_angle_is_off_straight_back(self):
        self.assertAlmostEqual(yaw_off_back(0.0, -1.0), 0.0)
        self.assertAlmostEqual(yaw_off_back(1.0, -1.0), 45.0)
        self.assertAlmostEqual(yaw_off_back(-1.0, -1.0), -45.0)
        self.assertAlmostEqual(yaw_off_back(1.0, 0.0), 90.0)

    def test_a_leg_out_to_either_side_turns_in(self):
        for x in (30.0, -30.0):
            turn = narrowed_turn((x, -40.0), (x, -40.0))
            self.assertLess(turn * x, 0.0)
            kept = yaw_off_back(x, -40.0) + turn
            self.assertAlmostEqual(kept, LEG_SPREAD * math.degrees(math.atan2(x, 40.0)))

    def test_a_leg_on_the_line_stays(self):
        self.assertAlmostEqual(narrowed_turn((0.0, -50.0), (0.0, -50.0)), 0.0)

    def test_the_calf_turns_to_the_packs_angle_not_where_the_thigh_left_it(self):
        # The thigh's turn carried the calf to 10 degrees; the pack had it at 40.
        now = (math.sin(math.radians(10.0)), -math.cos(math.radians(10.0)))
        pack = (math.sin(math.radians(40.0)), -math.cos(math.radians(40.0)))
        self.assertAlmostEqual(narrowed_turn(now, pack, 0.5), 10.0)

    def test_the_spread_draws_in_but_keeps_some(self):
        self.assertTrue(0.3 < LEG_SPREAD < 1.0)


if __name__ == "__main__":
    unittest.main()
