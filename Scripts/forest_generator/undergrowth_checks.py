"""Offline checks for the meshes the undergrowth is planted from, the grass
density tiers and the bushes. Pure Python; run_all_checks (verification.py) calls these.

The in-editor half -- that the saved cells carry these tiers, tags, distances
and no collision -- is forest_import/grass.py's and bushes.py's verify_*.
"""

from .bush_placement import (
    BUSH_SPAWN_CLEAR_CM, BUSH_TREE_CLEAR_CM, DEFAULT_BUSH_SPECS,
    bush_spec_by_name)
from .grass_cells import GRASS_TIERS
from .grass_placement import KNEE_HEIGHT_CM, MAX_UPSCALE_FACTOR
from .terrain import get_exact_mesh_z
from .undergrowth_meshes import BUSH_MESHES, GRASS_MESHES, UNDERGROWTH_MESHES
from .verification import CheckResult

# A planted bush, shortest to tallest: waist high to a head above the player.
BUSH_HEIGHT_CM = (90.0, 230.0)


def check_undergrowth_meshes() -> CheckResult:
    """The library meshes the grass and bushes are planted from
    (undergrowth_meshes.py): the grass near knee height, so planting barely
    scales it, and the bushes waist to above head at either end of their
    scale. The sizes are the recorded ones; the level verifier re-measures."""
    problems, details = [], []
    for mesh in UNDERGROWTH_MESHES:
        details.append(f"{mesh.name}: {mesh.lod0_triangles} tris in LOD0 of "
                       f"{mesh.lods}, {mesh.height_cm:.0f} cm tall, "
                       f"{mesh.width_cm:.0f} cm wide")
        if mesh.mesh not in mesh.packages:
            problems.append(f"{mesh.name}: its own package is not in its list")
    for mesh in GRASS_MESHES:
        scale = KNEE_HEIGHT_CM / mesh.height_cm
        if not (1.0 / MAX_UPSCALE_FACTOR <= scale <= MAX_UPSCALE_FACTOR):
            problems.append(f"{mesh.name}: {mesh.height_cm:.0f} cm needs "
                            f"x{scale:.2f} to reach knee height")
    planted = {s.mesh_path.split(".")[0]: s for s in DEFAULT_BUSH_SPECS}
    for mesh in BUSH_MESHES:
        spec = planted.get(mesh.mesh)
        if not spec:
            problems.append(f"{mesh.name}: no bush spec plants it")
            continue
        lo, hi = (mesh.height_cm * s for s in spec.scale_jitter)
        if lo < BUSH_HEIGHT_CM[0] or hi > BUSH_HEIGHT_CM[1]:
            problems.append(f"{mesh.name}: {lo:.0f}-{hi:.0f} cm is not bush height")
    return CheckResult("Undergrowth Meshes", not problems,
                       f"{len(GRASS_MESHES)} grass, {len(BUSH_MESHES)} bush, "
                       f"the right size" if not problems
                       else f"{len(problems)} problems", problems + details)


def check_grass_tiers(placed_grass, world_size_cm, tiers=GRASS_TIERS,
                      divisions=8) -> CheckResult:
    """Each of the level's density tiers holds its share of the grass, and the
    Low tier on its own still covers the whole map -- Low is thinner, not patchy."""
    if not placed_grass:
        return CheckResult("Grass Density Tiers", True, "No grass to check")
    counts = [0] * len(tiers)
    shares = [t.share / sum(t.share for t in tiers) for t in tiers]
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
    for i, (want, n) in enumerate(zip(shares, counts)):
        share = n / total
        if abs(share - want) > 0.25 * want:
            problems.append(f"tier {i}: {share:.1%} of grass, expected {want:.1%}")
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
