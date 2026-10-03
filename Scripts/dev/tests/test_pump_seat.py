"""combat/pump_seat.py: the left hand moved to where its fingers fit a pump."""

import unittest

import _paths  # noqa: F401

from combat import pump_seat

PUMP = ((28.4, -2.1, -2.5), (44.4, 2.1, 2.3))
# A hand under the pump, its fingers up the right side: each point 0.75 off.
FITTED = [(36.0, 0.0, -3.25), (36.0, 2.85, -1.0), (36.0, 2.85, 1.0),
          (38.0, -1.0, -3.25), (38.0, 2.85, 0.0)]
THUMB = [(34.0, -2.9, 0.5)]


def moved(points, by):
    return [tuple(p + d for p, d in zip(pt, by)) for pt in points]


class BoxDistance(unittest.TestCase):
    def test_outside_is_the_gap_and_inside_is_negative(self):
        self.assertAlmostEqual(pump_seat.box_distance(PUMP, (36.0, 4.1, 0.0)), 2.0)
        self.assertAlmostEqual(pump_seat.box_distance(PUMP, (36.0, 0.0, 0.0)), -2.1)
        self.assertAlmostEqual(pump_seat.box_distance(PUMP, (47.4, 6.1, 0.0)), 5.0)


class Seat(unittest.TestCase):
    def test_a_hand_that_fits_is_left_where_it_is(self):
        self.assertAlmostEqual(pump_seat.misfit(PUMP, FITTED), 0.0, places=6)
        self.assertEqual(pump_seat.seat(PUMP, FITTED, THUMB, 5.3), (0.0, 0.0, 0.0))

    def test_a_hand_off_the_pump_is_brought_back_onto_it(self):
        for off in ((0.0, 1.5, -3.0), (2.0, -1.0, 2.5), (0.0, 3.0, 0.0)):
            joints = moved(FITTED, off)
            move = pump_seat.seat(PUMP, joints, moved(THUMB, off), 5.3)
            self.assertLess(pump_seat.misfit(PUMP, joints, move), 0.1, off)
            # Along the pump nothing asks for a move: the hand is not slid.
            self.assertLess(abs(move[0]), 0.05, off)

    def test_the_thumb_stays_under_the_ceiling(self):
        off = (0.0, 0.0, -4.0)
        thumb = [(34.0, -2.9, 4.5)]
        move = pump_seat.seat(PUMP, moved(FITTED, off), thumb, 5.3)
        self.assertLess(thumb[0][2] + move[2], 5.3 - pump_seat.THUMB_CLEAR_CM)

    def test_the_move_is_bounded(self):
        move = pump_seat.seat(PUMP, moved(FITTED, (0.0, 40.0, 0.0)), [], 5.3)
        self.assertLessEqual(sum(m * m for m in move) ** 0.5,
                             pump_seat.SEAT_MAX_MOVE_CM + 1e-6)


if __name__ == "__main__":
    unittest.main()
