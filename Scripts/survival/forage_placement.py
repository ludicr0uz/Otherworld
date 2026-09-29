"""Where the forage goes: pure Python, no unreal import, deterministic for a
seed -- the same shape as forest_generator's placement modules, so it can be
reasoned about (and tested) without an editor.

    mushrooms  at the foot of a tree: a random trunk, then a random point in
               MUSHROOM_TRUNK_RING_CM around it. "In the forest" is taken
               literally -- mushrooms grow off roots, not in clearings.
    canteens   anywhere on the map, but not inside a trunk: dropped kit is
               where people walked, which is everywhere.

Both stay FORAGE_EDGE_MARGIN_CM inside the terrain, FORAGE_START_CLEAR_CM from
the player start and FORAGE_MIN_SPACING_CM from each other.
"""

import math
import random

from survival.tuning import (
    CANTEENS_PER_HECTARE, FORAGE_EDGE_MARGIN_CM, FORAGE_MIN_SPACING_CM,
    FORAGE_SEED, FORAGE_START_CLEAR_CM, MAX_CANTEENS, MAX_MUSHROOMS,
    MUSHROOM_TRUNK_RING_CM, MUSHROOMS_PER_HECTARE,
)

TRUNK_CLEAR_CM = 90.0      # a canteen is never closer than this to a trunk
ATTEMPTS_PER_ITEM = 40


class _Grid:
    """A spatial hash of points, for 'is anything within r of here'."""

    def __init__(self, cell):
        self.cell = cell
        self.cells = {}

    def _key(self, x, y):
        return (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))

    def add(self, x, y):
        self.cells.setdefault(self._key(x, y), []).append((x, y))

    def near(self, x, y, r):
        kx, ky = self._key(x, y)
        reach = int(math.ceil(r / self.cell))
        for ix in range(kx - reach, kx + reach + 1):
            for iy in range(ky - reach, ky + reach + 1):
                for px, py in self.cells.get((ix, iy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < r * r:
                        return True
        return False


def forage_counts(width_cm, depth_cm):
    hectares = (width_cm / 100.0) * (depth_cm / 100.0) / 10000.0
    return (min(MAX_MUSHROOMS, round(MUSHROOMS_PER_HECTARE * hectares)),
            min(MAX_CANTEENS, round(CANTEENS_PER_HECTARE * hectares)))


def scatter_forage(x_range, y_range, trunks, start_xy, seed=FORAGE_SEED):
    """Return [(kind, x, y)] with kind "Mushroom" or "Canteen".

    x_range/y_range are the terrain's (min, max) in cm; trunks is a list of
    (x, y) tree positions; start_xy is the player start.
    """
    rng = random.Random(seed)
    x0, x1 = x_range[0] + FORAGE_EDGE_MARGIN_CM, x_range[1] - FORAGE_EDGE_MARGIN_CM
    y0, y1 = y_range[0] + FORAGE_EDGE_MARGIN_CM, y_range[1] - FORAGE_EDGE_MARGIN_CM
    if x1 <= x0 or y1 <= y0:
        raise ValueError("terrain is smaller than twice the edge margin")
    n_mush, n_can = forage_counts(x_range[1] - x_range[0], y_range[1] - y_range[0])

    trunk_grid = _Grid(500.0)
    for tx, ty in trunks:
        trunk_grid.add(tx, ty)
    placed_grid = _Grid(max(FORAGE_MIN_SPACING_CM, 100.0))
    out = []

    def free(x, y, trunk_clear):
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        if math.hypot(x - start_xy[0], y - start_xy[1]) < FORAGE_START_CLEAR_CM:
            return False
        if placed_grid.near(x, y, FORAGE_MIN_SPACING_CM):
            return False
        return not trunk_grid.near(x, y, trunk_clear)

    def take(kind, x, y):
        placed_grid.add(x, y)
        out.append((kind, x, y))

    inner, outer = MUSHROOM_TRUNK_RING_CM
    for _ in range(n_mush * ATTEMPTS_PER_ITEM):
        if sum(1 for k, _x, _y in out if k == "Mushroom") >= n_mush:
            break
        if trunks:
            tx, ty = trunks[rng.randrange(len(trunks))]
            ang = rng.uniform(0.0, 2.0 * math.pi)
            r = rng.uniform(inner, outer)
            x, y = tx + r * math.cos(ang), ty + r * math.sin(ang)
            clear = inner * 0.8      # at the foot of its tree, not in another
        else:
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            clear = 0.0
        if free(x, y, clear):
            take("Mushroom", x, y)

    for _ in range(n_can * ATTEMPTS_PER_ITEM):
        if sum(1 for k, _x, _y in out if k == "Canteen") >= n_can:
            break
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if free(x, y, TRUNK_CLEAR_CM):
            take("Canteen", x, y)
    return out
