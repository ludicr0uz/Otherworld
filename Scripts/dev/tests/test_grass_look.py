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
from forest_generator.grass_cells import EXTRA_LAYERS_PRESET, GRASS_TIERS, tier_densities
from forest_generator.grass_placement import DEFAULT_DENSITY_PER_SQM, DEFAULT_GRASS_SPECS
from graphics_menu.gfx_stats import PRESET_LABELS
from forest_generator.undergrowth_meshes import GRASS_02_09, GRASS_PATCH, asset_path, content_file

ROOT = os.path.dirname(_paths.SCRIPTS)


class Levels(unittest.TestCase):
    def test_the_forest_levels_have_the_colour_and_the_200_m_one_the_patch(self):
        self.assertEqual(L.DARK_GRASS_LEVELS,
                         ("Lvl_Forest_200m", "Lvl_Forest_1000m", "Lvl_Horde_Survival"))
        self.assertEqual(L.PATCH_GRASS_LEVELS, ("Lvl_Forest_200m",))

    def test_any_other_level_plants_the_default_specs(self):
        # None is what a verify script written before the level argument passes.
        for level in ("Lvl_Probe_50m", "Lvl_Title", None):
            self.assertEqual(L.grass_specs_for(level), DEFAULT_GRASS_SPECS, level)

    def test_the_1_km_level_has_the_colour_alone(self):
        # Its meadow; the six other types are VariedGrass's.
        specs = L.grass_specs_for("Lvl_Forest_1000m")[:len(DEFAULT_GRASS_SPECS)]
        for dark, plain in zip(specs, DEFAULT_GRASS_SPECS):
            self.assertEqual(dark.material_paths, [L.material_object_path()])
            self.assertEqual(dataclasses.replace(dark, material_paths=plain.material_paths),
                             plain)

    def test_the_density_grew_everywhere_but_on_the_1_km_level(self):
        # 4.4 with all eight layers: the first four are G2's 2.2 (F1).
        self.assertEqual(DEFAULT_DENSITY_PER_SQM, 4.4)
        self.assertEqual(L.HELD_DENSITY_PER_SQM,
                         {"Lvl_Forest_1000m": 1.1, "Lvl_Horde_Survival": 1.1})
        self.assertEqual(L.density_for("Lvl_Forest_1000m"), 1.1)
        for level in ("Lvl_Forest_200m", "Lvl_Probe_50m", None):
            self.assertEqual(L.density_for(level), DEFAULT_DENSITY_PER_SQM, level)

    def test_the_1_km_level_keeps_its_four_tiers(self):
        self.assertEqual(L.tiers_for("Lvl_Forest_1000m"), GRASS_TIERS[:4])
        for level in ("Lvl_Forest_200m", "Lvl_Probe_50m", None):
            self.assertEqual(L.tiers_for(level), GRASS_TIERS, level)


class Tiers(unittest.TestCase):
    """F1: eight layers, of which the first four are what they were."""

    def test_eight_layers(self):
        self.assertEqual(len(GRASS_TIERS), 8)

    def test_the_first_four_layers_are_g2_s(self):
        g2 = [2.2 * s for s in (0.4, 0.2, 0.2, 0.2)]
        for got, want in zip(tier_densities(DEFAULT_DENSITY_PER_SQM)[:4], g2):
            self.assertAlmostEqual(got, want)
        self.assertEqual([(t.cull_start_cm, t.cull_end_cm) for t in GRASS_TIERS[:4]],
                         [(4500, 7000), (3500, 5000), (2500, 3500), (1500, 2500)])

    def test_the_1_km_level_s_tiers_are_its_old_ones(self):
        held = tier_densities(L.density_for("Lvl_Forest_1000m"),
                              L.tiers_for("Lvl_Forest_1000m"))
        for got, want in zip(held, [1.1 * s for s in (0.4, 0.2, 0.2, 0.2)]):
            self.assertAlmostEqual(got, want)

    def test_layers_five_to_eight_are_the_slider_s_alone_and_near(self):
        for t in GRASS_TIERS[4:]:
            self.assertEqual(t.min_preset, EXTRA_LAYERS_PRESET)
            self.assertLessEqual(t.cull_end_cm, GRASS_TIERS[3].cull_end_cm)
        ends = [t.cull_end_cm for t in GRASS_TIERS]
        self.assertEqual(ends, sorted(ends, reverse=True))
        # Every preset (Low, Medium, High, Custom) is below it.
        self.assertEqual(EXTRA_LAYERS_PRESET, len(PRESET_LABELS))

    def test_eight_layers_double_four(self):
        d = tier_densities(DEFAULT_DENSITY_PER_SQM)
        self.assertAlmostEqual(sum(d), 2 * sum(d[:4]))


    def test_the_default_specs_are_not_touched(self):
        L.grass_specs_for("Lvl_Forest_200m")
        self.assertEqual([list(s.material_paths) for s in DEFAULT_GRASS_SPECS], [[]])
        self.assertEqual([s.width_jitter for s in DEFAULT_GRASS_SPECS], [(0.85, 1.20)])


