"""The packaged Mac app's Info.plist template keeps the game clear of the notch.

Full screen on a Mac with a notch, the engine draws a viewport the size of the
whole screen into a window macOS has made 39 px shorter: the bottom of the HUD
is cut off. NSPrefersDisplaySafeAreaCompatibilityMode makes macOS scale the
whole window in under the notch instead (root CLAUDE.md, Config).
"""

import os
import plistlib
import unittest

import _paths

TEMPLATE = os.path.join(os.path.dirname(_paths.SCRIPTS),
                        "Build", "Mac", "Resources", "Info.Template.plist")


class MacPlistTest(unittest.TestCase):
    def test_full_screen_stays_clear_of_the_notch(self):
        with open(TEMPLATE, "rb") as handle:
            keys = plistlib.load(handle)
        self.assertIs(keys.get("NSPrefersDisplaySafeAreaCompatibilityMode"), True)


if __name__ == "__main__":
    unittest.main()
