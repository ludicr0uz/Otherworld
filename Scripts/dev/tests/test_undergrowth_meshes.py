"""The library meshes the grass and the bushes are planted from
(forest_generator/undergrowth_meshes.py), and the grass patch made of one: the
specs plant them, the offline check passes, and git carries exactly the
packages they need out of two otherwise ignored packs."""

import os
import subprocess
import unittest

import _paths

from forest_generator import undergrowth_meshes as U
from forest_generator.bush_placement import DEFAULT_BUSH_SPECS
from forest_generator.grass_look import (PATCH_GRASS_LEVELS, VARIED_GRASS_LEVELS,
                                         grass_specs_for)
from forest_generator.grass_placement import DEFAULT_GRASS_SPECS
from forest_generator.undergrowth_checks import check_undergrowth_meshes

ROOT = os.path.dirname(_paths.SCRIPTS)


def _ignored(paths):
    """Which of ``paths`` git ignores."""
    done = subprocess.run(["git", "check-ignore", *paths], cwd=ROOT,
                          capture_output=True, text=True)
    return set(done.stdout.split("\n")) - {""}


class Specs(unittest.TestCase):
    def test_the_specs_plant_the_library_meshes(self):
        self.assertEqual([s.mesh_path for s in DEFAULT_GRASS_SPECS],
                         [U.asset_path(U.GRASS_02_09)])
        self.assertEqual(U.GRASS_MESHES,
                         (U.GRASS_02_09, U.GRASS_PATCH) + U.LOW_GRASS_MESHES)
        self.assertEqual(len(U.LOW_GRASS_MESHES), 6)
        self.assertEqual([s.mesh_path for s in DEFAULT_BUSH_SPECS],
                         [U.asset_path(m) for m in U.BUSH_MESHES])

    def test_a_patch_level_s_meadow_is_the_patch(self):
        for level in PATCH_GRASS_LEVELS:
            self.assertEqual(grass_specs_for(level)[0].mesh_path,
                             U.asset_path(U.GRASS_PATCH), level)

    def test_a_varied_level_plants_the_six_low_grasses_besides(self):
        for level in VARIED_GRASS_LEVELS:
            self.assertEqual([s.mesh_path for s in grass_specs_for(level)[1:]],
                             [U.asset_path(m) for m in U.LOW_GRASS_MESHES], level)

    def test_a_cell_draws_the_mesh_s_own_materials(self):
        for spec in DEFAULT_GRASS_SPECS + DEFAULT_BUSH_SPECS:
            self.assertEqual(list(spec.material_paths), [], spec.name)

    def test_labels_keep_the_prefixes_the_import_sweeps_on(self):
        self.assertTrue(all(s.name.startswith("HISM_Grass") for s in DEFAULT_GRASS_SPECS))
        self.assertTrue(all(s.name.startswith("HISM_Bush") for s in DEFAULT_BUSH_SPECS))

    def test_the_offline_check_passes(self):
        result = check_undergrowth_meshes()
        self.assertTrue(result.passed, result.details)


class Committed(unittest.TestCase):
    def test_every_package_is_in_its_own_pack(self):
        for mesh in (U.GRASS_02_09, U.BUSH_02) + U.LOW_GRASS_MESHES:
            pack = "/".join(mesh.mesh.split("/")[:3]) + "/"
            self.assertIn(mesh.mesh, mesh.packages)
            self.assertTrue(all(p.startswith(pack) for p in mesh.packages), mesh.name)

    def test_the_patch_needs_the_clump_s_material_not_the_clump(self):
        patch, clump = U.GRASS_PATCH, U.GRASS_02_09
        self.assertIn(patch.mesh, patch.packages)
        self.assertNotIn(clump.mesh, patch.packages)
        ours = [p for p in patch.packages if not U.in_a_pack(p)]
        self.assertTrue(all(p.startswith("/Game/Forest/") for p in ours), ours)
        self.assertEqual(set(patch.packages) - set(ours), set(clump.packages) - {clump.mesh})

    def test_our_packages_are_committed(self):
        ours = [p for p in U.shipped_packages() if not U.in_a_pack(p)]
        self.assertEqual(len(ours), 5)
        files = [U.content_file(p) for p in ours]
        self.assertEqual(_ignored(files), set())
        for path in files:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)

    def test_gitignore_names_each_package(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            lines = set(fh.read().split("\n"))
        self.assertEqual([line for line in U.gitignore_lines() if line not in lines], [])
        named = {line for line in lines
                 if line.startswith(tuple(f"!/Content/{r[len('/Game/'):]}/"
                                          for r in U.PACK_ROOTS))
                 and not line.endswith("/**/")}
        self.assertEqual(named, set(U.gitignore_lines()))

    def test_git_carries_the_packages_and_nothing_else_of_the_packs(self):
        files = [U.content_file(p) for p in U.shipped_packages()]
        self.assertEqual(_ignored(files), set())
        others = ["Content/PN_GrassLibrary/Meshes/grassMesh/grass_02_08_mesh.uasset",
                  "Content/Light_Foliage/Meshes/SM_Bush_01.uasset",
                  "Content/Light_Foliage/Maps/Showcase.umap"]
        self.assertEqual(_ignored(others), set(others))


if __name__ == "__main__":
    unittest.main()
