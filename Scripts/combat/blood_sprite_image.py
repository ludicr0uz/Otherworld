"""The blood splatter flipbook, drawn in plain Python (no editor): a seeded
splat that blooms out of its middle, throws droplets and streaks, then
breaks up to nothing, as SPLAT_FRAMES cells of one RGBA atlas. blood_sprite.py
writes it as a PNG and imports it as T_BloodSprite.

RGB is a shade, not a colour (thick blood darker, the rim lighter); the
material multiplies it by M_Blood's colour, so the colour is stated once
(materials.BLOOD_BASE_COLOUR). Alpha is the splat's outline, read as an
opacity mask. Frame k sits at column k % GRID, row k // GRID, row 0 on top.

Seeded, so the atlas is the same bytes every build, and the unit tests
(dev/tests/test_blood_sprite.py) can hold its shape: it grows, then goes.
"""

import math
import random
import struct
import zlib

from combat.blood_sprite_consts import (
    SPLAT_CELL, SPLAT_FRAMES, SPLAT_GRID, SPLAT_GROW, SPLAT_SEED,
)

_CORE_BLOBS = 7
_DROPLETS = 22
_NOISE_GRID = 12
_EDGE = 0.12          # how soft the alpha's edge is, in field units


def _layout(rng, cell):
    """The splat's pieces at full bloom, in px from the cell's middle."""
    core = []
    for _ in range(_CORE_BLOBS):
        a, d = rng.uniform(0.0, 2.0 * math.pi), rng.uniform(0.0, 0.08 * cell)
        core.append((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.08, 0.14) * cell))
    drops = []
    for _ in range(_DROPLETS):
        a = rng.uniform(0.0, 2.0 * math.pi)
        drops.append((math.cos(a), math.sin(a), rng.uniform(0.22, 0.45) * cell,
                      rng.uniform(0.014, 0.04) * cell, rng.random() < 0.6))
    noise = [[rng.random() for _ in range(_NOISE_GRID + 1)] for _ in range(_NOISE_GRID + 1)]
    return core, drops, noise


def _stamp(field, cell, cx, cy, r, weight=1.0):
    """Add a smooth bump of radius ``r`` at (cx, cy) (from the middle)."""
    if r <= 0.3:
        return
    mid = cell / 2.0
    x0, x1 = max(0, int(mid + cx - r)), min(cell - 1, int(mid + cx + r) + 1)
    y0, y1 = max(0, int(mid + cy - r)), min(cell - 1, int(mid + cy + r) + 1)
    inv = 1.0 / (r * r)
    for y in range(y0, y1 + 1):
        dy = y + 0.5 - mid - cy
        row = field[y]
        for x in range(x0, x1 + 1):
            dx = x + 0.5 - mid - cx
            q = 1.0 - (dx * dx + dy * dy) * inv
            if q > 0.0:
                row[x] += weight * q * q * 2.0


def _noise_at(noise, cell, x, y):
    gx, gy = x / cell * _NOISE_GRID, y / cell * _NOISE_GRID
    ix, iy = min(int(gx), _NOISE_GRID - 1), min(int(gy), _NOISE_GRID - 1)
    fx, fy = gx - ix, gy - iy
    top = noise[iy][ix] * (1 - fx) + noise[iy][ix + 1] * fx
    bottom = noise[iy + 1][ix] * (1 - fx) + noise[iy + 1][ix + 1] * fx
    return top * (1 - fy) + bottom * fy


def frame_phases(t):
    """(grow, erode) at the flipbook's time ``t`` in [0, 1]: the bloom eases
    out to full by SPLAT_GROW, and only then does the break-up begin."""
    g = min(t / SPLAT_GROW, 1.0)
    grow = 1.0 - (1.0 - g) ** 3
    erode = max(0.0, (t - SPLAT_GROW) / (1.0 - SPLAT_GROW))
    return grow, erode


def draw_frame(layout, t, cell=SPLAT_CELL):
    """One cell: rows of (shade, alpha) pairs, each 0..1."""
    core, drops, noise = layout
    grow, erode = frame_phases(t)
    field = [[0.0] * cell for _ in range(cell)]
    for cx, cy, r in core:
        k = 0.5 + 0.5 * grow
        _stamp(field, cell, cx * k, cy * k, r * (0.35 + 0.65 * grow))
    for dx, dy, dist, r, streak in drops:
        reach = dist * grow
        _stamp(field, cell, dx * reach, dy * reach, r * (1.0 - 0.3 * grow))
        if streak:
            # Stamps close enough to overlap into one tapering streak.
            steps = min(40, max(3, int(reach * 0.65 / max(r * 0.25, 0.5))))
            for i in range(steps):
                f = (i + 1) / (steps + 1)
                along = reach * (0.35 + 0.65 * f)
                _stamp(field, cell, dx * along, dy * along, r * (0.4 + 0.5 * f), 0.8)
    # The break-up: a texel goes once the erosion passes what it keeps by,
    # its noise and how thick the blood is there, so the thin rim and the
    # droplets go first and the middle last, in ragged holes.
    rows = []
    for y in range(cell):
        row = []
        for x in range(cell):
            f = field[y][x]
            a = (min(f, 1.0) - 0.3) / _EDGE
            keep = 0.4 * _noise_at(noise, cell, x, y) + 0.6 * min(f / 3.0, 1.0)
            keep = (keep - 0.25) / 0.7       # spread over 0..1
            a = min(a, (keep - 1.1 * erode + 0.05) / 0.08)
            alpha = 0.0 if a <= 0.0 else (1.0 if a >= 1.0 else a)
            shade = 1.0 - 0.45 * min(f / 2.0, 1.0)
            row.append((shade, alpha))
        rows.append(row)
    return rows


def draw_frames(seed=SPLAT_SEED, cell=SPLAT_CELL, frames=SPLAT_FRAMES):
    layout = _layout(random.Random(seed), cell)
    return [draw_frame(layout, k / (frames - 1), cell) for k in range(frames)]


def coverage(frame):
    """The share of a cell's texels the mask keeps (alpha over a half)."""
    kept = sum(1 for row in frame for _shade, a in row if a > 0.5)
    return kept / float(len(frame) * len(frame[0]))


def atlas_rgba(frames, grid=SPLAT_GRID):
    """The frames laid into one (width, height, RGBA bytes) atlas."""
    cell = len(frames[0])
    size = cell * grid
    data = bytearray(size * size * 4)
    for k, frame in enumerate(frames):
        ox, oy = (k % grid) * cell, (k // grid) * cell
        for y, row in enumerate(frame):
            at = ((oy + y) * size + ox) * 4
            for shade, alpha in row:
                v = int(round(shade * 255.0))
                data[at:at + 4] = bytes((v, v, v, int(round(alpha * 255.0))))
                at += 4
    return size, size, bytes(data)


def _chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def png_bytes(width, height, rgba):
    """An 8-bit RGBA PNG of ``rgba`` (rows top to bottom)."""
    stride = width * 4
    raw = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 6))
            + _chunk(b"IEND", b""))


def splat_png():
    """The whole flipbook as PNG bytes."""
    return png_bytes(*atlas_rgba(draw_frames()))
