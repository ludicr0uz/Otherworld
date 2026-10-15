"""combat/drawn_thumb.py: a thumb standing up behind a pistol's slide is laid
forward along the frame's side, under the sights, out of the gun."""

import unittest

import _paths  # noqa: F401

from combat import drawn_grip as D
from combat import drawn_thumb as T
from combat import finger_fit
from combat.finger_fit import SKIN_CM

BONES = D.chain("thumb", "r")
# A pistol in the hand's frame (+X down the barrel, +Z up, its left side -Y):
# the grip, the frame above it and the slide on top (the 1911's heights).
GUN = finger_fit.as_solid([((-4.0, -1.0, -6.0), (1.0, 1.0, 0.0)),
                           ((-2.5, -1.2, 0.0), (6.0, 1.2, 4.5)),
                           ((-2.0, -0.8, 5.5), (15.0, 0.8, 7.5))])
SLIDE_TOP = 7.5
UP = (0.0, -0.7071068, 0.0, 0.7071068)  # +X turned to +Z
CEILING = 6.0
# The rest: beside the frame's left side, a skin off it.
REST = ((0.0, -1.2 - SKIN_CM, 4.0), (3.0, -1.2 - SKIN_CM, 4.0))


def height(p):
    return p[2]


def upright():
    """The retarget's thumb: behind the grip, on its right, standing up (its
    bones along their +X, as a MetaHuman's, the first turned to +Z)."""
    return {BONES[0]: ((-6.0, 2.0, -0.5), UP),
            BONES[1]: ((4.4, 0.0, 0.0), D.IDENTITY[1]),
            BONES[2]: ((2.7, 0.0, 0.0), D.IDENTITY[1])}


def thumb_points(locals_):
    return D.points(D.placed(locals_, BONES), D.THUMB_TIP_CM)


class LayThumb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moved, cls.params = T.lay(upright(), BONES, GUN, REST, height, CEILING)
        cls.locals = {**upright(), **cls.moved}
        cls.pts = thumb_points(cls.locals)

    def test_the_upright_thumb_stands_over_the_slide(self):
        self.assertGreater(T.top(upright(), BONES, height), SLIDE_TOP)

    def test_its_tip_is_laid_on_the_rest(self):
        tip = self.pts[-1]
        near = finger_fit._len(finger_fit._sub(tip, finger_fit.aimed(REST, tip)))
        self.assertLess(near, 0.5)
        self.assertLess(tip[1], -1.2)

    def test_no_skin_rises_past_the_ceiling(self):
        self.assertLessEqual(T.top(self.locals, BONES, height) + SKIN_CM, CEILING + 0.05)

    def test_it_is_not_pressed_into_the_gun(self):
        deepest = max(SKIN_CM - GUN.distance(p) for p in finger_fit.riding(self.pts))
        self.assertLessEqual(deepest, 0.1)

    def test_only_the_thumbs_turns_change(self):
        self.assertEqual(sorted(self.moved), sorted(BONES))
        for bone in BONES:
            self.assertEqual(self.moved[bone][0], upright()[bone][0])

    def test_the_root_is_turned_within_its_search(self):
        yaw, pitch, roll, b1, b2 = self.params
        self.assertLessEqual(max(abs(yaw), abs(pitch)), T.SWING_DEG)
        self.assertLessEqual(abs(roll), T.ROLL_DEG)
        for b in (b1, b2):
            self.assertTrue(T.BEND_DEG[0] <= b <= T.BEND_DEG[1])


class Between(unittest.TestCase):
    def test_the_least_turn_takes_one_direction_to_the_other(self):
        q = T._between((0.0, 0.0, 2.0), (3.0, 0.0, 0.0))
        got = D._turn(q, (0.0, 0.0, 1.0))
        for g, w in zip(got, (1.0, 0.0, 0.0)):
            self.assertAlmostEqual(g, w, places=6)


if __name__ == "__main__":
    unittest.main()
