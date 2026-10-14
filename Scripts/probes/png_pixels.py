"""Reading a screenshot's pixels in a probe: the editor's Python has no image
library, and a picture is the only proof that something far off was drawn.

Pure Python (zlib alone), so the dev unit tests cover it. It reads what the
engine's ``shot`` writes and no more: 8 bits a channel, RGB or RGBA, not
interlaced.
"""

import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {2: 3, 6: 4}        # colour type -> bytes per pixel


def _unfilter(kind, line, above, bpp):
    """One scanline as stored -> its bytes (PNG's five filters)."""
    if kind == 0:
        return line
    out = bytearray(line)
    for i in range(len(out)):
        left = out[i - bpp] if i >= bpp else 0
        up = above[i]
        if kind == 1:
            add = left
        elif kind == 2:
            add = up
        elif kind == 3:
            add = (left + up) >> 1
        elif kind == 4:
            corner = above[i - bpp] if i >= bpp else 0
            p = left + up - corner
            pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
            add = left if pa <= pb and pa <= pc else up if pb <= pc else corner
        else:
            raise ValueError(f"PNG filter {kind}")
        out[i] = (out[i] + add) & 0xFF
    return out


def read(path):
    """``(width, height, bytes per pixel, rows)``: each row a bytes-like of
    width x bytes-per-pixel values, top row first."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != _SIGNATURE:
        raise ValueError(f"{path} is not a PNG")
    at, packed, header = 8, [], None
    while at < len(data):
        size, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + size]
        at += 12 + size
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            packed.append(body)
    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or colour not in _CHANNELS or interlace:
        raise ValueError(f"{path}: depth {depth}, colour type {colour}, "
                         f"interlace {interlace} is not read here")
    bpp = _CHANNELS[colour]
    raw, stride = zlib.decompress(b"".join(packed)), width * bpp
    rows, above = [], bytes(stride)
    for y in range(height):
        start = y * (stride + 1)
        above = _unfilter(raw[start], raw[start + 1:start + 1 + stride], above, bpp)
        rows.append(above)
    return width, height, bpp, rows


def changed(a, b, threshold=12, box=None):
    """How many pixels of two pictures of one size differ by more than
    ``threshold`` in red, green or blue, and the box they lie in
    (``(count, (left, top, right, bottom))``, the box None when none do).
    ``box`` (the same four, inclusive) keeps the count to a part of the frame."""
    wa, ha, bpa, rows_a = a
    wb, hb, bpb, rows_b = b
    if (wa, ha) != (wb, hb):
        raise ValueError(f"pictures of {wa}x{ha} and {wb}x{hb}")
    left, top, right, bottom = box or (0, 0, wa - 1, ha - 1)
    left, top, right, bottom = max(0, left), max(0, top), min(wa - 1, right), min(ha - 1, bottom)
    count, found = 0, None
    for y in range(top, bottom + 1):
        ra, rb = rows_a[y], rows_b[y]
        if ra == rb and bpa == bpb:
            continue
        for x in range(left, right + 1):
            i, j = x * bpa, x * bpb
            if (abs(ra[i] - rb[j]) > threshold or abs(ra[i + 1] - rb[j + 1]) > threshold
                    or abs(ra[i + 2] - rb[j + 2]) > threshold):
                count += 1
                found = ((x, y, x, y) if found is None else
                         (min(found[0], x), min(found[1], y), max(found[2], x),
                          max(found[3], y)))
    return count, found
