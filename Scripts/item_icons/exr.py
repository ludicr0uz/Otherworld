"""Read one channel of the EXR the editor exports from a float render target.

Only what that file is: scan lines, ZIP-compressed or not, HALF or FLOAT
channels, one part. Pillow reads no EXR, and this keeps the compose step to
Pillow and numpy. The depth pass is the one float pass there is (capture.py).
"""

import struct
import zlib

import numpy as np

MAGIC = 20000630
NO_COMPRESSION, ZIPS, ZIP = 0, 2, 3
LINES_PER_BLOCK = {NO_COMPRESSION: 1, ZIPS: 1, ZIP: 16}
PIXEL_TYPES = {1: np.dtype("<f2"), 2: np.dtype("<f4")}      # HALF, FLOAT


def _header(data):
    """The attributes as {name: bytes}, and the offset the header ends at."""
    if struct.unpack_from("<i", data, 0)[0] != MAGIC:
        raise ValueError("not an EXR")
    attrs, at = {}, 8
    while data[at] != 0:
        end = data.index(b"\0", at)
        name = data[at:end].decode()
        type_end = data.index(b"\0", end + 1)
        size = struct.unpack_from("<i", data, type_end + 1)[0]
        attrs[name] = data[type_end + 5:type_end + 5 + size]
        at = type_end + 5 + size
    return attrs, at + 1


def _channels(raw):
    """[(name, dtype)] in the order the file stores them (alphabetical)."""
    out, at = [], 0
    while raw[at] != 0:
        end = raw.index(b"\0", at)
        kind = struct.unpack_from("<i", raw, end + 1)[0]
        if kind not in PIXEL_TYPES:
            raise ValueError(f"EXR channel {raw[at:end].decode()} is neither half nor float")
        out.append((raw[at:end].decode(), PIXEL_TYPES[kind]))
        at = end + 17
    return out


def _unzip(chunk, raw_size):
    """A ZIP block: inflate, undo the byte delta, then the byte interleave."""
    if len(chunk) == raw_size:          # stored as it is: it did not shrink
        return chunk
    flat = np.frombuffer(zlib.decompress(chunk), dtype=np.uint8)
    flat = (np.cumsum(flat.astype(np.int64) - 128) + 128).astype(np.uint8)
    half = (len(flat) + 1) // 2
    out = np.empty(len(flat), dtype=np.uint8)
    out[0::2], out[1::2] = flat[:half], flat[half:]
    return out.tobytes()


def read_channel(path, channel):
    """The named channel as a float32 array, (height, width)."""
    with open(path, "rb") as fh:
        data = fh.read()
    attrs, at = _header(data)
    compression = attrs["compression"][0]
    if compression not in LINES_PER_BLOCK:
        raise ValueError(f"{path}: EXR compression {compression} is not read here")
    x0, y0, x1, y1 = struct.unpack("<4i", attrs["dataWindow"])
    width, height = x1 - x0 + 1, y1 - y0 + 1
    channels = _channels(attrs["channels"])
    if channel not in [n for n, _ in channels]:
        raise ValueError(f"{path}: no channel {channel}")
    line_bytes = sum(t.itemsize for _, t in channels) * width
    lines = LINES_PER_BLOCK[compression]
    out = np.empty((height, width), dtype=np.float32)
    for block in range(-(-height // lines)):
        offset = struct.unpack_from("<Q", data, at + 8 * block)[0]
        y, size = struct.unpack_from("<2i", data, offset)
        rows = min(lines, y1 - y + 1)
        raw = data[offset + 8:offset + 8 + size]
        if compression != NO_COMPRESSION:
            raw = _unzip(raw, rows * line_bytes)
        for row in range(rows):
            col = row * line_bytes
            for name, kind in channels:
                if name == channel:
                    out[y - y0 + row] = np.frombuffer(raw, dtype=kind, count=width, offset=col)
                col += kind.itemsize * width
    return out
