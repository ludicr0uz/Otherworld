"""combat/reload_tuning.py: every gun that reloads with a clip names a row of
gun_rows.GUN_DEFAULTS (where its reload time is read) and a clip field of
PlayerSkin, and the rate fits the clip to the reload.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import os
import re
import unittest

import _paths  # noqa: F401

from combat import reload_tuning as R
from combat.gun_rows import GUN_DEFAULTS, gun_row

SKIN = os.path.join(os.path.dirname(__file__), "..", "..", "combat", "skin.py")


class ReloadClips(unittest.TestCase):
    def test_rows_name_a_gun_and_a_skin_field(self):
        with open(SKIN) as f:
            fields = set(re.findall(r"^    (reload_\w+): str = None", f.read(), re.M))
        for name, (display, field) in R.RELOAD_CLIP_GUNS.items():
            self.assertTrue(name.startswith("BP_"), name)
            self.assertIn(display, GUN_DEFAULTS, name)
            self.assertIn(field, fields, name)

    def test_the_pistols_reload_with_the_pistol_clip(self):
        self.assertEqual(R.RELOAD_CLIP_GUNS["BP_Pistol"][1], "reload_pistol")
        self.assertEqual(R.RELOAD_CLIP_GUNS["BP_SMG"][1], "reload_pistol")

    def test_rate_ends_the_clip_with_the_reload(self):
        for clip_s in (2.0, 2.2):
            for display, _field in R.RELOAD_CLIP_GUNS.values():
                secs = gun_row(display)["reload_s"]
                self.assertAlmostEqual(clip_s / R.reload_rate(clip_s, secs), secs)

    def test_handover_fits_the_shortest_reload(self):
        shortest = min(gun_row(d)["reload_s"] for d, _f in R.RELOAD_CLIP_GUNS.values())
        self.assertLess(R.RELOAD_BLEND_OUT_S, R.RELOAD_HANDOVER_S)
        self.assertLess(R.RELOAD_HANDOVER_S, shortest / 2)


if __name__ == "__main__":
    unittest.main()
