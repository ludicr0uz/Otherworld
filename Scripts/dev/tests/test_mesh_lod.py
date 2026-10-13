"""mesh_lod's pure half: the spec's arithmetic, the jobs, the impostor's
planes and the atlas."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from mesh_lod import jobs, planes                                    # noqa: E402
from mesh_lod import spec as S                                       # noqa: E402

try:
    import numpy as np
    from mesh_lod import atlas
except ImportError:                                                  # pragma: no cover
    np = atlas = None


class SpecTest(unittest.TestCase):
    def test_default_spec_is_buildable(self):
        self.assertEqual(S.LodSpec().problems(), [])

    def test_overrides_coerce_command_line_text(self):
        spec = S.with_overrides(S.LodSpec(), {"lod0_triangles": "60000",
                                              "lod_distances_m": "40,80,150",
                                              "impostor": "no", "foliage_slots": [1, 2]})
        self.assertEqual(spec.lod0_triangles, 60000)
        self.assertEqual(spec.lod_distances_m, (40.0, 80.0, 150.0))
        self.assertFalse(spec.impostor)
        self.assertEqual(spec.foliage_slots, (1, 2))

    def test_unknown_setting_is_refused(self):
        with self.assertRaises(ValueError):
            S.with_overrides(S.LodSpec(), {"lod_triangles": 1})

    def test_distances_must_match_the_lods(self):
        spec = S.with_overrides(S.LodSpec(), {"impostor": False})
        self.assertTrue(spec.problems())            # three distances, two LODs after the first
        spec = S.with_overrides(spec, {"lod_distances_m": [30, 60]})
        self.assertEqual(spec.problems(), [])
        self.assertTrue(S.with_overrides(S.LodSpec(), {"lod_distances_m": [60, 30, 90]}).problems())

    def test_a_changed_setting_changes_the_stamp(self):
        self.assertNotEqual(S.LodSpec().stamp, S.with_overrides(S.LodSpec(), {"lod_ratio": 0.5}).stamp)
        self.assertEqual(S.LodSpec().stamp, S.from_dict(S.to_dict(S.LodSpec())).stamp)

    def test_lod_targets_fall_by_the_ratio(self):
        self.assertEqual(S.lod_targets(S.LodSpec(), 200_000), [40_000, 16_000, 6_400])

    def test_a_small_source_keeps_its_triangles(self):
        self.assertEqual(S.lod_targets(S.LodSpec(), 10_000)[0], 10_000)

    def test_slot_budgets_share_by_size_and_keep_the_floor(self):
        budgets = S.slot_budgets(S.LodSpec(), {0: 800, 1: 150_000, 2: 49_200}, 40_000, 0)
        self.assertEqual(budgets[0], 600)           # 160 by share: the floor wins
        self.assertEqual(budgets[1], 30_000)
        self.assertEqual(S.slot_budgets(S.LodSpec(), {0: 100, 1: 200}, 40_000, 0), {0: 100, 1: 200})

    def test_foliage_is_simplified_before_pieces_are_dropped(self):
        spec = S.LodSpec()
        cut = S.foliage_cut(spec, 24_000, 1_000, 8_000)        # 24 a piece -> 8 a piece
        self.assertEqual((cut.keep_pieces, cut.simplify), (1.0, True))
        cut = S.foliage_cut(spec, 24_000, 1_000, 2_000)        # 4 a piece is the floor
        self.assertAlmostEqual(cut.keep_pieces, 0.5)
        cut = S.foliage_cut(spec, 3_000, 1_000, 1_500)         # already 3 a piece: drop only
        self.assertEqual((round(cut.keep_pieces, 3), cut.simplify), (0.5, False))
        self.assertEqual(S.foliage_cut(spec, 100, 10, 500).keep_pieces, 1.0)

    def test_screen_size_halves_as_distance_doubles(self):
        spec = S.LodSpec()
        self.assertAlmostEqual(S.screen_size(spec, 1000.0, 50.0), 2 * S.screen_size(spec, 1000.0, 100.0))
        # 90 degrees at 16:9: the multiple is 8/9, so a 10 m sphere 100 m off is 0.1778.
        self.assertAlmostEqual(S.screen_size(spec, 1000.0, 100.0), 16.0 / 90.0)

    def test_screen_sizes_fall(self):
        for radius in (200.0, 1000.0, 5000.0):
            sizes = S.screen_sizes(S.with_overrides(S.LodSpec(), {"planted_scale": 3}), radius)
            self.assertEqual(len(sizes), 4)
            self.assertEqual(sizes, sorted(sizes, reverse=True))
            self.assertGreater(sizes[0], sizes[1])


class JobsTest(unittest.TestCase):
    def test_tree_jobs_are_buildable_and_distinct(self):
        self.assertEqual(len({j.path for j in jobs.TREES}), 5)
        for job in jobs.TREES:
            self.assertEqual(job.spec.problems(), [])
            self.assertTrue(job.path.startswith(jobs.TREE_DEST + "/"))
            self.assertNotEqual(job.path, job.source)

    def test_round_trip(self):
        job = jobs.Job("/Game/A/SM_X", "/Game/B", overrides={"lod_ratio": 0.5})
        again = jobs.from_dict(job.to_dict())
        self.assertEqual((again.path, again.spec), ("/Game/B/SM_X", job.spec))
        self.assertEqual(again.texture_path("BC"), "/Game/B/Impostors/T_SM_X_Impostor_BC")


class PlanesTest(unittest.TestCase):
    def test_frame_crosses_on_a_near_pivot(self):
        frame = planes.frame_of((-8.0, -35.0, 940.0), (340.0, 320.0, 948.0))
        self.assertEqual((frame.centre_x, frame.centre_y), (0.0, 0.0))
        self.assertGreaterEqual(frame.width / 2.0, 348.0)
        self.assertLess(frame.bottom, 940.0 - 948.0 + 1e-6)

    def test_frame_keeps_the_middle_of_an_off_pivot_mesh(self):
        frame = planes.frame_of((1200.0, 0.0, 300.0), (200.0, 200.0, 300.0))
        self.assertEqual(frame.centre_x, 1200.0)

    def test_cells_do_not_overlap_and_stay_inside(self):
        for count in (2, 3, 4, 5):
            cells = [planes.cell_px(k, count, 1024) for k in range(count)]
            for left, top, w, h in cells:
                self.assertTrue(0 <= left and left + w <= 1024 and 0 <= top and top + h <= 1024)
            for i, a in enumerate(cells):
                for b in cells[i + 1:]:
                    apart = (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                             or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
                    self.assertTrue(apart)

    def test_quad_spans_the_frame_and_its_cell(self):
        frame = planes.Frame(0.0, 0.0, -10.0, 400.0, 900.0)
        corners = planes.quad(1, 3, frame, 1024)
        zs = sorted({p[2] for p, _uv in corners})
        self.assertEqual(zs, [-10.0, 890.0])
        for position, _uv in corners:
            self.assertAlmostEqual(math.hypot(position[0], position[1]), 200.0)
        u0, v0, u1, v1 = planes.cell_uv(1, 3, 1024)
        self.assertEqual(sorted({uv[0] for _p, uv in corners}), [u0, u1])
        self.assertEqual(corners[0][1], (u0, v1))               # bottom left of the picture

    def test_tangent_basis_is_right_handed_and_faces_the_camera(self):
        for k in range(3):
            t, b, n = planes.tangent_basis(k, 3)
            cross = (t[1] * b[2] - t[2] * b[1], t[2] * b[0] - t[0] * b[2], t[0] * b[1] - t[1] * b[0])
            for got, want in zip(cross, n):
                self.assertAlmostEqual(got, want)
            yaw = math.radians(planes.camera_yaw(k, 3))
            forward = (math.cos(yaw), math.sin(yaw), 0.0)
            self.assertAlmostEqual(sum(f * c for f, c in zip(forward, n)), -1.0)

    def test_capture_keeps_the_frames_shape(self):
        self.assertEqual(planes.capture_size(planes.Frame(0, 0, 0, 500.0, 1000.0), 1024), (512, 1024))
        self.assertEqual(planes.capture_size(planes.Frame(0, 0, 0, 1000.0, 500.0), 1024), (1024, 512))


@unittest.skipIf(atlas is None, "numpy and Pillow are not installed")
class AtlasTest(unittest.TestCase):
    def _passes(self):
        colour = np.zeros((8, 8, 3), dtype=np.float32)
        world = np.full((8, 8, 3), atlas.EMPTY_NORMAL, dtype=np.float32)
        colour[2:6, 2:6] = 0.2
        world[2:6, 2:6] = planes.tangent_basis(0, 3)[2]          # facing the camera
        return colour, world

    def test_mask_is_where_the_mesh_was_drawn(self):
        colour, world = self._passes()
        mask = atlas.mesh_mask(colour, world)
        self.assertEqual(mask.sum(), 16.0)
        colour[0, 0] = 0.0
        world[0, 0] = (0.0, 0.0, 1.0)                            # black, but a surface
        self.assertEqual(atlas.mesh_mask(colour, world).sum(), 17.0)

    def test_a_normal_facing_the_camera_is_flat_in_tangent_space(self):
        rgba, normal = atlas.plane_pictures(*self._passes(), 0, 3)
        np.testing.assert_allclose(normal[3, 3], (0.5, 0.5, 1.0), atol=1e-5)
        np.testing.assert_allclose(normal[0, 0], (0.5, 0.5, 1.0), atol=1e-5)
        self.assertEqual(rgba[3, 3, 3], 1.0)
        self.assertEqual(rgba[0, 7, 3], 0.0)

    def test_colour_is_spread_past_the_mask(self):
        rgba, _normal = atlas.plane_pictures(*self._passes(), 0, 3)
        self.assertGreater(rgba[1, 3, 0], 0.4)                   # one pixel outside: the edge's colour
        self.assertAlmostEqual(float(rgba[1, 3, 0]), float(rgba[3, 3, 0]), places=5)


class TreeLodLevels(unittest.TestCase):
    """forest_generator/tree_lods.py: which levels plant the LOD build."""

    def test_only_a_named_level_plants_the_lod_build(self):
        from forest_generator import tree_lods
        self.assertTrue(tree_lods.plants_lods("Lvl_Forest_1000m"))
        self.assertFalse(tree_lods.plants_lods("Lvl_Forest_200m"))
        self.assertFalse(tree_lods.plants_lods(None))            # a caller with no level

    def test_every_planted_tree_has_a_lod_build_to_plant(self):
        from forest_generator import tree_lods
        from forest_generator.tree_placement import DEFAULT_TREE_SPECS
        built = {f"{job.path}.{job.asset_name}" for job in jobs.TREES}
        for spec in DEFAULT_TREE_SPECS:
            path = tree_lods.lod_mesh_path(spec.mesh_path)
            self.assertIn(path, built, spec.name)
            self.assertEqual(tree_lods.lod_mesh_path(path), path)


if __name__ == "__main__":
    unittest.main()
