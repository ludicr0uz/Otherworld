"""forest_generator/low_leaves.py: which trees are walked through."""

import unittest

import _paths  # noqa: F401

from forest_generator import low_leaves as LL
from forest_generator.tree_meshes import PINE_SAPLING_A, TREE_MESH_RECIPES
from forest_generator.tree_placement import DEFAULT_TREE_SPECS


class LowLeaves(unittest.TestCase):
    def test_every_planted_tree_has_its_leaves_measured(self):
        self.assertEqual(set(LL.LEAVES), {r.name for r in TREE_MESH_RECIPES})
        for recipe in TREE_MESH_RECIPES:
            slot, _floor = LL.LEAVES[recipe.name]
            self.assertLess(slot, len(recipe.material_paths), recipe.name)

    def test_only_the_sapling_is_walked_through(self):
        self.assertEqual([s.mesh_path for s in LL.LOW_LEAF_TREE_SPECS],
                         [PINE_SAPLING_A.object_path])

    def test_the_rule_is_the_largest_tree(self):
        for spec in DEFAULT_TREE_SPECS:
            low = LL.lowest_leaf_cm(spec) < LL.WALKER_HEAD_CM
            self.assertEqual(spec in LL.LOW_LEAF_TREE_SPECS, low, spec.name)

    def test_both_builds_of_each_mesh(self):
        self.assertEqual(LL.low_leaf_mesh_paths(), [
            "/Game/Forest/Trees/SM_PineSapling_A.SM_PineSapling_A",
            "/Game/Forest/TreesLOD/SM_PineSapling_A.SM_PineSapling_A"])


if __name__ == "__main__":
    unittest.main()
