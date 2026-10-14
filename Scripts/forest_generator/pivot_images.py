"""The two image files the grass patch's pivot textures are imported from
(forest_generator/grass_patch.py). Pure Python with no third-party module:
the editor's Python has no numpy or Pillow.

    write_exr   RGBA half floats, uncompressed: the pivots and the packed
                indices, which must come through bit for bit
    write_png   RGBA 8 bits: the axes and lengths, as the pack's texture holds
                them

``pixels`` is a list of rows, top row first, each a list of (r, g, b, a).
"""

import struct
import zlib


def _attribute(name, kind, value):
    return name.encode() + b"\0" + kind.encode() + b"\0" + struct.pack("<i", len(value)) + value


def write_exr(path, pixels):
    """A scanline OpenEXR file of half-float R, G, B and A, no compression."""
    high, wide = len(pixels), len(pixels[0])
    channels = b"".join(c.encode() + b"\0" + struct.pack("<iB3xii", 1, 0, 1, 1)
                        for c in "ABGR") + b"\0"
    box = struct.pack("<iiii", 0, 0, wide - 1, high - 1)
    header = (b"\x76\x2f\x31\x01" + struct.pack("<i", 2)
              + _attribute("channels", "chlist", channels)
              + _attribute("compression", "compression", b"\0")
              + _attribute("dataWindow", "box2i", box)
              + _attribute("displayWindow", "box2i", box)
              + _attribute("lineOrder", "lineOrder", b"\0")
              + _attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0))
              + _attribute("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
              + _attribute("screenWindowWidth", "float", struct.pack("<f", 1.0))
              + b"\0")
    lines = []
    for y, row in enumerate(pixels):
        data = b"".join(struct.pack(f"<{wide}e", *(px[c] for px in row)) for c in (3, 2, 1, 0))
        lines.append(struct.pack("<ii", y, len(data)) + data)
    offset = len(header) + 8 * high
    table = b""
    for line in lines:
        table += struct.pack("<Q", offset)
        offset += len(line)
    with open(path, "wb") as fh:
        fh.write(header + table + b"".join(lines))


def _chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def write_png(path, pixels):
    """An 8-bit RGBA PNG; each channel 0-1, rounded."""
    high, wide = len(pixels), len(pixels[0])
    raw = b"".join(b"\0" + bytes(max(0, min(255, round(c * 255.0)))
                                 for px in row for c in px) for row in pixels)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n"
                 + _chunk(b"IHDR", struct.pack(">IIBBBBB", wide, high, 8, 6, 0, 0, 0))
                 + _chunk(b"IDAT", zlib.compress(raw, 9))
                 + _chunk(b"IEND", b""))
