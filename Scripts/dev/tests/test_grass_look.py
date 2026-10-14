"""The dark grass and the patch (forest_generator/grass_look.py): which levels
have the colour, which the patch and which a density of their own, that the
patch is planted as the clump was but for its mesh, name, material and
height, and that the material instances are content git carries."""

import dataclasses
import os
import subprocess
import unittest

import _paths

from forest_generator import grass_look as L
from forest_generator.grass_placement import DEFAULT_DENSITY_PER_SQM, DEFAULT_GRASS_SPECS
from forest_generator.undergrowth_meshes import GRASS_02_09, GRASS_PATCH, asset_path, content_file

ROOT = os.path.dirname(_paths.SCRIPTS)


class Levels(unittest.TestCase):
    def test_the_forest_levels_have_the_colour_and_the_200_m_one_the_patch(self):
        self.assertEqual(L.DARK_GRASS_LEVELS, ("Lvl_Forest_200m", "Lvl_Forest_1000m"))
        self.assertEqual(L.PATCH_GRASS_LEVELS, ("Lvl_Forest_200m",))

    def test_any_other_level_plants_the_default_specs(self):
        # None is what a verify script written before the level argument passes.
        for level in ("Lvl_Probe_50m", "Lvl_Title", None):
            self.assertEqual(L.grass_specs_for(level), DEFAULT_GRASS_SPECS, level)

    def test_the_1_km_level_has_the_colour_alone(self):
        specs = L.grass_specs_for("Lvl_Forest_1000m")
        self.assertEqual(len(specs), len(DEFAULT_GRASS_SPECS))
        for dark, plain in zip(specs, DEFAULT_GRASS_SPECS):
            self.assertEqual(dark.material_paths, [L.material_object_path()])
            self.assertEqual(dataclasses.replace(dark, material_paths=plain.material_paths),
                             plain)

    def test_the_density_doubled_everywhere_but_on_the_1_km_level(self):
        self.assertEqual(DEFAULT_DENSITY_PER_SQM, 2.2)
        self.assertEqual(L.HELD_DENSITY_PER_SQM, {"Lvl_Forest_1000m": 1.1})
        self.assertEqual(L.density_for("Lvl_Forest_1000m"), 1.1)
        for level in ("Lvl_Forest_200m", "Lvl_Probe_50m", None):
            self.assertEqual(L.density_for(level), DEFAULT_DENSITY_PER_SQM, level)

    def test_the_default_specs_are_not_touched(self):
        L.grass_specs_for("Lvl_Forest_200m")
        self.assertEqual([list(s.material_paths) for s in DEFAULT_GRASS_SPECS], [[]])
        self.assertEqual([s.width_jitter for s in DEFAULT_GRASS_SPECS], [(0.85, 1.20)])


class PatchSpecs(unittest.TestCase):
    def setUp(self):
        self.specs = L.grass_specs_for("Lvl_Forest_200m")

    def test_each_draws_the_patch_s_dark_instance(self):
        for spec in self.specs:
            self.assertEqual(spec.material_paths, [L.patch_material_object_path()])
        self.assertEqual(L.patch_material_object_path(),
                         "/Game/Forest/Undergrowth/MI_Grass_Patch_Dark.MI_Grass_Patch_Dark")
        self.assertEqual(L.material_object_path(),
                         "/Game/Forest/Materials/MI_Grass_02_09_Dark.MI_Grass_02_09_Dark")

    def test_only_the_mesh_its_name_material_and_height_differ(self):
        self.assertEqual(len(self.specs), len(DEFAULT_GRASS_SPECS))
        for patch, plain in zip(self.specs, DEFAULT_GRASS_SPECS):
            self.assertEqual(patch.mesh_path, asset_path(GRASS_PATCH))
            self.assertEqual(patch.nominal_mesh_height_cm, GRASS_PATCH.height_cm)
            self.assertTrue(patch.name.startswith("HISM_Grass"), patch.name)
            same = dataclasses.replace(patch, name=plain.name, mesh_path=plain.mesh_path,
                                       material_paths=plain.material_paths,
                                       nominal_mesh_height_cm=plain.nominal_mesh_height_cm)
            self.assertEqual(same, plain)

    def test_the_blades_are_not_stretched(self):
        for spec in self.specs:
            self.assertEqual(spec.width_jitter, (0.85, 1.20))


class Colours(unittest.TestCase):
    def test_the_grass_is_dark_dull_and_olive(self):
        r, g, b = L.GRASS_TINT
        self.assertTrue(b < g <= r <= 1.0, L.GRASS_TINT)
        self.assertLess(L.GRASS_BRIGHTNESS, 0.5)
        self.assertLess(L.GRASS_SATURATION, 1.0)
        self.assertLess(L.GRASS_SUBSURFACE_STRENGTH, 0.5)

    def test_the_ground_is_the_grass_s_hue(self):
        # Each channel's share of the sum, within a few hundredths of the tint's.
        for ground, grass in zip(L.GROUND_TINT, L.GRASS_TINT):
            self.assertAlmostEqual(ground / sum(L.GROUND_TINT),
                                   grass / sum(L.GRASS_TINT), delta=0.04)

    def test_every_scalar_is_one_the_instance_sets(self):
        self.assertEqual(L.GRASS_SCALARS["Brightness"], L.GRASS_BRIGHTNESS)
        self.assertEqual(L.GRASS_SCALARS["Subsurface ColorVariation"],
                         L.GRASS_SCALARS["ColorVariation"])
        self.assertEqual(len(L.GRASS_SCALARS), 6)


class Committed(unittest.TestCase):
    def test_the_instance_is_ours_and_its_parent_the_pack_s(self):
        self.assertTrue(L.GRASS_MATERIAL.startswith("/Game/Forest/Materials/MI_"))
        self.assertIn(L.GRASS_MATERIAL_PARENT, GRASS_02_09.packages)
        self.assertEqual(set(L.GRASS_MATERIAL_PACKAGES),
                         {L.GRASS_MATERIAL, *GRASS_02_09.packages})
        self.assertIn(L.GRASS_MATERIAL, GRASS_PATCH.packages)
        self.assertIn(L.PATCH_MATERIAL, GRASS_PATCH.packages)

    def test_git_does_not_ignore_the_instances(self):
        for package in (L.GRASS_MATERIAL, L.PATCH_MATERIAL):
            path = content_file(package)
            done = subprocess.run(["git", "check-ignore", path], cwd=ROOT,
                                  capture_output=True, text=True)
            self.assertEqual(done.stdout.strip(), "")
            self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)


if __name__ == "__main__":
    unittest.main()
