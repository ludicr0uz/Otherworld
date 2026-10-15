"""The blood splatter flipbook (combat/blood_sprite_image.py) and the size a
pellet's zone picks (combat/blood_sprite_consts.py), in plain Python: the
atlas is the shape the material reads, it blooms and then goes, and the head
splats largest, a limb least.
"""

import struct
import unittest
import zlib

import _paths  # noqa: F401

from combat import blood_sprite_consts as C
from combat import blood_sprite_image as I


class Flipbook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = I.draw_frames()

    def test_frame_count_and_cell(self):
        self.assertEqual(len(self.frames), C.SPLAT_FRAMES)
        self.assertEqual(C.SPLAT_FRAMES, C.SPLAT_GRID * C.SPLAT_GRID)
        for frame in self.frames:
            self.assertEqual(len(frame), C.SPLAT_CELL)
            self.assertEqual(len(frame[0]), C.SPLAT_CELL)

    def test_blooms_then_goes(self):
        cover = [I.coverage(f) for f in self.frames]
        peak = cover.index(max(cover))
        self.assertGreater(max(cover), 0.08, cover)
        self.assertLess(cover[0], max(cover) / 4, cover)
        self.assertEqual(cover[-1], 0.0, "the last frame must be empty: the actor dies on it")
        self.assertTrue(all(a <= b + 1e-9 for a, b in zip(cover[:peak], cover[1:peak + 1])),
                        f"grows to its peak: {cover}")
        self.assertTrue(all(a >= b - 1e-9 for a, b in zip(cover[peak:], cover[peak + 1:])),
                        f"then only shrinks: {cover}")

    def test_hold_frame_is_the_fullest(self):
        cover = [I.coverage(f) for f in self.frames]
        self.assertEqual(cover[C.SPLAT_HOLD_FRAME], max(cover), cover)

    def test_seeded(self):
        self.assertEqual(I.atlas_rgba(I.draw_frames()), I.atlas_rgba(self.frames))

    def test_png(self):
        png = I.png_bytes(*I.atlas_rgba(self.frames))
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        width, height, depth, colour = struct.unpack(">IIBB", png[16:26])
        size = C.SPLAT_CELL * C.SPLAT_GRID
        self.assertEqual((width, height, depth, colour), (size, size, 8, 6))
        start = png.index(b"IDAT") + 4
        length = struct.unpack(">I", png[start - 8:start - 4])[0]
        raw = zlib.decompress(png[start:start + length])
        self.assertEqual(len(raw), size * (size * 4 + 1))

    def test_frame_order(self):
        """Frame k at column k % GRID, row k // GRID, as the material reads it."""
        w, _h, rgba = I.atlas_rgba(self.frames)
        k = 5
        x = (k % C.SPLAT_GRID) * C.SPLAT_CELL + C.SPLAT_CELL // 2
        y = (k // C.SPLAT_GRID) * C.SPLAT_CELL + C.SPLAT_CELL // 2
        alpha = rgba[(y * w + x) * 4 + 3]
        self.assertEqual(alpha, int(round(self.frames[k][C.SPLAT_CELL // 2][C.SPLAT_CELL // 2][1]
                                          * 255.0)))


class ZoneSize(unittest.TestCase):
    def test_head_chest_limb(self):
        head = C.splat_scale(True, 1.75)
        chest = C.splat_scale(False, 1.0)
        limb = C.splat_scale(False, 0.75)
        self.assertGreater(head, chest)
        self.assertGreater(chest, limb)
        self.assertAlmostEqual(head, C.SPLAT_HEAD_CM / C.PLANE_CM)
        self.assertAlmostEqual(limb, C.SPLAT_LIMB_CM / C.PLANE_CM)

    def test_head_wins_over_worth(self):
        self.assertEqual(C.splat_scale(True, 0.5), C.splat_scale(True, 1.0))


if __name__ == "__main__":
    unittest.main()
