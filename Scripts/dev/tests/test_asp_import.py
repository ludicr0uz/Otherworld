"""The Animation Starter Pack's clips the game plays: one table, one import
path, nothing of the pack committed (Scripts/asset_pipeline/asp_paths.py), and
the carry's numbers in range (Scripts/combat/carry_pose_consts.py).
"""

import os
import unittest

import _paths

from asset_pipeline import asp_paths
from combat import carry_pose_consts as C

ROOT = os.path.dirname(_paths.SCRIPTS)


class AspImport(unittest.TestCase):
    def test_every_clip_is_the_packs_and_lands_beside_it(self):
        self.assertEqual(len(set(asp_paths.CLIPS)), len(asp_paths.CLIPS))
        for clip in asp_paths.CLIPS:
            self.assertTrue(clip.startswith(asp_paths.GAME_ROOT + "/"), clip)
            copy = asp_paths.uefn_clip(clip)
            self.assertTrue(copy.startswith(asp_paths.UEFN_DIR + "/" + asp_paths.UEFN_PREFIX))
            self.assertTrue(copy.endswith(clip.rsplit("/", 1)[1]))

    def test_the_carry_is_five_clips_of_the_table(self):
        carry = (asp_paths.CARRY_IDLE, asp_paths.CARRY_JOG, asp_paths.CARRY_SPRINT,
                 asp_paths.CARRY_CROUCH_IDLE, asp_paths.CARRY_CROUCH_WALK)
        self.assertEqual(len(set(carry)), 5)
        for clip in carry:
            self.assertIn(clip, asp_paths.CLIPS)

    def test_the_ue4_mannequins_spine_and_neck_are_its_own(self):
        self.assertEqual(asp_paths.CHAINS["Spine"], ("spine_01", "spine_03"))
        self.assertEqual(asp_paths.CHAINS["Neck"], ("neck_01", "neck_01"))

    def test_the_pack_and_its_copies_are_not_committed(self):
        with open(os.path.join(ROOT, ".gitignore")) as handle:
            ignored = {line.strip() for line in handle}
        # The folder, or (since the clips the game plays are committed) all under it.
        root = "/" + asp_paths.CONTENT_DIR + "/"
        self.assertTrue({root, root + "**"} & ignored, root)
        for made in (asp_paths.UEFN_DIR, asp_paths.RIG_DIR):
            self.assertTrue(made.startswith(asp_paths.GAME_ROOT + "/"), made)

    def test_the_carrys_numbers(self):
        self.assertNotEqual(C.CARRY_POSE, C.CARRY_SPRINT)
        for speed in (C.CARRY_BLEND_SPEED, C.CARRY_SPRINT_BLEND_SPEED):
            self.assertGreater(speed, 0.0)
        # The jog's clip is all in by the jog's speed (4 m/s), and not at a creep.
        self.assertTrue(100.0 <= C.CARRY_JOG_FULL_CM_S <= 400.0)
        # The crouch walk's is all in under the crouch's own pace (0.45 of the
        # jog's 4 m/s), and under the standing carry's.
        self.assertTrue(50.0 <= C.CARRY_CROUCH_WALK_FULL_CM_S <= 180.0)
        self.assertLess(C.CARRY_CROUCH_WALK_FULL_CM_S, C.CARRY_JOG_FULL_CM_S)


if __name__ == "__main__":
    unittest.main()
