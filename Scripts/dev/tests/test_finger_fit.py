"""combat/finger_fit.py: how far a finger's joints bend to lie on a gun, and
the swing that lays a thumb against it."""

import math
import unittest

import _paths  # noqa: F401

from combat import finger_fit
from combat.finger_fit import SKIN_CM

# A handguard along X: 4 cm wide, its underside at z 0.
GUARD = ((0.0, -2.0, 0.0), (30.0, 2.0, 4.0))
# A finger under it, pointing across it (+Y), slightly curled upwards: its
# knuckle under the left edge, 2 cm bones.
KNUCKLE = (10.0, -3.5, -1.5)


def finger(curl=(10.0, 10.0), start=0.0, at=KNUCKLE, bones=(3.0, 2.0, 2.0)):
    """A finger in the YZ plane from ``at``: its first bone ``start`` degrees
    up from +Y, each joint after it bent on by ``curl``."""
    points, angle = [at], start
    for length, more in zip(bones, (0.0,) + tuple(curl)):
        angle += more
        last = points[-1]
        points.append((last[0], last[1] + length * math.cos(math.radians(angle)),
                       last[2] + length * math.sin(math.radians(angle))))
    return points


class Geometry(unittest.TestCase):
    def test_turned_is_right_handed(self):
        for got, want in zip(finger_fit.turned((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), 90.0),
                             (0.0, 0.0, 1.0)):
            self.assertAlmostEqual(got, want)

    def test_the_hinge_is_the_normal_of_the_curl_and_a_positive_turn_curls_on(self):
        points = finger()
        axis = finger_fit.hinge(points)
        for got, want in zip(axis, (1.0, 0.0, 0.0)):
            self.assertAlmostEqual(got, want)
        for got, want in zip(finger_fit.bend(points, axis), (10.0, 10.0)):
            self.assertAlmostEqual(got, want)
        more = finger_fit.posed(points, axis, (0.0, 15.0, 5.0))
        for got, want in zip(finger_fit.bend(more, axis), (25.0, 15.0)):
            self.assertAlmostEqual(got, want)

    def test_a_straight_finger_has_no_hinge(self):
        self.assertIsNone(finger_fit.hinge(finger(curl=(0.0, 0.0))))

    def test_posed_keeps_every_bone_its_length_and_the_knuckle_its_place(self):
        points = finger()
        bent = finger_fit.posed(points, finger_fit.hinge(points), (12.0, -7.0, 30.0))
        self.assertEqual(bent[0], points[0])
        for a, b, c, d in zip(points, points[1:], bent, bent[1:]):
            self.assertAlmostEqual(math.dist(a, b), math.dist(c, d))

    def test_posed_by_nothing_is_the_finger(self):
        points = finger()
        for a, b in zip(points, finger_fit.posed(points, finger_fit.hinge(points),
                                                 (0.0, 0.0, 0.0))):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y)

    def test_the_limits_never_bend_a_joint_back_past_straight(self):
        points = finger(curl=(5.0, 95.0))
        ranges = finger_fit.limits(points, finger_fit.hinge(points))
        self.assertEqual(ranges[0], (-finger_fit.OPEN_DEG[0], finger_fit.CLOSE_DEG[0]))
        self.assertAlmostEqual(ranges[1][0], -5.0)
        self.assertAlmostEqual(ranges[2][1], finger_fit.BEND_MAX_DEG - 95.0)


