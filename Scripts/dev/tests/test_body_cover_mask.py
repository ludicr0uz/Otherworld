"""asset_pipeline/body_cover_mask.py: which skin each garment covers, and the
UV mask of it the body's material is cut by. Pure, so the rule is held here
without an editor.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import struct
import unittest
import zlib

import _paths  # noqa: F401

from asset_pipeline import body_cover_mask as M
from asset_pipeline.metahuman_paths import CLOTHING, COVER_PARTS


class Covers(unittest.TestCase):
    def test_over_the_skin_within_reach(self):
        self.assertTrue(M.covers(M.COVER_OUT_CM - 0.1, None))
        self.assertFalse(M.covers(M.COVER_OUT_CM + 0.1, None))

    def test_under_the_skin_only_close(self):
        self.assertTrue(M.covers(None, M.COVER_IN_CM - 0.1))
        self.assertFalse(M.covers(None, M.COVER_IN_CM + 0.1))

    def test_misses(self):
        self.assertFalse(M.covers(None, None))


class VertexBits(unittest.TestCase):
    def test_kept_skin_is_never_cut(self):
        hits = [[(0.5, None)], [(0.5, None)], [(0.5, None)]]
        self.assertEqual(M.vertex_bits([True], hits, [[0.0], [0.0], [0.0]]), [0])

    def test_every_garment_that_covers(self):
        hits = [[(1.0, None)], [(None, 1.0)], [(None, None)]]
        self.assertEqual(M.vertex_bits([False], hits, [[9.0], [9.0], [9.0]]), [0b011])

    def test_uncovered_cut_skin_goes_to_the_nearest(self):
        hits = [[(None, None)]] * 3
        self.assertEqual(M.vertex_bits([False], hits, [[5.0], [9.0], [2.0]]), [0b100])


class Triangles(unittest.TestCase):
    def test_any_corner_cuts_the_triangle(self):
        self.assertEqual(M.triangle_bits([(0, 1, 2), (1, 2, 3)], [1, 0, 0, 4]), [1, 4])


class Raster(unittest.TestCase):
    def test_tile_wraps_and_fills(self):
        # Two triangles over the whole of tile u 1..2: every texel set.
        quad = [((1.0, 0.0), (2.0, 0.0), (2.0, 1.0)), ((1.0, 0.0), (2.0, 1.0), (1.0, 1.0))]
        img = M.dilate(M.raster(quad, [1, 2], size=8), steps=1)
        self.assertTrue(all(b for row in img for b in row))
        self.assertEqual(img[7][0], 2)   # row 7 is v ~ 1, column 0 u ~ 1
        self.assertEqual(img[0][7], 1)

    def test_dilate_reaches_empty_texels_only(self):
        img = [[None, None, None], [None, 2, None], [None, None, 1]]
        out = M.dilate(img, steps=1)
        self.assertEqual(out[1][1], 2)
        self.assertEqual(out[1][2], 3)   # between the two: either part cuts it
        self.assertEqual(out[0][0], 0)   # two steps away: left whole


class Png(unittest.TestCase):
    def test_a_channel_per_part(self):
        data = M.png_rgb([[1, 2], [4, 0]])
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        w, h = struct.unpack(">II", data[16:24])
        self.assertEqual((w, h), (2, 2))
        idat = data.index(b"IDAT")
        (length,) = struct.unpack(">I", data[idat - 4:idat])
        raw = zlib.decompress(data[idat + 4:idat + 4 + length])
        self.assertEqual(raw, b"\0" + bytes([255, 0, 0, 0, 255, 0])
                         + b"\0" + bytes([0, 0, 255, 0, 0, 0]))


class Parts(unittest.TestCase):
    def test_one_channel_per_drawn_garment(self):
        self.assertEqual(set(COVER_PARTS), set(CLOTHING))
        self.assertLessEqual(len(COVER_PARTS), 3)


if __name__ == "__main__":
    unittest.main()
