"""The library meshes the grass and the bushes are planted from
(forest_generator/undergrowth_meshes.py): the specs plant them, the offline
check passes, and git carries exactly the packages they need out of two
otherwise ignored packs."""

import os
import subprocess
import unittest

import _paths

from forest_generator import undergrowth_meshes as U
from forest_generator.bush_placement import DEFAULT_BUSH_SPECS
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
                         [U.asset_path(m) for m in U.GRASS_MESHES])
        self.assertEqual([s.mesh_path for s in DEFAULT_BUSH_SPECS],
                         [U.asset_path(m) for m in U.BUSH_MESHES])

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
        for mesh in U.UNDERGROWTH_MESHES:
            pack = "/".join(mesh.mesh.split("/")[:3]) + "/"
            self.assertIn(mesh.mesh, mesh.packages)
            self.assertTrue(all(p.startswith(pack) for p in mesh.packages), mesh.name)

    def test_gitignore_names_each_package(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            lines = set(fh.read().split("\n"))
        self.assertEqual([line for line in U.gitignore_lines() if line not in lines], [])

    def test_git_carries_the_packages_and_nothing_else_of_the_packs(self):
        files = [U.content_file(p) for p in U.shipped_packages()]
        self.assertEqual(_ignored(files), set())
        others = ["Content/PN_GrassLibrary/Meshes/grassMesh/grass_02_08_mesh.uasset",
                  "Content/Light_Foliage/Meshes/SM_Bush_01.uasset",
                  "Content/Light_Foliage/Maps/Showcase.umap"]
        self.assertEqual(_ignored(others), set(others))


if __name__ == "__main__":
    unittest.main()