class Close(unittest.TestCase):
    def test_a_finger_hanging_under_the_part_is_laid_on_it(self):
        points = finger()
        self.assertLess(finger_fit.on([GUARD], points), finger_fit.ON_POINTS)
        angles, met = finger_fit.close(points, [GUARD])
        self.assertTrue(met)
        bent = finger_fit.posed(points, finger_fit.hinge(points), angles)
        self.assertGreaterEqual(finger_fit.on([GUARD], bent), finger_fit.ON_POINTS)
        self.assertLess(finger_fit.misfit([GUARD], bent), finger_fit.misfit([GUARD], points))
        off = [finger_fit.nearest([GUARD], [p]) for p in finger_fit.riding(bent)]
        self.assertGreater(min(off), SKIN_CM - 0.3)
        self.assertLess(max(off), SKIN_CM + 0.75)

    def test_a_finger_inside_the_part_is_lifted_out_of_it(self):
        points = finger(start=15.0)
        self.assertLess(finger_fit.nearest([GUARD], finger_fit.riding(points)), 0.0)
        angles, met = finger_fit.close(points, [GUARD])
        self.assertTrue(met)
        bent = finger_fit.posed(points, finger_fit.hinge(points), angles)
        self.assertGreater(finger_fit.nearest([GUARD], finger_fit.riding(bent)), 0.3)

    def test_a_finger_that_fits_is_left_alone(self):
        flat = [(10.0, -1.5, -SKIN_CM), (10.0, 1.5, -SKIN_CM)]
        points = flat + finger(at=flat[1], bones=(1.2, 1.2), curl=(89.0,), start=1.0)[1:]
        angles, _met = finger_fit.close(points, [GUARD])
        after = finger_fit.posed(points, finger_fit.hinge(points), angles)
        self.assertLessEqual(finger_fit.misfit([GUARD], after),
                             finger_fit.misfit([GUARD], points) + 1e-9)
        self.assertLess(max(abs(a) for a in angles), 15.0)

    def test_a_finger_past_the_end_of_the_part_keeps_the_clips_pose(self):
        points = finger(at=(40.0, -3.5, -1.5))
        self.assertEqual(finger_fit.close(points, [GUARD]), ((0.0, 0.0, 0.0), False))

    def test_no_joint_leaves_its_limits(self):
        for start in (-30.0, 0.0, 15.0):
            points = finger(start=start)
            angles, _met = finger_fit.close(points, [GUARD])
            for angle, (lo, hi) in zip(angles, finger_fit.limits(points,
                                                                 finger_fit.hinge(points))):
                self.assertTrue(lo - 1e-9 <= angle <= hi + 1e-9, (start, angles))

    def test_a_straight_finger_or_no_gun_is_left_alone(self):
        still = ((0.0, 0.0, 0.0), False)
        self.assertEqual(finger_fit.close(finger(curl=(0.0, 0.0)), [GUARD]), still)
        self.assertEqual(finger_fit.close(finger(), []), still)


class Swing(unittest.TestCase):
    # A thumb beside the guard's left face, standing 2 cm off it.
    THUMB = [(12.0, -4.5, 1.0), (12.0, -4.2, 2.0), (12.5, -4.0, 2.6), (13.0, -3.9, 3.0)]

    def test_the_thumb_is_swung_onto_the_part_and_stops_a_skin_off_it(self):
        axis, deg = finger_fit.swing(self.THUMB, [GUARD], 10.0)
        self.assertGreater(deg, 0.0)
        moved = finger_fit.swung(self.THUMB, axis, deg)[1:]
        near = finger_fit.nearest([GUARD], moved)
        self.assertGreaterEqual(near, SKIN_CM - 1e-6)
        self.assertLess(near, SKIN_CM + 0.3)

    def test_it_stops_under_the_ceiling(self):
        axis, deg = finger_fit.swing(self.THUMB, [GUARD], 3.5)
        top = max(p[2] for p in finger_fit.swung(self.THUMB, axis, deg)[1:])
        self.assertLessEqual(top, 3.5 - finger_fit.THUMB_CLEAR_CM + 1e-6)

    def test_a_thumb_that_reaches_nothing_stays(self):
        far = [(p[0], p[1] - 30.0, p[2]) for p in self.THUMB]
        self.assertEqual(finger_fit.swing(far, [GUARD], 10.0)[1], 0.0)
        self.assertEqual(finger_fit.swing(self.THUMB, [], 10.0)[1], 0.0)


if __name__ == "__main__":
    unittest.main()
