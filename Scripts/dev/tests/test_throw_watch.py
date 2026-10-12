"""The sums probe_net_throw.py makes over a client's frames of a thrown item
(probes/throw_watch.py): the distance to the curve, the frames that showed
some other number of items than one, the frames a flying item stood still."""

import unittest

import _paths  # noqa: F401

from probes import throw_watch as W

G = -980.0
START, VEL = (0.0, 0.0, 150.0), (1500.0, 0.0, 300.0)


def frame(wall, shown, flying=True, world=None):
    return (wall, wall if world is None else world, shown, flying)


class TestCurve(unittest.TestCase):
    def test_a_point_of_the_curve_is_on_it(self):
        for t in (0.0, 0.13, 0.5, 1.9):
            self.assertLess(W.off_curve(W.on_curve(START, VEL, G, t), START, VEL, G, 4.0), 0.05)

    def test_a_point_beside_the_curve_is_that_far_off(self):
        x, y, z = W.on_curve(START, VEL, G, 0.4)
        self.assertAlmostEqual(W.off_curve((x, y + 40.0, z), START, VEL, G, 4.0), 40.0, delta=0.1)

    def test_a_point_behind_the_start_is_measured_from_the_start(self):
        self.assertAlmostEqual(W.off_curve((-30.0, 0.0, 150.0), START, VEL, G, 4.0), 30.0,
                               delta=0.5)

    def test_gravity_is_in_the_curve(self):
        x, y, _z = W.on_curve(START, VEL, G, 1.0)
        straight = (x, y, START[2] + VEL[2])
        self.assertAlmostEqual(START[2] + VEL[2] - W.on_curve(START, VEL, G, 1.0)[2], 490.0)
        self.assertGreater(W.off_curve(straight, START, VEL, G, 4.0), 100.0)


class TestFrames(unittest.TestCase):
    def test_the_worst_stand_in_is_the_one_reported_and_other_kinds_are_not_measured(self):
        on = W.on_curve(START, VEL, G, 0.2)
        frames = [frame(0.0, [(W.HAND, (9e3, 9e3, 9e3))]),
                  frame(0.1, [(W.STANDIN, on)]),
                  frame(0.2, [(W.STANDIN, (on[0], on[1] + 12.0, on[2]))])]
        self.assertAlmostEqual(W.worst_off(frames, START, VEL, G, 4.0), 12.0, delta=0.1)

    def test_a_stand_in_that_has_ended_may_be_at_the_rest_instead(self):
        rest = (500.0, 300.0, 20.0)
        frames = [frame(0.3, [(W.STANDIN, (500.0, 302.0, 20.0))], flying=False)]
        self.assertAlmostEqual(W.worst_off(frames, START, VEL, G, 4.0, rest), 2.0, delta=0.01)
        flying = [frame(0.3, [(W.STANDIN, (500.0, 302.0, 20.0))], flying=True)]
        self.assertGreater(W.worst_off(flying, START, VEL, G, 4.0, rest), 100.0)

    def test_none_and_two_are_both_miscounts_and_the_window_bounds_them(self):
        one = [(W.STANDIN, START)]
        frames = [frame(0.0, []), frame(1.0, one), frame(2.0, one + [(W.WORLD, START)]),
                  frame(3.0, []), frame(9.0, [])]
        self.assertEqual(W.miscounts(frames, since=1.0, until=3.0),
                         [(1.0, [W.STANDIN, W.WORLD]), (2.0, [])])

    def test_the_first_frame_of_a_kind(self):
        frames = [frame(1.0, [(W.HAND, START)]), frame(2.0, [(W.STANDIN, START)]),
                  frame(3.0, [(W.STANDIN, START)])]
        self.assertEqual(W.first_wall(frames, W.STANDIN), 2.0)
        self.assertIsNone(W.first_wall(frames, W.WORLD))

    def test_a_flying_stand_in_that_does_not_move_is_a_stall(self):
        a, b = W.on_curve(START, VEL, G, 0.1), W.on_curve(START, VEL, G, 0.2)
        moving = [frame(0.1, [(W.STANDIN, a)]), frame(0.2, [(W.STANDIN, b)])]
        stuck = [frame(0.1, [(W.STANDIN, a)]), frame(0.2, [(W.STANDIN, a)])]
        self.assertEqual((W.stalls(moving), W.stalls(stuck)), (0, 1))

    def test_one_that_has_stopped_or_a_world_that_has_not_ticked_is_no_stall(self):
        a = W.on_curve(START, VEL, G, 0.1)
        stopped = [frame(0.1, [(W.STANDIN, a)]), frame(0.2, [(W.STANDIN, a)], flying=False)]
        frozen = [frame(0.1, [(W.STANDIN, a)], world=5.0), frame(0.2, [(W.STANDIN, a)], world=5.0)]
        self.assertEqual((W.stalls(stopped), W.stalls(frozen)), (0, 0))

    def test_places_counts_where_it_was_shown(self):
        frames = [frame(t / 10.0, [(W.STANDIN, W.on_curve(START, VEL, G, t / 10.0))])
                  for t in range(6)]
        self.assertEqual(W.places(frames), 6)


if __name__ == "__main__":
    unittest.main()
