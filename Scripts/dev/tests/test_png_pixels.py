"""probes/png_pixels.py: every PNG filter decodes, and two pictures compare."""

import os
import struct
import tempfile
import unittest
import zlib

import _paths  # noqa: F401

from probes import png_pixels


def _paeth(left, up, corner):
    p = left + up - corner
    pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
    return left if pa <= pb and pa <= pc else up if pb <= pc else corner


def _filtered(kind, row, above, bpp):
    out = bytearray()
    for i, v in enumerate(row):
        left = row[i - bpp] if i >= bpp else 0
        up = above[i]
        corner = above[i - bpp] if i >= bpp else 0
        sub = (0, left, up, (left + up) >> 1, _paeth(left, up, corner))[kind]
        out.append((v - sub) & 0xFF)
    return bytes(out)


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _write(path, width, rows, bpp, filters):
    colour = {3: 2, 4: 6}[bpp]
    raw, above = bytearray(), bytes(width * bpp)
    for y, row in enumerate(rows):
        kind = filters[y % len(filters)]
        raw.append(kind)
        raw += _filtered(kind, row, above, bpp)
        above = row
    packed = zlib.compress(bytes(raw))
    half = len(packed) // 2      # two IDAT chunks: they are one stream
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n"
                + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(rows), 8, colour, 0, 0, 0))
                + _chunk(b"IDAT", packed[:half]) + _chunk(b"IDAT", packed[half:])
                + _chunk(b"IEND", b""))


def _rows(width, height, bpp, seed=0):
    return [bytes((x * 7 + y * 13 + c * 29 + seed) % 256
                  for x in range(width) for c in range(bpp)) for y in range(height)]


class PngPixelsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def test_every_filter_reads_back(self):
        for bpp in (3, 4):
            rows = _rows(9, 10, bpp)
            _write(self.path("a.png"), 9, rows, bpp, filters=(0, 1, 2, 3, 4))
            width, height, got_bpp, got = png_pixels.read(self.path("a.png"))
            self.assertEqual((width, height, got_bpp), (9, 10, bpp))
            self.assertEqual([bytes(r) for r in got], rows)

    def test_not_a_png(self):
        with open(self.path("b.png"), "wb") as f:
            f.write(b"not a picture")
        with self.assertRaises(ValueError):
            png_pixels.read(self.path("b.png"))

    def test_changed_counts_pixels_and_boxes_them(self):
        rows = _rows(8, 6, 4)
        other = [bytearray(r) for r in rows]
        for x, y in ((2, 1), (5, 4)):
            other[y][x * 4 + 1] = (other[y][x * 4 + 1] + 100) % 256
        other[0][0] = (other[0][0] + 5) % 256           # under the threshold
        _write(self.path("a.png"), 8, rows, 4, filters=(4,))
        _write(self.path("b.png"), 8, [bytes(r) for r in other], 4, filters=(1,))
        a, b = png_pixels.read(self.path("a.png")), png_pixels.read(self.path("b.png"))
        self.assertEqual(png_pixels.changed(a, a), (0, None))
        self.assertEqual(png_pixels.changed(a, b), (2, (2, 1, 5, 4)))
        self.assertEqual(png_pixels.changed(a, b, box=(0, 0, 4, 5)), (1, (2, 1, 2, 1)))
        self.assertEqual(png_pixels.changed(a, b, box=(3, 2, 99, 99)), (1, (5, 4, 5, 4)))
        self.assertEqual(png_pixels.changed(a, b, threshold=4)[0], 3)

    def test_rgb_against_rgba(self):
        rgba = _rows(4, 3, 4)
        rgb = [bytes(v for i, v in enumerate(r) if i % 4 != 3) for r in rgba]
        _write(self.path("a.png"), 4, rgba, 4, filters=(0,))
        _write(self.path("b.png"), 4, rgb, 3, filters=(2,))
        self.assertEqual(png_pixels.changed(png_pixels.read(self.path("a.png")),
                                            png_pixels.read(self.path("b.png")))[0], 0)

    def test_sizes_must_match(self):
        _write(self.path("a.png"), 4, _rows(4, 3, 4), 4, filters=(0,))
        _write(self.path("b.png"), 5, _rows(5, 3, 4), 4, filters=(0,))
        with self.assertRaises(ValueError):
            png_pixels.changed(png_pixels.read(self.path("a.png")),
                               png_pixels.read(self.path("b.png")))


if __name__ == "__main__":
    unittest.main()
