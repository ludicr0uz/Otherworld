"""Where each grass type grows: one smooth noise field per type, and the mix
of types at a point read off them. Pure Python (no ``unreal``).

A level that plants several grass types (grass_look.GRASS_TYPES) does not
scatter them evenly: a walk through the forest crosses a stretch of one, a
stretch of another, and the seams between where both grow. Each type has its
own value-noise field over the map, the same everywhere for a seed; a type's
weight at a point is exp(SHARPNESS x its field) times its base weight, so the
type whose field is clearly highest owns the ground there and, where two or
three fields are close, they mix.

The fields are read on a 2.5 m grid, cached: a region is tens of metres
across, so the step cannot be seen, and the 1 km map's million clumps cost a
dictionary lookup each instead of fourteen noise samples.

    REGION_CM          lattice step of the broad field: a region is about
                       this across
    DETAIL_CM, _AMP    a second, finer octave, so the edges wander
    SHARPNESS          how hard the highest field wins: 20 makes a lead of
                       0.1 a 7-to-1 share. Measured over the 1 km map with
                       seven equal types (tests/test_grass_regions.py): one
                       type holds over 70% of the ground on 53% of it, none
                       holds half on 17% (the mixed seams), and each type
                       leads on 13-16% of the map
"""

import math

REGION_CM = 4000.0
DETAIL_CM = 1500.0
DETAIL_AMPLITUDE = 0.35
SHARPNESS = 20.0
SAMPLE_STEP_CM = 250.0


def _lattice(seed, ix, iy):
    """A value in [0, 1) for one lattice point; a fixed integer hash, so it
    does not change with Python's string hashing or version."""
    h = (ix * 0x8DA6B343 ^ iy * 0xD8163841 ^ seed * 0xCB1AB31F) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 0x2C1B3C6D) & 0xFFFFFFFF
    h ^= h >> 12
    h = (h * 0x297A2D39) & 0xFFFFFFFF
    h ^= h >> 15
    return h / 4294967296.0


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def value_noise(seed, x, y, step):
    """Smoothly interpolated lattice noise in [0, 1)."""
    fx, fy = x / step, y / step
    ix, iy = math.floor(fx), math.floor(fy)
    tx, ty = _smooth(fx - ix), _smooth(fy - iy)
    a = _lattice(seed, ix, iy)
    b = _lattice(seed, ix + 1, iy)
    c = _lattice(seed, ix, iy + 1)
    d = _lattice(seed, ix + 1, iy + 1)
    top = a + (b - a) * tx
    bottom = c + (d - c) * tx
    return top + (bottom - top) * ty


def field(seed, x, y):
    """One type's field at (x, y): the broad octave and the detail, in [0, 1)."""
    broad = value_noise(seed, x, y, REGION_CM)
    detail = value_noise(seed ^ 0x5BD1, x, y, DETAIL_CM)
    return (broad + DETAIL_AMPLITUDE * detail) / (1.0 + DETAIL_AMPLITUDE)


class RegionMix:
    """The share of each of ``len(base_weights)`` types at any point."""

    def __init__(self, seed, base_weights):
        self.seeds = [(seed * 7919 + 104729 * (i + 1)) & 0x7FFFFFFF
                      for i in range(len(base_weights))]
        self.base = list(base_weights)
        self._cache = {}

    def weights(self, x, y):
        """Unnormalised weights at (x, y), for random.choices."""
        key = (round(x / SAMPLE_STEP_CM), round(y / SAMPLE_STEP_CM))
        got = self._cache.get(key)
        if got is None:
            sx, sy = key[0] * SAMPLE_STEP_CM, key[1] * SAMPLE_STEP_CM
            fields = [field(s, sx, sy) for s in self.seeds]
            top = max(fields)
            got = [b * math.exp(SHARPNESS * (f - top))
                   for b, f in zip(self.base, fields)]
            self._cache[key] = got
        return got

    def shares(self, x, y):
        w = self.weights(x, y)
        total = sum(w)
        return [v / total for v in w]
