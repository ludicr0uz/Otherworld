"""combat/capsule_fit.py: capsules fitted to synthetic clouds of points."""

import math
import unittest

import _paths  # noqa: F401

from combat import capsule_fit


def tube(start, end, r0, r1, rings=40, around=16):
    """Points on a round tube from ``start`` to ``end`` whose radius runs
    r0 to r1; the tube lies along x, y or z only in the tests that say so."""
    axis = tuple(b - a for a, b in zip(start, end))
    n = math.sqrt(sum(c * c for c in axis))
    w = tuple(c / n for c in axis)
    u = capsule_fit._unit(capsule_fit._cross(w, (0.3, 0.5, 0.8)))
    v = capsule_fit._cross(w, u)
    out = []
    for i in range(rings):
        t = i / (rings - 1.0)
        r = r0 + (r1 - r0) * t
        for j in range(around):
            a = 2.0 * math.pi * j / around
            out.append(tuple(s + ax * t + (u[k] * math.cos(a) + v[k] * math.sin(a)) * r
                             for k, (s, ax) in enumerate(zip(start, axis))))
    return out


class PrincipalAxes(unittest.TestCase):
    def test_the_long_axis_is_the_tubes_whichever_way_it_lies(self):
        for end in ((40, 0, 0), (0, 0, 40), (20, 25, -18)):
            long_axis, middle, short = capsule_fit.principal_axes(
                tube((0, 0, 0), end, 5, 5))
            want = capsule_fit._unit(end)
            self.assertAlmostEqual(abs(capsule_fit._dot(long_axis, want)), 1.0, places=3)
            self.assertAlmostEqual(capsule_fit._dot(long_axis, middle), 0.0, places=6)
            for got, cross in zip(short, capsule_fit._cross(long_axis, middle)):
                self.assertAlmostEqual(got, cross)

    def test_the_same_cloud_gives_the_same_axes(self):
        cloud = tube((1, 2, 3), (-20, 25, 18), 6, 3)
        for one, other in zip(capsule_fit.principal_axes(cloud),
                              capsule_fit.principal_axes(list(reversed(cloud)))):
            for a, b in zip(one, other):
                self.assertAlmostEqual(a, b, places=9)


class FitCapsules(unittest.TestCase):
    def test_a_straight_tube_is_one_capsule_its_size(self):
        _axes, capsules = capsule_fit.fit_capsules(tube((0, 0, 0), (0, 0, 40), 5, 5))
        self.assertEqual(len(capsules), 1)
        self.assertAlmostEqual(capsules[0]["radius"], 5.0, delta=0.3)
        # The rounded ends reach a quarter of the radius past the ends.
        whole = capsules[0]["length"] + 2 * capsules[0]["radius"]
        self.assertAlmostEqual(whole, 40.0 + 2 * 0.25 * 5.0, delta=2.5)
        self.assertAlmostEqual(capsules[0]["center"][2], 20.0, delta=0.5)

    def test_a_tapering_limb_is_cut_and_each_piece_is_narrower_than_the_last(self):
        _axes, capsules = capsule_fit.fit_capsules(tube((0, 0, 0), (0, 0, 45), 9, 4))
        self.assertGreater(len(capsules), 1)
        radii = [c["radius"] for c in sorted(capsules, key=lambda c: c["center"][2])]
        self.assertEqual(radii, sorted(radii, reverse=True))
        self.assertLess(radii[-1], 6.0)

    def test_a_ball_is_not_cut(self):
        ball = [(8 * math.sin(a) * math.cos(b), 8 * math.sin(a) * math.sin(b),
                 9 * math.cos(a))
                for a in (math.pi * i / 20 for i in range(21))
                for b in (2 * math.pi * j / 20 for j in range(20))]
        self.assertEqual(len(capsule_fit.fit_capsules(ball)[1]), 1)


if __name__ == "__main__":
    unittest.main()
