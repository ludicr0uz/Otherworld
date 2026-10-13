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
        # Raised from 400 KB on 11 Oct 2026 (the title level's package took it over),
        # and from 448 KB on 13 Oct 2026: the index stood 129 bytes under it, and
        # the long gun's carry (some 50 symbols) took it over.
        self.assertLess(os.path.getsize(symbols.OUT), 512 * 1024)


if __name__ == "__main__":
    unittest.main()
