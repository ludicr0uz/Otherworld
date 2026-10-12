"""net/leftover_consts.py: the cleanup rule's table is one a server can keep."""

import unittest

import _paths  # noqa: F401

from net import leftover_consts as LC  # noqa: E402


class LeftoverRows(unittest.TestCase):
    def test_one_row_a_kind(self):
        kinds = [row.kind for row in LC.ROWS]
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertEqual(set(LC.ROWS), {LC.ITEM, LC.CORPSE, LC.CAMPFIRE})

    def test_every_kind_is_capped(self):
        # A cap of 0 is "no cap": the world would fill up with that kind.
        for row in LC.ROWS:
            self.assertIsInstance(row.cap, int, row.kind)
            self.assertGreater(row.cap, 0, row.kind)

    def test_lifetimes(self):
        # An item has no lifespan of its own, so the rule must give it one; a
        # body and a fire have theirs (SetLifeSpan), and 0 says so.
        self.assertGreater(LC.ITEM.lifetime_s, 0.0)
        self.assertEqual(LC.CORPSE.lifetime_s, 0.0)
        self.assertEqual(LC.CAMPFIRE.lifetime_s, 0.0)
        for row in LC.ROWS:
            self.assertIsInstance(row.lifetime_s, float, row.kind)


if __name__ == "__main__":
    unittest.main()
