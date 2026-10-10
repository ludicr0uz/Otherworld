"""Where the garments found in the forest go: pure Python, no unreal import,
deterministic for a seed -- the shape of survival/forage_placement.py, whose
spatial hash this reuses, so it can be tested without an editor.

Only the garments drawn on the body when worn are scattered (the jacket, the
pants, the boots: specs.GARMENTS rows with a `worn`), in turn, so a level
with three or more has each. Anywhere on the map, as a canteen is, but not
inside a trunk, not on the forage and not at the player start (the test row
lies there). About one per hectare, and at least one, so the probes' 50 m
level has a garment to find.
"""

import math
import random

from clothing.specs import GARMENTS
from survival.forage_placement import _Grid

SCATTER_KINDS = tuple(g.display for g in GARMENTS if g.worn is not None)
GARMENTS_PER_HECTARE = 1.0
MAX_GARMENTS = 120
SCATTER_SEED = 11
EDGE_MARGIN_CM = 1500.0     # inside the terrain's edge
START_CLEAR_CM = 1200.0     # from the player start
MIN_SPACING_CM = 2000.0     # between two scattered garments
TRUNK_CLEAR_CM = 110.0      # the hoodie's sleeves are 97 cm across
AVOID_CLEAR_CM = 150.0      # from anything else lying there (the forage)
ATTEMPTS_PER_ITEM = 40


def garment_count(width_cm, depth_cm):
    hectares = (width_cm / 100.0) * (depth_cm / 100.0) / 10000.0
    return max(1, min(MAX_GARMENTS, round(GARMENTS_PER_HECTARE * hectares)))


def scatter_clothing(x_range, y_range, trunks, start_xy, avoid=(), seed=SCATTER_SEED):
    """Return [(display, x, y)], display one of SCATTER_KINDS.

    x_range/y_range are the terrain's (min, max) in cm; trunks and avoid are
    lists of (x, y); start_xy is the player start.
    """
    rng = random.Random(seed)
    width, depth = x_range[1] - x_range[0], y_range[1] - y_range[0]
    side = min(width, depth)
    # The margins and the spacing shrink on a small map, as the forage's do.
    margin = min(EDGE_MARGIN_CM, 0.1 * side)
    start_clear = min(START_CLEAR_CM, 0.12 * side)
    spacing = min(MIN_SPACING_CM, 0.2 * side)
    x0, x1 = x_range[0] + margin, x_range[1] - margin
    y0, y1 = y_range[0] + margin, y_range[1] - margin
    if x1 <= x0 or y1 <= y0:
        raise ValueError("terrain is smaller than twice the edge margin")
    count = garment_count(width, depth)

    trunk_grid, avoid_grid = _Grid(500.0), _Grid(500.0)
    for tx, ty in trunks:
        trunk_grid.add(tx, ty)
    for ax, ay in avoid:
        avoid_grid.add(ax, ay)
    placed_grid = _Grid(spacing)
    out = []
    for _ in range(count * ATTEMPTS_PER_ITEM):
        if len(out) >= count:
            break
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if math.hypot(x - start_xy[0], y - start_xy[1]) < start_clear:
            continue
        if (placed_grid.near(x, y, spacing) or trunk_grid.near(x, y, TRUNK_CLEAR_CM)
                or avoid_grid.near(x, y, AVOID_CLEAR_CM)):
            continue
        placed_grid.add(x, y)
        out.append((SCATTER_KINDS[len(out) % len(SCATTER_KINDS)], x, y))
    return out
