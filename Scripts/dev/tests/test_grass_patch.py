"""The grass patch's numbers (forest_generator/grass_patch.py) and the image
files its pivot textures come from (forest_generator/pivot_images.py): the
LOD chain's triangles, the bands, and the Pivot Painter 2 texels moved with
each copy."""

import math
import os
import struct
import tempfile
import unittest
import zlib

import _paths  # noqa: F401

from forest_generator import grass_patch as P
from forest_generator.pivot_images import write_exr, write_png
from forest_generator.undergrowth_meshes import GRASS_02_09, GRASS_PATCH


class Lods(unittest.TestCase):
    def test_lod0_is_at_most_twice_the_clump_and_the_last_is_the_clump_s_last(self):
        tris = P.lod_triangles()
        self.assertEqual(tris, [3766, 1883, 807, 269])
        self.assertLessEqual(tris[0], 2 * GRASS_02_09.lod0_triangles)
        self.assertEqual(tris[-1], P.SOURCE_LOD_TRIANGLES[-1])
        self.assertEqual(tris[0], GRASS_PATCH.lod0_triangles)
        self.assertEqual(len(tris), GRASS_PATCH.lods)

    def test_nothing_near_is_stretched(self):
        self.assertTrue(all(p.width == 1.0 for p in P.LODS[0].placements + P.LODS[1].placements))
        self.assertTrue(all(p.width >= 1.0 for p in P.PLACEMENTS))

    def test_the_lods_come_in_order(self):
        far = [lod.from_m for lod in P.LODS]
        self.assertEqual(far, sorted(far))
        sizes = P.screen_sizes(65.0)
        self.assertEqual(sizes[0], 2.0)
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        # The screen size it leaves a LOD at is where it is P x R / d.
        self.assertAlmostEqual(sizes[1], 1.78 * 65.0 / (P.LODS[1].from_m * 100.0))

    def test_the_paths_are_the_record_s(self):
        for path in (P.MESH, P.MATERIAL, P.PIVOT_TEXTURE, P.AXIS_TEXTURE):
            self.assertIn(path, GRASS_PATCH.packages)
        self.assertEqual(P.SOURCE, GRASS_02_09.mesh)


class Bands(unittest.TestCase):
    def test_each_placement_has_its_band(self):
        self.assertEqual(len(P.PLACEMENTS), len(set(P.PLACEMENTS)))
        self.assertEqual(P.texture_size(), (89, 2 * len(P.PLACEMENTS)))
        for i, p in enumerate(P.PLACEMENTS):
            scale, offset = P.uv_scale_and_offset(p)
            self.assertEqual(P.band(p), i)
            # The clump's rows, v in 0-1, land in rows 2i and 2i+1.
            for v, row in ((0.25, 0), (0.75, 1)):
                moved = v * scale + offset
                self.assertEqual(int(moved * P.texture_size()[1]), 2 * i + row)


class Texels(unittest.TestCase):
    def test_an_index_packs_and_unpacks(self):
        for index in (0, 1, 177, 178, 1957):
            self.assertEqual(P.unpack_index(P.pack_index(index)), index)
        # 0 is stored as the half float with the bits 1024: 2 ** -14.
        self.assertEqual(P.pack_index(0), 2.0 ** -14)

    def test_a_pivot_moves_with_its_copy(self):
        x, y, z = P.move_point(P.Placement(90.0, 40.0, -10.0), (10.0, 0.0, 3.0))
        self.assertAlmostEqual(x, 40.0, places=4)
        self.assertAlmostEqual(y, 0.0, places=4)
        self.assertEqual(z, 3.0)

    def test_a_pivot_s_parent_moves_into_its_band(self):
        for p in P.PLACEMENTS:
            packed = P.move_pivot(p, (0.0, 0.0, 0.0, P.pack_index(7)))[3]
            self.assertEqual(P.unpack_index(packed), 7 + 178 * P.band(p))

    def test_an_axis_turns_and_its_length_widens(self):
        up = (0.5, 0.5, 1.0, 0.01)
        self.assertEqual(P.move_axis(P.Placement(47.0, 3.0, 4.0, 2.4), up), up)
        side = (1.0, 0.5, 0.5, 0.01)
        r, g, b, a = P.move_axis(P.Placement(90.0, 0.0, 0.0, 2.0), side)
        self.assertAlmostEqual(r, 0.5, places=6)
        self.assertAlmostEqual(g, 1.0, places=6)
        self.assertAlmostEqual(b, 0.5, places=6)
        self.assertAlmostEqual(a, 0.02, places=6)

    def test_a_point_turns_then_moves(self):
        x, y, z = P.move_point(P.Placement(180.0, 5.0, 0.0, 1.0), (1.0, 2.0, 3.0))
        self.assertAlmostEqual(x, 4.0)
        self.assertAlmostEqual(y, -2.0)
        self.assertEqual(z, 3.0)
        ring = [math.hypot(p.x_cm, p.y_cm) for p in P.DENSE[1:]]
        self.assertTrue(all(abs(r - 40.0) < 1e-6 for r in ring))


class Images(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.pixels = [[(0.25, 0.5, 1.0, 0.75), (0.0, 1.0, 0.0, 1.0)],
                       [(1.0, 0.0, 0.5, 0.0), (0.5, 0.5, 0.5, 0.5)]]

    def tearDown(self):
        self.dir.cleanup()

    def test_the_png_holds_the_pixels(self):
        path = os.path.join(self.dir.name, "t.png")
        write_png(path, self.pixels)
        data = open(path, "rb").read()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        wide, high, depth, kind = struct.unpack(">IIBB", data[16:26])
        self.assertEqual((wide, high, depth, kind), (2, 2, 8, 6))
        size = struct.unpack(">I", data[33:37])[0]
        raw = zlib.decompress(data[41:41 + size])
        self.assertEqual(raw[:9], bytes([0, 64, 128, 255, 191, 0, 255, 0, 255]))

    def test_the_exr_holds_the_half_floats_bit_for_bit(self):
        path = os.path.join(self.dir.name, "t.exr")
        pixels = [[(1.5, -2.0, 3.25, P.pack_index(177))]]
        write_exr(path, pixels)
        data = open(path, "rb").read()
        self.assertEqual(data[:4], b"\x76\x2f\x31\x01")
        # One line: its y, its size and A, B, G, R as halves.
        line = data[-(8 + 8):]
        y, size = struct.unpack("<ii", line[:8])
        self.assertEqual((y, size), (0, 8))
        a, b, g, r = struct.unpack("<4e", line[8:])
        self.assertEqual((r, g, b), (1.5, -2.0, 3.25))
        self.assertEqual(P.unpack_index(a), 177)


if __name__ == "__main__":
    unittest.main()