class PatchSpecs(unittest.TestCase):
    def setUp(self):
        # The meadow; the six other types are VariedGrass's.
        self.specs = L.grass_specs_for("Lvl_Forest_200m")[:len(DEFAULT_GRASS_SPECS)]

    def test_each_draws_the_patch_s_dark_instance(self):
        for spec in self.specs:
            self.assertEqual(spec.material_paths, [L.patch_material_object_path()])
        self.assertEqual(L.patch_material_object_path(),
                         "/Game/Forest/Undergrowth/MI_Grass_Patch_Dark.MI_Grass_Patch_Dark")
        self.assertEqual(L.material_object_path(),
                         "/Game/Forest/Materials/MI_Grass_02_09_Dark.MI_Grass_02_09_Dark")

    def test_only_the_mesh_its_name_material_and_height_differ(self):
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


class VariedGrass(unittest.TestCase):
    """F2: seven grass types on the two forest levels, the meadow first."""

    def test_the_forest_levels_plant_seven_types(self):
        self.assertEqual(L.VARIED_GRASS_LEVELS,
                         ("Lvl_Forest_200m", "Lvl_Forest_1000m", "Lvl_Horde_Survival"))
        for level in L.VARIED_GRASS_LEVELS:
            specs = L.grass_specs_for(level)
            self.assertEqual(len(specs), 7, level)
            self.assertEqual(len({s.name for s in specs}), 7, level)
            # The prefix the import's cleanup sweeps on.
            self.assertTrue(all(s.name.startswith("HISM_Grass") for s in specs), level)
            self.assertEqual(len({s.mesh_path for s in specs}), 7, level)
            self.assertEqual(len({tuple(s.material_paths) for s in specs}), 7, level)
        for level in ("Lvl_Probe_50m", "Lvl_Title", None):
            self.assertFalse(L.has_varied_grass(level))

    def test_each_type_draws_its_own_dark_instance(self):
        for t in L.LOW_GRASS_TYPES:
            self.assertTrue(t.material.startswith("/Game/Forest/Materials/MI_LowGrass_"))
            self.assertTrue(t.material.endswith("_Dark"))
            self.assertIn(t.material_parent, t.mesh.packages)
            self.assertNotEqual(t.material_parent, L.GRASS_MATERIAL_PARENT)
        self.assertEqual(L.LOW_GRASS_MATERIALS, tuple(t.material for t in L.LOW_GRASS_TYPES))

    def test_only_the_patch_level_plants_a_spot_more_than_once(self):
        for spec in L.grass_specs_for("Lvl_Forest_1000m"):
            self.assertEqual(spec.density_scale, 1.0, spec.name)
        specs = L.grass_specs_for("Lvl_Forest_200m")
        self.assertEqual(specs[0].density_scale, 1.0)
        for spec in specs[1:]:
            self.assertTrue(1.0 <= spec.density_scale <= 2.0, spec.name)

    def test_most_types_stand_in_the_knee_layer(self):
        # verification.check_grass_knee_height holds a ratio of 0.85 and up to
        # the knee band; one short lawn is allowed under it.
        ratios = [t.height_ratio for t in L.LOW_GRASS_TYPES]
        self.assertEqual(sum(r < 0.85 for r in ratios), 1)
        self.assertTrue(all(0.5 <= r <= 1.3 for r in ratios), ratios)

    def test_the_tints_are_dark_olive_like_the_meadow_s(self):
        for t in L.LOW_GRASS_TYPES:
            r, g, b = t.tint
            self.assertTrue(b < g <= r <= 1.0, (t.name, t.tint))

    def test_the_widths_are_not_stretched_flat(self):
        for t in L.LOW_GRASS_TYPES:
            self.assertLessEqual(t.width_jitter[1], 1.4, t.name)


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
        for package in (L.GRASS_MATERIAL, L.PATCH_MATERIAL) + L.LOW_GRASS_MATERIALS:
            path = content_file(package)
            done = subprocess.run(["git", "check-ignore", path], cwd=ROOT,
                                  capture_output=True, text=True)
            self.assertEqual(done.stdout.strip(), "")
            self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)


if __name__ == "__main__":
    unittest.main()
