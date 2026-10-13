"""The title's trees are the play level's own middle ones: title/forest.py
runs the forest's scatter again, and what it keeps must be, one for one,
what the generated import of the play level plants within the same radius."""

import json
import math
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from forest_generator.tree_lods import plants_lods                   # noqa: E402
from title import forest                                             # noqa: E402
from title import paths as P                                         # noqa: E402

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PLAY_NAME = P.PLAY_LEVEL.rsplit("/", 1)[1]


def _play_import():
    with open(os.path.join(SCRIPTS, "generated_levels", PLAY_NAME,
                           f"import_{PLAY_NAME}.py")) as f:
        return f.read()


def _key(t):
    return (t["spec"], t["x"], t["y"], t["yaw"], t["scale"])


class TitleForestTest(unittest.TestCase):
    def test_the_trees_are_the_play_levels_middle_ones(self):
        src = _play_import()
        planted = json.loads(re.search(r"^TREE_DATA = (\[.*\])$", src, re.M).group(1))
        near = [t for t in planted if math.hypot(t["x"], t["y"]) <= P.TREE_RADIUS_CM]
        mine = forest.trees()
        self.assertGreater(len(mine), 150)
        self.assertEqual(sorted(map(_key, mine)), sorted(map(_key, near)))

    def test_the_species_are_planted_from_the_play_levels_meshes(self):
        src = _play_import()
        configs = json.loads(
            re.search(r'^TREE_CONFIGS = json\.loads\(r"""(.*)"""\)$', src, re.M).group(1))
        self.assertEqual(forest.configs(), configs)
        self.assertEqual(plants_lods(P.TITLE_LEVEL_NAME), plants_lods(PLAY_NAME))

    def test_the_stage_is_clear_and_the_floor_holds_every_tree(self):
        mine = forest.trees()
        # The figure and the camera stand inside the scatter's clearing.
        self.assertGreaterEqual(min(math.hypot(t["x"], t["y"]) for t in mine), 700.0)
        self.assertLess(math.hypot(*P.CAMERA[:2]), 700.0)
        # The cube is 100 cm wide: half its scaled width reaches past the trees.
        self.assertGreater(P.FLOOR_SCALE[0] * 50.0, P.TREE_RADIUS_CM)
        # Each tree is sunk into a flat floor whose top is z = 0.
        self.assertTrue(all(-120.0 < t["z"] < 0.0 for t in mine))
        self.assertEqual(sum(forest.counts(mine).values()), len(mine))


if __name__ == "__main__":
    unittest.main()
