"""combat/drawn_grip.py: the drawn MetaHuman's finger fit in the hand's own
frame (the transforms, the gun seen from several placements of a hand, a
finger bent, cupped at its metacarpal, a thumb swung), and the capture's
trim."""

import unittest

import _paths  # noqa: F401

from combat import drawn_grip as D
from combat import finger_fit
from combat.finger_fit import SKIN_CM

TURN_Z = (0.0, 0.0, 0.7071068, 0.7071068)   # 90 degrees about +Z
# A straight finger along +X from the hand's origin: the metacarpal 6 cm,
# then 4, 2.5 and 2.5 (each bone's local along its parent's +X); the curl
# axis (D.CURL_AXIS, -Z) bends it towards -Y.
BONES = D.chain("middle", "r")


def straight(at=(0.0, 0.0, 0.0)):
    lengths = (0.0, 6.0, 4.0, 2.5)
    return {b: ((at[0], at[1], at[2]) if i == 0 else (n, 0.0, 0.0), D.IDENTITY[1])
            for i, (b, n) in enumerate(zip(BONES, lengths))}


def riding(locals_):
    return finger_fit.riding(D.points(D.placed(locals_, BONES), D.FINGER_TIP_CM))


def deepest(solid, pts):
    return max(SKIN_CM - solid.distance(p) for p in pts)


class Transforms(unittest.TestCase):
    def test_compose_and_inverse_undo_each_other(self):
        a = ((1.0, 2.0, 3.0), TURN_Z)
        b = ((4.0, -1.0, 0.5), (0.0, 0.3826834, 0.0, 0.9238795))
        back = D.compose(D.inverse(a), D.compose(a, b))
        for got, want in zip(back[0] + back[1], b[0] + b[1]):
            self.assertAlmostEqual(got, want, places=5)

    def test_apply_turns_then_moves(self):
        got = D.apply(((1.0, 0.0, 0.0), TURN_Z), (1.0, 0.0, 0.0))
        for g, w in zip(got, (1.0, 1.0, 0.0)):
            self.assertAlmostEqual(g, w, places=5)

    def test_placed_runs_down_the_chain(self):
        xfs = D.placed(straight(), BONES)
        self.assertEqual([round(xf[0][0], 6) for xf in xfs], [0.0, 6.0, 10.0, 12.5])

    def test_the_points_are_the_last_three_joints_and_a_tip_along_the_last_bone(self):
        pts = D.points(D.placed(straight(), BONES), D.FINGER_TIP_CM)
        self.assertEqual([round(p[0], 6) for p in pts], [6.0, 10.0, 12.5, 15.0])


class Seen(unittest.TestCase):
    def test_the_nearest_placement_is_what_counts(self):
        box = [((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0))]
        seen = D.Seen(box, [((0.0, 0.0, 0.0), D.IDENTITY[1]),
                            ((5.0, 0.0, 0.0), D.IDENTITY[1])])
        # The point (-5, 0, 0) of the hand is (0, 0, 0) of the gun from the
        # second placement: inside.
        self.assertLess(seen.distance((-5.0, 0.0, 0.0)), 0.0)
        self.assertAlmostEqual(seen.distance((2.0, 0.0, 0.0)), 1.0)


class FitFinger(unittest.TestCase):
    def test_a_finger_over_a_part_is_curled_onto_it_and_not_into_it(self):
        # A grip under the finger's middle bones, 2.5 cm down.
        solid = finger_fit.as_solid([((7.0, -8.0, -3.0), (16.0, -2.5, 3.0))])
        before = min(solid.distance(p) for p in riding(straight())) - SKIN_CM
        moved, said = D.fit_finger(straight(), BONES, solid)
        after = riding({**straight(), **moved})
        self.assertGreater(before, 0.5)
        self.assertNotIn(BONES[0], moved)
        self.assertLessEqual(deepest(solid, after), 0.3)
        self.assertLess(min(solid.distance(p) for p in after) - SKIN_CM, 0.3)
        self.assertEqual(said[-1], 0.0)

    def test_a_knuckle_on_the_gun_is_lifted_by_cupping_the_metacarpal(self):
        # The knuckle (6, 0, 0) is 0.2 cm off a face below it: pressed in,
        # and no bend past it can lift it.
        solid = finger_fit.as_solid([((3.0, -6.0, -3.0), (20.0, -0.2, 3.0))])
        knuckle = (6.0, 0.0, 0.0)
        self.assertGreater(SKIN_CM - solid.distance(knuckle), 0.5)
        moved, said = D.fit_finger(straight(), BONES, solid)
        self.assertIn(BONES[0], moved)
        self.assertNotEqual(said[-1], 0.0)
        self.assertLessEqual(abs(said[-1]), D.CUP_DEG)
        locals_ = {**straight(), **moved}
        pts = D.points(D.placed(locals_, BONES), D.FINGER_TIP_CM)
        self.assertLessEqual(deepest(solid, [pts[0]] + finger_fit.riding(pts)), 0.1)

    def test_a_finger_clear_of_everything_is_left_alone(self):
        solid = finger_fit.as_solid([((50.0, 50.0, 50.0), (60.0, 60.0, 60.0))])
        moved, said = D.fit_finger(straight(), BONES, solid)
        self.assertEqual(moved, {})
        self.assertEqual(said[-2:], (0.0, 0.0))


class Names(unittest.TestCase):
    def test_the_roots_are_each_fingers_first_bone(self):
        self.assertEqual(D.roots("l"), ["thumb_01_l", "index_metacarpal_l",
                                        "middle_metacarpal_l", "ring_metacarpal_l",
                                        "pinky_metacarpal_l"])

    def test_finger_bones_keeps_one_sides_fingers_and_their_helpers(self):
        names = ["hand_r", "index_01_r", "index_01_l", "pinky_metacarpal_r",
                 "thumb_03_r", "lowerarm_twist_01_r", "middle_02_r"]
        self.assertEqual(D.finger_bones(names, "r"),
                         ["index_01_r", "middle_02_r", "pinky_metacarpal_r", "thumb_03_r"])


class Trim(unittest.TestCase):
    def test_trim_keeps_the_frames_states_and_the_named_bones(self):
        xf = [[1.23456789, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        state = {"hand_r": xf, "hand_l": xf, "local": {"a_r": xf, "b_l": xf, "c_l": xf}}
        capture = {"BP_Gun": {"raised": state, "ads": state}}
        frames = {"hold": (("raised", "gone"), "raised"), "sights": (("ads",), "ads")}
        got = D.trim(capture, frames, {"r": ["a_r"], "l": ["b_l"]})["BP_Gun"]
        self.assertEqual(got["hand_r"][0][0], 1.2346)
        self.assertEqual(list(got["right"]), ["a_r"])
        self.assertEqual(len(got["frames"]["hold"]["hands"]), 1)
        self.assertEqual(list(got["frames"]["sights"]["left"]), ["b_l"])


if __name__ == "__main__":
    unittest.main()
