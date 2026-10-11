"""combat/grip_nudges.py: the grip nudge table's parse and write-back, and
the tracked table itself. Pure, so it is held here without an editor; that
the game's C++ reads and writes the same file is probes/probe_grip_nudge.py.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import os
import tempfile
import unittest

import _paths  # noqa: F401

from combat import grip_nudges as G

HEADER = "item,x,y,z,pitch,yaw,roll\n"


class Table(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "sub", "grip_nudges.csv")

    def _file(self, text):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            f.write(text)

    def _text(self):
        with open(self.path) as f:
            return f.read()

    def test_no_file_is_no_rows(self):
        self.assertEqual(G.read_table(self.path), {})

    def test_parse(self):
        self._file(HEADER + "BP_Knife,1.5,-2,0.25,10,-20,30\nBP_Axe,0,0,0,0,0,0\n")
        table = G.read_table(self.path)
        self.assertEqual(list(table), ["BP_Knife", "BP_Axe"])
        self.assertEqual(table["BP_Knife"], dict(x=1.5, y=-2.0, z=0.25, pitch=10.0,
                                                 yaw=-20.0, roll=30.0))
        self.assertTrue(G.is_zero(table["BP_Axe"]))
        self.assertFalse(G.is_zero(table["BP_Knife"]))

    def test_an_empty_or_missing_cell_is_zero_and_a_nameless_row_is_skipped(self):
        self._file(HEADER + "BP_Knife,,2\n,1,1,1,1,1,1\n BP_Axe ,1,,,,,5\n")
        table = G.read_table(self.path)
        self.assertEqual(table, {"BP_Knife": dict(G.ZERO, y=2.0),
                                 "BP_Axe": dict(G.ZERO, x=1.0, roll=5.0)})

    def test_a_row_named_twice_is_its_last(self):
        self._file(HEADER + "BP_Knife,1,0,0,0,0,0\nBP_Knife,2,0,0,0,0,0\n")
        self.assertEqual(G.read_table(self.path)["BP_Knife"]["x"], 2.0)

    def test_write_back_round_trips(self):
        rows = [("BP_Knife", dict(x=1.5, y=-2.0, z=0.25, pitch=10.0, yaw=-20.0, roll=30.0)),
                ("BP_Axe", dict(G.ZERO))]
        G.write_table(rows, self.path)
        self.assertEqual(self._text(),
                         HEADER + "BP_Knife,1.5,-2,0.25,10,-20,30\nBP_Axe,0,0,0,0,0,0\n")
        self.assertEqual(list(G.read_table(self.path).items()), rows)
        # Written again from what was read: the same bytes.
        text = self._text()
        G.write_table(list(G.read_table(self.path).items()), self.path)
        self.assertEqual(self._text(), text)

    def test_a_missing_column_is_written_zero(self):
        G.write_table([("BP_Knife", {"z": 1.0})], self.path)
        self.assertEqual(self._text(), HEADER + "BP_Knife,0,0,1,0,0,0\n")

    def test_numbers_are_written_without_float_noise(self):
        self.assertEqual(G.format_value(0.1 + 0.1 + 0.1), "0.3")
        self.assertEqual(G.format_value(-0.0), "0")
        self.assertEqual(G.format_value(-1e-9), "0")
        self.assertEqual(G.format_value(12.0), "12")
        self.assertEqual(G.format_value(-0.125), "-0.125")
        self.assertEqual(G.format_value(100.0), "100")

    def test_row_of_is_the_blueprints_name(self):
        self.assertEqual(G.row_of("/Game/Weapons/BP_Knife"), "BP_Knife")
        self.assertEqual(G.row_of("/Game/Weapons/BP_Knife.BP_Knife"), "BP_Knife")


class Tracked(unittest.TestCase):
    """Content/Tuning/grip_nudges.csv as committed."""

    def test_it_parses_and_writes_back_to_the_same_bytes(self):
        with open(G.CSV_PATH) as f:
            text = f.read()
        table = G.read_table()
        self.assertTrue(table)
        self.assertTrue(all(name.startswith("BP_") for name in table))
        out = os.path.join(tempfile.mkdtemp(), "out.csv")
        G.write_table(list(table.items()), out)
        with open(out) as f:
            self.assertEqual(f.read(), text)

    def test_the_stats_are_the_columns_and_signed(self):
        self.assertEqual(G.GRIP_COLUMNS, ("x", "y", "z", "pitch", "yaw", "roll"))
        self.assertTrue(all(step > 0 for _c, _l, step in G.GRIP_STATS))
        self.assertLess(G.GRIP_MIN, 0)

    def test_the_packaging_stages_it_loose(self):
        ini = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(G.CSV_PATH))),
                           "Config", "DefaultGame.ini")
        with open(ini) as f:
            self.assertIn('+DirectoriesToAlwaysStageAsNonUFS=(Path="Tuning")', f.read())


if __name__ == "__main__":
    unittest.main()
