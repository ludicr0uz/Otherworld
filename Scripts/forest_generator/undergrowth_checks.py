"""Offline checks for the generated foliage meshes, the grass density tiers
and the bushes. Pure Python; run_all_checks (verification.py) calls these.

The in-editor half -- that the saved cells carry these tiers, tags, distances
and no collision -- is forest_import/grass.py's and bushes.py's verify_*.
"""

import math

from .bush_placement import (
    BUSH_SPAWN_CLEAR_CM, BUSH_TREE_CLEAR_CM, bush_spec_by_name)
from .foliage_meshes import (
    BUSH_RECIPES, BUSH_TRI_BUDGET, GRASS_RECIPES, GRASS_TRI_BUDGET, build)
from .grass_cells import GRASS_TIERS
from .grass_placement import KNEE_HEIGHT_CM, MAX_UPSCALE_FACTOR
from .terrain import get_exact_mesh_z
from .verification import CheckResult


def _tri_area2(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return math.sqrt(cx * cx + cy * cy + cz * cz)


def check_foliage_meshes() -> CheckResult:
    """Every generated mesh: inside its triangle budget, no degenerate
    triangles, unit normals, rooted at the origin, and the right size -- grass
    near knee height (so planting barely scales it), bushes waist to head."""
    problems, details = [], []
    for recipe in GRASS_RECIPES + BUSH_RECIPES:
        buf = build(recipe)
        is_grass = recipe in GRASS_RECIPES
        budget = GRASS_TRI_BUDGET if is_grass else BUSH_TRI_BUDGET
        (x0, y0, z0), (x1, y1, z1) = buf.bounds()
        details.append(f"{recipe.name}: {buf.triangle_count} tris, "
                       f"{z1:.0f} cm tall, {x1 - x0:.0f} cm wide")
        if buf.triangle_count > budget:
            problems.append(f"{recipe.name}: {buf.triangle_count} tris > {budget}")
        degenerate = sum(1 for t in buf.triangles
                         if _tri_area2(*(buf.vertices[i] for i in t)) < 1e-4)
        if degenerate:
            problems.append(f"{recipe.name}: {degenerate} degenerate triangles")
        bad_n = sum(1 for n in buf.normals
                    if abs(math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) - 1.0) > 1e-3)
        if bad_n:
            problems.append(f"{recipe.name}: {bad_n} non-unit normals")
        if z0 < -5.0 or abs((x0 + x1) / 2) > 15.0 or abs((y0 + y1) / 2) > 15.0:
            problems.append(f"{recipe.name}: pivot is not at the base centre")
        if is_grass:
            scale = KNEE_HEIGHT_CM / z1
            if not (1.0 / MAX_UPSCALE_FACTOR <= scale <= MAX_UPSCALE_FACTOR):
                problems.append(f"{recipe.name}: {z1:.0f} cm needs x{scale:.2f} "
                                f"to reach knee height")
        elif not (90.0 <= z1 <= 200.0):
            problems.append(f"{recipe.name}: {z1:.0f} cm is not bush height")
    return CheckResult("Foliage Meshes", not problems,
                       f"{len(GRASS_RECIPES)} grass patches, {len(BUSH_RECIPES)} "
                       f"bushes, within budget" if not problems
                       else f"{len(problems)} problems", problems + details)


def check_grass_tiers(placed_grass, world_size_cm, divisions=8) -> CheckResult:
    """Each density tier holds its share of the grass, and the Low tier on its
    own still covers the whole map -- Low is thinner, not patchy."""
    if not placed_grass:
        return CheckResult("Grass Density Tiers", True, "No grass to check")
    counts = [0] * len(GRASS_TIERS)
    half = world_size_cm / 2.0
    cell = 2.0 * half / divisions
    low_cells = set()
    for g in placed_grass:
        counts[g.tier] += 1
        if g.tier == 0:
            low_cells.add((min(divisions - 1, int((g.x + half) / cell)),
                           min(divisions - 1, int((g.y + half) / cell))))
    total = len(placed_grass)
    problems = []
    for i, (tier, n) in enumerate(zip(GRASS_TIERS, counts)):
        share = n / total
        if abs(share - tier.share) > 0.25 * tier.share:
            problems.append(f"tier {i}: {share:.1%} of grass, expected "
                            f"{tier.share:.0%}")
    if len(low_cells) < divisions * divisions:
        problems.append(f"Low tier covers {len(low_cells)}/{divisions ** 2} cells")
    msg = ", ".join(f"T{i} {n:,}" for i, n in enumerate(counts))
    return CheckResult("Grass Density Tiers", not problems, msg, problems)


def check_bushes(placed_bushes, placed_trees, world_size_cm, grid_z,
                 grid_size) -> CheckResult:
    """Bushes: a sane number, on the map, seated on the ground, clear of
    trunks and the spawn, and intermittent -- neither everywhere nor nowhere."""
    if not placed_bushes:
        return CheckResult("Bushes", False, "No bushes placed")
    half = world_size_cm / 2.0
    area_ha = (world_size_cm / 10000.0) ** 2
    per_ha = len(placed_bushes) / area_ha
    problems = []
    if not 30.0 <= per_ha <= 150.0:
        problems.append(f"{per_ha:.0f} bushes/ha outside 30-150")

    trunk_r2 = (BUSH_TREE_CLEAR_CM - 1.0) ** 2
    trees = [(t.x, t.y) for t in placed_trees or []]
    step = max(1, len(placed_bushes) // 400)
    for b in placed_bushes[::step]:
        if abs(b.x) > half or abs(b.y) > half:
            problems.append(f"{b.spec_name} at ({b.x:.0f},{b.y:.0f}) off the map")
        if b.x * b.x + b.y * b.y < BUSH_SPAWN_CLEAR_CM ** 2 - 1.0:
            problems.append(f"{b.spec_name} at ({b.x:.0f},{b.y:.0f}) in the spawn")
        exact = get_exact_mesh_z(b.x, b.y, grid_z, grid_size, world_size_cm)
        if abs(exact - b.terrain_z) > 0.01 or abs(b.terrain_z - b.sink_cm - b.placed_z) > 0.01:
            problems.append(f"{b.spec_name} at ({b.x:.0f},{b.y:.0f}) not seated")
        if any((b.x - tx) ** 2 + (b.y - ty) ** 2 < trunk_r2 for tx, ty in trees):
            problems.append(f"{b.spec_name} at ({b.x:.0f},{b.y:.0f}) in a trunk")
        if not bush_spec_by_name(b.spec_name):
            problems.append(f"unknown bush spec {b.spec_name}")
        if len(problems) > 20:
            break

    # Intermittent: the share of 10 m squares holding a bush.
    occupied = {(int((b.x + half) // 1000), int((b.y + half) // 1000))
                for b in placed_bushes}
    squares = (world_size_cm / 1000.0) ** 2
    share = len(occupied) / squares
    if not 0.05 <= share <= 0.60:
        problems.append(f"bushes in {share:.0%} of 10 m squares; want 5-60%")
    msg = (f"{len(placed_bushes):,} bushes ({per_ha:.0f}/ha) in {share:.0%} of "
           f"10 m squares")
    return CheckResult("Bushes", not problems, msg, problems)
