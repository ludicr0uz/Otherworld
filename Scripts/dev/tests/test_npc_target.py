"""The scan a patrolling wanderer picks its candidate from (npc/target.py,
forest_generator/npc_agro.NPC_TARGET_SCAN_CM) has to hold every player one of
its own senses could answer for: a player inside a creature's sight or touch
but outside the scan would be asked about only when no one else was near."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forest_generator.npc_agro import NPC_AGRO, NPC_TARGET_SCAN_CM   # noqa: E402
from forest_generator.npc_placement import NPC_VARIANTS              # noqa: E402
from npc.monster_tuning import monster_specs                         # noqa: E402


class TargetScanTest(unittest.TestCase):
    def test_scan_holds_every_built_sense(self):
        for key, settings in NPC_AGRO.items():
            with self.subTest(creature=key):
                self.assertGreater(NPC_TARGET_SCAN_CM, settings.vision_range_cm)
                self.assertGreater(NPC_TARGET_SCAN_CM, settings.touch_range_cm)

    def test_scan_holds_every_tuned_sense(self):
        """monster_tuning.csv lies over the built numbers: the same rule."""
        for variant in NPC_VARIANTS:
            spec = monster_specs(variant.key)
            with self.subTest(creature=variant.key):
                self.assertGreater(NPC_TARGET_SCAN_CM, spec["vision_range_cm"])
                self.assertGreater(NPC_TARGET_SCAN_CM, spec["touch_range_cm"])


if __name__ == "__main__":
    unittest.main()
