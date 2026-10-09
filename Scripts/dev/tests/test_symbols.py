"""symbols.txt is current against the tree, and small enough to grep cheaply."""

import os
import unittest

import _paths  # noqa: F401
import symbols


class SymbolsTest(unittest.TestCase):
    def test_current(self):
        with open(symbols.OUT, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), symbols.symbols(),
                             "stale: python3 Scripts/dev/symbols.py")

    def test_size(self):
        self.assertLess(os.path.getsize(symbols.OUT), 400 * 1024)


if __name__ == "__main__":
    unittest.main()
