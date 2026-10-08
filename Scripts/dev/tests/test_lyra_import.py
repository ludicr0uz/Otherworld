"""Lyra's copy: its redirect is in the engine's config and moves nothing of
the game's.

Content/Sourced/Lyra is a byte copy of packages that still name each other by
Lyra's /Game paths (Scripts/asset_pipeline/lyra_paths.py). A clip there loads
with its skeleton only while each row of REDIRECTED has its [CoreRedirects]
line in Config/DefaultEngine.ini; a redirect over a folder the game has
content of its own in would move the game's packages too.
"""

import os
import unittest

import _paths

from asset_pipeline import lyra_paths

ROOT = os.path.dirname(_paths.SCRIPTS)


class LyraImport(unittest.TestCase):
    def test_the_redirects_are_in_the_engine_ini(self):
        with open(os.path.join(ROOT, "Config", "DefaultEngine.ini")) as handle:
            have = {line.strip() for line in handle}
        self.assertEqual([l for l in lyra_paths.redirect_lines() if l not in have], [])

    def test_no_redirect_covers_a_folder_the_game_keeps_content_in(self):
        for old in lyra_paths.REDIRECTED:
            here = os.path.join(ROOT, "Content", old[len("/Game/"):].rstrip("/"))
            self.assertFalse(os.path.isdir(here) or os.path.exists(here + ".uasset"),
                             f"{old} is the game's own: {here}")

    def test_every_clip_is_under_a_redirected_folder_and_lands_beside_the_pack(self):
        for clip in lyra_paths.CLIPS:
            self.assertTrue(clip.startswith(lyra_paths.GAME_ROOT + "/"), clip)
            there = "/Game" + clip[len(lyra_paths.GAME_ROOT):]
            self.assertTrue(any(there.startswith(old) for old in lyra_paths.REDIRECTED), clip)
            self.assertTrue(lyra_paths.uefn_clip(clip).startswith(lyra_paths.UEFN_DIR + "/"))

    def test_the_pack_is_not_committed(self):
        with open(os.path.join(ROOT, ".gitignore")) as handle:
            self.assertIn("/" + lyra_paths.CONTENT_DIR + "/", {l.strip() for l in handle})


if __name__ == "__main__":
    unittest.main()
