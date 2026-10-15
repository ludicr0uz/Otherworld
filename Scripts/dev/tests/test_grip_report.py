import math
import unittest

import _paths  # noqa: F401

from probes import grip_report as G


class FingerTest(unittest.TestCase):
    def test_axis_inside_the_mesh_is_skin_plus_depth(self):
        near, pen, gap = G.finger([-0.5, 2.0, 3.0])
        self.assertAlmostEqual(near, -0.5)
        self.assertAlmostEqual(pen, G.SKIN_CM + 0.5)
        self.assertEqual(gap, 0.0)

    def test_axis_a_skin_off_touches(self):
        self.assertEqual(G.finger([G.SKIN_CM, 4.0])[1:], (0.0, 0.0))
        self.assertEqual(G.finger_cell([G.SKIN_CM + 0.02]), "on")

    def test_gap_and_cells(self):
        _near, pen, gap = G.finger([2.75, 5.0])
        self.assertEqual(pen, 0.0)
        self.assertAlmostEqual(gap, 2.0)
        self.assertEqual(G.finger_cell([2.75]), "off 2.00")
        self.assertEqual(G.finger_cell([0.25]), "in 0.50")


class ReportTest(unittest.TestCase):
    def test_offset(self):
        self.assertAlmostEqual(G.offset((0, 0, 0), (3, 4, 0)), 5.0)

    def test_angle(self):
        half = math.sqrt(0.5)
        self.assertAlmostEqual(G.angle((0, 0, 0, 1), (0, 0, half, half)), 90.0)
        # q and -q are the same turn.
        self.assertAlmostEqual(G.angle((0, 0, half, half), (0, 0, -half, -half)), 0.0)

    def test_table(self):
        lines = G.table(["a", "b"], [["x", 1.234]])
        self.assertEqual(lines, ["| a | b |", "|---|---|", "| x | 1.23 |"])

    def test_worst(self):
        pen, gap = G.worst({"index": [-1.0], "ring": [3.0], "little": [0.75]})
        self.assertEqual(pen[0], "index")
        self.assertAlmostEqual(pen[1], 1.75)
        self.assertEqual(gap[0], "ring")
        self.assertAlmostEqual(gap[1], 2.25)
        self.assertEqual(G.worst({"index": [0.75]}), (None, None))


if __name__ == "__main__":
    unittest.main()
