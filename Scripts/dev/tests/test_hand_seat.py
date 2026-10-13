"""combat/hand_seat.py: the left hand moved to where its fingers fit the part
of the gun it holds."""

import unittest

import _paths  # noqa: F401

from combat import hand_seat

PUMP = ((28.4, -2.1, -2.5), (44.4, 2.1, 2.3))
# A hand under the pump, its fingers up the right side: each point 0.75 off.
FITTED = [(36.0, 0.0, -3.25), (36.0, 2.85, -1.0), (36.0, 2.85, 1.0),
          (38.0, -1.0, -3.25), (38.0, 2.85, 0.0)]
THUMB = [(34.0, -2.9, 0.5)]


def moved(points, by):
    return [tuple(p + d for p, d in zip(pt, by)) for pt in points]


class BoxDistance(unittest.TestCase):
    def test_outside_is_the_gap_and_inside_is_negative(self):
        self.assertAlmostEqual(hand_seat.box_distance(PUMP, (36.0, 4.1, 0.0)), 2.0)
        self.assertAlmostEqual(hand_seat.box_distance(PUMP, (36.0, 0.0, 0.0)), -2.1)
        self.assertAlmostEqual(hand_seat.box_distance(PUMP, (47.4, 6.1, 0.0)), 5.0)


class Seat(unittest.TestCase):
    def test_a_hand_that_fits_is_left_where_it_is(self):
        self.assertAlmostEqual(hand_seat.misfit(PUMP, FITTED), 0.0, places=6)
        self.assertEqual(hand_seat.seat(PUMP, FITTED, THUMB, 5.3), (0.0, 0.0, 0.0))

    def test_a_hand_off_the_pump_is_brought_back_onto_it(self):
        for off in ((0.0, 1.5, -3.0), (2.0, -1.0, 2.5), (0.0, 3.0, 0.0)):
            joints = moved(FITTED, off)
            move = hand_seat.seat(PUMP, joints, moved(THUMB, off), 5.3)
            self.assertLess(hand_seat.misfit(PUMP, joints, move), 0.1, off)
            # Along the pump nothing asks for a move: the hand is not slid.
            self.assertLess(abs(move[0]), 0.05, off)

    def test_the_thumb_stays_under_the_ceiling(self):
        off = (0.0, 0.0, -4.0)
        thumb = [(34.0, -2.9, 4.5)]
        move = hand_seat.seat(PUMP, moved(FITTED, off), thumb, 5.3)
        self.assertLess(thumb[0][2] + move[2], 5.3 - hand_seat.THUMB_CLEAR_CM)

    def test_the_move_is_bounded(self):
        move = hand_seat.seat(PUMP, moved(FITTED, (0.0, 40.0, 0.0)), [], 5.3)
        self.assertLessEqual(sum(m * m for m in move) ** 0.5,
                             hand_seat.SEAT_MAX_MOVE_CM + 1e-6)

    def test_the_hand_keeps_out_of_the_part_beside_the_one_held(self):
        # A magazine under the pump's back end, where the hand starts.
        magazine = ((30.0, -2.1, -14.0), (37.0, 2.1, -2.5))
        joints = moved(FITTED, (0.0, 0.0, -1.0))
        self.assertGreater(hand_seat.crowding([magazine], joints), 1.0)
        move = hand_seat.seat(PUMP, joints, THUMB, 5.3, obstacles=[magazine])
        self.assertLess(hand_seat.crowding([magazine], joints, move), 0.1)
        self.assertGreater(move[0], 1.0)
        self.assertLess(hand_seat.misfit(PUMP, joints, move), 0.1)

    def test_parts_that_are_clear_change_nothing(self):
        far = ((0.0, -2.0, -2.0), (10.0, 2.0, 6.0))
        joints = moved(FITTED, (0.0, 1.5, -3.0))
        self.assertEqual(hand_seat.seat(PUMP, joints, THUMB, 5.3, obstacles=[far]),
                         hand_seat.seat(PUMP, joints, THUMB, 5.3))

    def test_the_wrist_stays_within_the_arm(self):
        # A hand 8 cm behind the pump's back end wants to go forward ...
        behind = moved(FITTED, (-16.0, 0.0, 0.0))
        free = hand_seat.seat(PUMP, behind, [], 5.3)
        self.assertGreater(free[0], 5.0)
        # ... and an arm already at full stretch cannot follow.
        shoulder, wrist = (-30.0, 0.0, 0.0), (10.0, 0.0, 0.0)
        held = hand_seat.seat(PUMP, behind, [], 5.3, reach=(shoulder, wrist, 42.0))
        self.assertLessEqual(wrist[0] + held[0] - shoulder[0], 42.0 + 1e-6)


