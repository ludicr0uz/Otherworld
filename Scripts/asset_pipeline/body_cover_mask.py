"""body_cover_mask -- which skin of the whole MetaHuman body each garment
covers, and the UV mask that says so.  Pure Python (no ``unreal``): the
editor side, body_cover.py, measures the meshes and hands the numbers here
(tests: dev/tests/test_body_cover_mask.py).

Where the skin may be cut is Epic's: Taro's own body (BODY_MESH) is the
whole body with the skin under his hoodie, jeans and shoes removed, vertex
for vertex (its 10490 vertices lie on the whole body's to 0.01 cm, and its
triangles are the whole body's with all three corners kept).  Which garment
covers a removed vertex is measured: a ray from it along its normal that
meets the garment within COVER_OUT_CM (the garment over the skin), or
against its normal within COVER_IN_CM (a tight garment under the skin's
surface, the jeans).  A removed vertex no ray assigns goes to the nearest
garment.  A vertex may be covered by two (the hoodie's hem over the jeans'
waist): it is hidden while either is worn.

The mask is one texel per UV point of the body, a channel per part
(COVER_PARTS order), flat over each triangle: a triangle is cut for a part
when any of its corners is covered by it, as Taro's mesh drops it.  Texels
no triangle reaches take their neighbours' value (``dilate``), so the
filtering at an island's edge never reads the background.
"""

import struct
import zlib

COVER_OUT_CM = 8.0
COVER_IN_CM = 3.0
KEPT_CM = 0.01
MASK_SIZE = 1024
DILATE_TEXELS = 4


def covers(out_hit, in_hit):
    """Does one garment cover a vertex: ray distances along and against its
    normal, None for a miss."""
    return ((out_hit is not None and 0.0 <= out_hit < COVER_OUT_CM)
            or (in_hit is not None and 0.0 <= in_hit < COVER_IN_CM))


def vertex_bits(kept, hits, nearest):
    """A bit per part for each vertex: 0 for a vertex Taro's body keeps.
    ``kept[v]`` bool; ``hits[p][v]`` (out, in) ray distances or None;
    ``nearest[p][v]`` the distance to garment p, for the fallback."""
    parts = range(len(hits))
    bits = []
    for v, keep in enumerate(kept):
        if keep:
            bits.append(0)
            continue
        b = 0
        for p in parts:
            if covers(*hits[p][v]):
                b |= 1 << p
        if not b:
            b = 1 << min(parts, key=lambda p: nearest[p][v])
        bits.append(b)
    return bits


def triangle_bits(tris, bits):
    """A triangle is cut for every part any corner is covered by."""
    return [bits[a] | bits[b] | bits[c] for a, b, c in tris]


def raster(tri_uvs, tri_bits, size=MASK_SIZE):
    """``size``x``size`` texels of bits (None where no triangle reaches),
    row 0 at v = 0.  UVs are taken modulo 1 by tile (the body's lie in
    u 1..2), as a wrapping sampler reads them."""
    img = [[None] * size for _ in range(size)]
    for uvs, b in zip(tri_uvs, tri_bits):
        tile_u = min(int(u // 1) for u, _ in uvs)
        tile_v = min(int(v // 1) for _, v in uvs)
        pts = [((u - tile_u) * size - 0.5, (v - tile_v) * size - 0.5) for u, v in uvs]
        (ax, ay), (bx, by), (cx, cy) = pts
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        x0 = max(0, int(min(ax, bx, cx))); x1 = min(size - 1, int(max(ax, bx, cx)) + 1)
        y0 = max(0, int(min(ay, by, cy))); y1 = min(size - 1, int(max(ay, by, cy)) + 1)
        eps = -1e-6
        for y in range(y0, y1 + 1):
            row = img[y]
            for x in range(x0, x1 + 1):
                w0 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / den
                if w0 < eps:
                    continue
                w1 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / den
                if w1 < eps or 1.0 - w0 - w1 < eps:
                    continue
                # A texel two triangles share keeps every part either cuts.
                row[x] = b | (row[x] or 0)
    return img


def dilate(img, steps=DILATE_TEXELS):
    """Fill empty texels from their filled 4-neighbours, ``steps`` rings
    out; what stays empty is 0."""
    size = len(img)
    for _ in range(steps):
        grown = [row[:] for row in img]
        for y in range(size):
            for x in range(size):
                if img[y][x] is not None:
                    continue
                got = None
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < size and 0 <= ny < size and img[ny][nx] is not None:
                        got = img[ny][nx] | (got or 0)
                grown[y][x] = got
        img = grown
    return [[b or 0 for b in row] for row in img]


def png_rgb(img):
    """An 8-bit RGB PNG of the bits: bit p is channel p, 255 when set."""
    size = len(img)
    raw = b"".join(
        b"\0" + bytes(255 if (b >> ch) & 1 else 0 for b in row for ch in range(3))
        for row in img)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
