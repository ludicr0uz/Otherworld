"""The Free Animation Library's clips the game plays: one table, one import
path, and nothing of the pack committed (Scripts/asset_pipeline/fal_paths.py).
"""

import os
import unittest

import _paths

from asset_pipeline import fal_paths

ROOT = os.path.dirname(_paths.SCRIPTS)


class FalImport(unittest.TestCase):
    def test_every_clip_is_the_packs_and_lands_beside_it(self):
        self.assertEqual(len(set(fal_paths.CLIPS)), len(fal_paths.CLIPS))
        for clip in fal_paths.CLIPS:
            self.assertTrue(clip.startswith(fal_paths.GAME_ROOT + "/Animations/"), clip)
            copy = fal_paths.uefn_clip(clip)
            self.assertTrue(copy.startswith(fal_paths.UEFN_DIR + "/" + fal_paths.UEFN_PREFIX))
            self.assertTrue(copy.endswith(clip.rsplit("/", 1)[1]))

    def test_the_prone_is_an_idle_and_a_forward_loop_of_the_table(self):
        self.assertIn(fal_paths.PRONE_IDLE, fal_paths.CLIPS)
        self.assertIn(fal_paths.PRONE_FWD, fal_paths.CLIPS)
        self.assertGreater(fal_paths.PRONE_FWD_TRAVEL_CM, 0.0)

    def test_the_pack_and_its_copies_are_not_committed(self):
        with open(os.path.join(ROOT, ".gitignore")) as handle:
            ignored = {line.strip() for line in handle}
        self.assertIn("/" + fal_paths.CONTENT_DIR + "/", ignored)
        for made in (fal_paths.UEFN_DIR, fal_paths.RIG_DIR):
            self.assertTrue(made.startswith(fal_paths.GAME_ROOT + "/"), made)


if __name__ == "__main__":
    unittest.main()