class Reach(unittest.TestCase):
    REACH = ((0.0, 0.0, 0.0), (40.0, 0.0, 0.0), 45.0)

    def test_a_move_the_arm_makes_is_kept(self):
        self.assertEqual(hand_seat.reached((3.0, 2.0, -1.0), self.REACH), (3.0, 2.0, -1.0))
        self.assertEqual(hand_seat.reached((30.0, 0.0, 0.0), None), (30.0, 0.0, 0.0))

    def test_a_move_past_the_arm_is_cut_short_towards_the_shoulder(self):
        made = hand_seat.reached((10.0, 0.0, 0.0), self.REACH)
        self.assertAlmostEqual(made[0], 5.0)
        made = hand_seat.reached((20.0, 30.0, 0.0), self.REACH)
        wrist = [w + m for w, m in zip(self.REACH[1], made)]
        self.assertAlmostEqual(sum(c * c for c in wrist) ** 0.5, 45.0)
        # Along the line from the shoulder to where it was asked to be.
        self.assertAlmostEqual(wrist[1] / wrist[0], 30.0 / 60.0)

    def test_the_seat_is_a_move_the_arm_makes(self):
        behind = moved(FITTED, (-16.0, 0.0, 0.0))
        shoulder, wrist = (-30.0, 0.0, 0.0), (10.0, 0.0, 0.0)
        held = hand_seat.seat(PUMP, behind, [], 5.3, reach=(shoulder, wrist, 42.0))
        self.assertEqual(held, hand_seat.reached(held, (shoulder, wrist, 42.0)))


class Sink(unittest.TestCase):
    def test_a_joint_deep_in_the_part_outweighs_one_as_far_off_it(self):
        top = PUMP[1][2]
        mid = ((PUMP[0][0] + PUMP[1][0]) / 2.0, 0.0)
        inside, outside = (mid + (top - 1.5,)), (mid + (top + 1.5 + 2 * hand_seat.SEAT_OFF_CM,))
        self.assertGreater(hand_seat.misfit(PUMP, [inside]), hand_seat.misfit(PUMP, [outside]))
        # Within SEAT_SINK_CM the two count alike.
        inside, outside = (mid + (top - 0.25,)), (mid + (top + 0.25 + 2 * hand_seat.SEAT_OFF_CM,))
        self.assertAlmostEqual(hand_seat.misfit(PUMP, [inside]), hand_seat.misfit(PUMP, [outside]))


class Boxes(unittest.TestCase):
    def test_bounding_union_grown_overlaps(self):
        box = hand_seat.bounding([(0.0, 1.0, 2.0), (3.0, -1.0, 5.0)])
        self.assertEqual(box, ((0.0, -1.0, 2.0), (3.0, 1.0, 5.0)))
        self.assertEqual(hand_seat.union(box, ((-1.0, 0.0, 0.0), (1.0, 4.0, 3.0))),
                         ((-1.0, -1.0, 0.0), (3.0, 4.0, 5.0)))
        self.assertEqual(hand_seat.grown(box, 0.5), ((-0.5, -1.5, 1.5), (3.5, 1.5, 5.5)))
        self.assertTrue(hand_seat.overlaps(box, ((2.0, 0.0, 4.0), (9.0, 9.0, 9.0))))
        # Touching faces share no volume.
        self.assertFalse(hand_seat.overlaps(box, ((3.0, -1.0, 2.0), (9.0, 1.0, 5.0))))


if __name__ == "__main__":
    unittest.main()
