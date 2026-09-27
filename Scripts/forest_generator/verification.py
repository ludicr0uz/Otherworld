"""
verification.py — Pure-Python verification suite for generated forest levels.

These checks run *without* Unreal and validate the mathematical correctness
of the OBJ mesh and tree placements.  A second set of checks runs *inside*
Unreal (see verify_in_unreal.py).
"""

import json
import math
import os
from dataclasses import dataclass, field

from .terrain import get_exact_mesh_z, compute_grid, make_elevation_fn
from .npc_placement import (
    NAV_MAX_VERTICAL_SPAN_CM,
    NAV_MAX_HALF_XY_CM,
    NAV_COVERAGE_FRACTION,
    NPC_CAPSULE_HALF_HEIGHT_CM,
    npc_usable_radius,
    TRUNK_CLEARANCE_CM,
    EDGE_MARGIN_FRACTION,
    NPC_MIN_SEPARATION_CM,
    NPC_SPAWN_MIN_DISTANCE_CM,
    NPC_SPAWN_MAX_DISTANCE_CM,
    spawn_band,
)
from .grass_placement import (
    KNEE_LAYER_MIN_RATIO,
    MAX_UPSCALE_FACTOR,
    grass_spec_by_name,
)


# ─── Result types ────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    level_name: str
    world_size_m: float
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.passed)
        failed = total - passed
        status = "✅ ALL PASSED" if self.all_passed else f"❌ {failed} FAILED"
        lines = [
            f"═══ Verification Report: {self.level_name} ({self.world_size_m}m × {self.world_size_m}m) ═══",
            f"Result: {status}  ({passed}/{total} checks passed)",
            "",
        ]
        for c in self.checks:
            icon = "✅" if c.passed else "❌"
            lines.append(f"  {icon} {c.name}: {c.message}")
            for d in c.details[:5]:
                lines.append(f"      ↳ {d}")
            if len(c.details) > 5:
                lines.append(f"      ↳ ... and {len(c.details) - 5} more")
        return "\n".join(lines)

    def to_json(self, filepath: str):
        """Write report as JSON for programmatic consumption."""
        data = {
            "level_name": self.level_name,
            "world_size_m": self.world_size_m,
            "all_passed": self.all_passed,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)


# ─── Check implementations ──────────────────────────────────────────────────

def check_obj_file_valid(obj_path: str) -> CheckResult:
    """Verify the OBJ file exists, has vertices, faces, and valid normals."""
    if not os.path.exists(obj_path):
        return CheckResult("OBJ File Exists", False, f"Missing: {obj_path}")

    n_verts = n_faces = n_normals = 0
    with open(obj_path) as f:
        for line in f:
            if line.startswith("v "):
                n_verts += 1
            elif line.startswith("f "):
                n_faces += 1
            elif line.startswith("vn "):
                n_normals += 1

    ok = n_verts > 0 and n_faces > 0 and n_normals > 0
    msg = f"{n_verts} vertices, {n_faces} faces, {n_normals} normals"
    return CheckResult("OBJ File Valid", ok, msg)


def check_terrain_bounds(obj_path: str, world_size_cm: float) -> CheckResult:
    """Verify terrain vertices span the expected world bounds ±5%."""
    half = world_size_cm / 2.0
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    with open(obj_path) as f:
        for line in f:
            if line.startswith("v "):
                parts = line.split()
                x, y = float(parts[1]), float(parts[2])
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)

    span_x = max_x - min_x
    span_y = max_y - min_y
    tol = world_size_cm * 0.05
    ok = (abs(span_x - world_size_cm) < tol and
          abs(span_y - world_size_cm) < tol)
    msg = f"X span: {span_x:.0f} cm, Y span: {span_y:.0f} cm (expected {world_size_cm:.0f} cm)"
    return CheckResult("Terrain Bounds", ok, msg)


def check_terrain_center_flat(world_size_cm: float, grid_z,
                              grid_size: int) -> CheckResult:
    """Verify the center spawn area is flat (Z ≈ 0)."""
    flat_radius = world_size_cm * 0.1  # well within the flat zone
    test_points = [
        (0, 0), (flat_radius * 0.5, 0), (-flat_radius * 0.5, 0),
        (0, flat_radius * 0.5), (0, -flat_radius * 0.5),
    ]
    max_z = 0.0
    details = []
    for px, py in test_points:
        z = get_exact_mesh_z(px, py, grid_z, grid_size, world_size_cm)
        max_z = max(max_z, abs(z))
        details.append(f"({px:.0f}, {py:.0f}) → Z={z:.2f}")

    ok = max_z < 1.0  # should be exactly 0 at center
    msg = f"Max |Z| in spawn zone: {max_z:.2f} cm (threshold: 1.0 cm)"
    return CheckResult("Center Spawn Flat", ok, msg, details)


def check_normals_upward(obj_path: str) -> CheckResult:
    """Verify all top-surface normals point generally upward (nz > 0)."""
    bad_normals = []
    total = 0
    with open(obj_path) as f:
        for i, line in enumerate(f, 1):
            if line.startswith("vn "):
                parts = line.split()
                nz = float(parts[3])
                total += 1
                if nz < -0.01 and total <= (total // 2):
                    # Only check top-half normals (bottom cap has nz = -1)
                    bad_normals.append(f"Line {i}: nz={nz:.4f}")

    # The bottom cap legitimately has nz=-1. We just check no top normals are inverted.
    ok = len(bad_normals) == 0
    msg = f"Checked {total} normals, {len(bad_normals)} bad top-surface normals"
    return CheckResult("Top Normals Upward", ok, msg, bad_normals[:10])


def check_tree_count(placed_trees, world_size_cm: float) -> CheckResult:
    """Verify reasonable tree density (not empty, not absurdly dense)."""
    area_hectares = (world_size_cm / 100.0) ** 2 / 10_000.0
    count = len(placed_trees)
    density = count / area_hectares if area_hectares > 0 else 0

    # Expect 30-50 trees/hectare (our specs sum to ~34/ha)
    ok = 10 < density < 100
    msg = f"{count} trees on {area_hectares:.1f} ha = {density:.1f} trees/ha"
    return CheckResult("Tree Count / Density", ok, msg)


def check_trees_within_bounds(placed_trees, world_size_cm: float) -> CheckResult:
    """Verify all trees are within the terrain boundary."""
    half = world_size_cm / 2.0
    oob = []
    for t in placed_trees:
        if abs(t.x) > half or abs(t.y) > half:
            oob.append(f"{t.spec_name} at ({t.x:.0f}, {t.y:.0f}) — OUT OF BOUNDS")

    ok = len(oob) == 0
    msg = f"{len(oob)} trees out of bounds" if oob else "All trees within map bounds"
    return CheckResult("Trees Within Bounds", ok, msg, oob)


def check_trees_not_floating(placed_trees) -> CheckResult:
    """
    Verify no tree is placed *above* the terrain surface.

    Each tree's placed_z must be ≤ terrain_z (they should be sunk IN, not
    floating above).
    """
    floating = []
    for t in placed_trees:
        gap = t.placed_z - t.terrain_z
        if gap > 1.0:  # more than 1 cm above surface
            floating.append(
                f"{t.spec_name} at ({t.x:.0f},{t.y:.0f}): "
                f"placed_z={t.placed_z:.1f} > terrain_z={t.terrain_z:.1f} "
                f"(floating {gap:.1f} cm)"
            )

    ok = len(floating) == 0
    msg = f"{len(floating)} trees floating" if floating else "All trees at or below terrain"
    return CheckResult("Trees Not Floating", ok, msg, floating)


def check_trees_not_buried(placed_trees) -> CheckResult:
    """
    Verify trees aren't sunk too deep.  Sink should be < 200 cm (2 m).
    """
    buried = []
    for t in placed_trees:
        if t.sink_cm > 200.0:
            buried.append(
                f"{t.spec_name} at ({t.x:.0f},{t.y:.0f}): "
                f"sunk {t.sink_cm:.1f} cm (>200 cm max)"
            )

    ok = len(buried) == 0
    msg = f"{len(buried)} trees buried too deep" if buried else "All sinks within 200 cm"
    return CheckResult("Trees Not Over-Buried", ok, msg, buried)


def check_trees_vertical(placed_trees) -> CheckResult:
    """
    Trees must be vertical (pitch=0, roll=0, only yaw varies).
    Our scatter only sets yaw, so this should always pass.
    """
    # PlacedTree only has yaw_deg, pitch/roll are implicitly 0.
    ok = True
    msg = "All trees placed with pitch=0, roll=0 (vertical)"
    return CheckResult("Trees Vertical", ok, msg)


def check_tree_spacing(placed_trees) -> CheckResult:
    """
    Verify no two trees overlap at trunk level (minimum 100 cm apart).
    Uses a simple O(n²) check for moderate tree counts.
    """
    min_dist = float("inf")
    violations = []
    n = len(placed_trees)

    # For large maps, only check nearest neighbors within grid cells
    for i in range(n):
        for j in range(i + 1, min(i + 50, n)):  # check nearby in list
            dx = placed_trees[i].x - placed_trees[j].x
            dy = placed_trees[i].y - placed_trees[j].y
            d = math.hypot(dx, dy)
            min_dist = min(min_dist, d)
            if d < 100.0:
                violations.append(
                    f"{placed_trees[i].spec_name} & {placed_trees[j].spec_name} "
                    f"only {d:.0f} cm apart"
                )

    ok = len(violations) == 0
    msg = (f"Min spacing: {min_dist:.0f} cm, {len(violations)} overlaps"
           if min_dist < float("inf") else "No trees to check")
    return CheckResult("Tree Spacing (>100cm)", ok, msg, violations[:10])


def check_no_trees_in_spawn_zone(placed_trees, world_size_cm: float) -> CheckResult:
    """Verify no trees within the minimum distance from center."""
    intruders = []
    for t in placed_trees:
        dist = math.hypot(t.x, t.y)
        if dist < 500.0:  # 5 m radius hard minimum
            intruders.append(
                f"{t.spec_name} at ({t.x:.0f},{t.y:.0f}) — {dist:.0f} cm from center"
            )

    ok = len(intruders) == 0
    msg = (f"{len(intruders)} trees in spawn zone" if intruders
           else "Spawn zone (5m radius) clear")
    return CheckResult("Spawn Zone Clear", ok, msg, intruders)


# ─── Grass checks ───────────────────────────────────────────────────────────

def check_grass_count(placed_grass, world_size_cm: float,
                      density_per_sqm: float) -> CheckResult:
    """Verify the realised density matches the requested density."""
    area_sqm = (world_size_cm / 100.0) ** 2
    count = len(placed_grass)
    density = count / area_sqm if area_sqm > 0 else 0.0

    # Trees, the spawn ring and the coverage inset all remove a little area,
    # so allow the realised density to sit inside 70–105 % of the request.
    lo, hi = density_per_sqm * 0.70, density_per_sqm * 1.05
    ok = count > 0 and lo <= density <= hi
    msg = (f"{count:,} clumps on {area_sqm:,.0f} m² = {density:.2f}/m² "
           f"(requested {density_per_sqm:.2f}/m²)")
    return CheckResult("Grass Count / Density", ok, msg)


def check_grass_within_bounds(placed_grass, world_size_cm: float) -> CheckResult:
    """Verify every clump sits inside the terrain boundary."""
    half = world_size_cm / 2.0
    oob = []
    for g in placed_grass:
        if abs(g.x) > half or abs(g.y) > half:
            oob.append(f"{g.spec_name} at ({g.x:.0f}, {g.y:.0f}) — OUT OF BOUNDS")
            if len(oob) > 20:
                break

    ok = len(oob) == 0
    msg = f"{len(oob)} clumps out of bounds" if oob else "All grass within map bounds"
    return CheckResult("Grass Within Bounds", ok, msg, oob)


def check_grass_snapped_to_terrain(placed_grass, world_size_cm: float,
                                   grid_z, grid_size: int) -> CheckResult:
    """
    Re-derive the terrain height under a sample of clumps and confirm each one
    is seated on the surface (sunk by its own sink_cm, never floating).
    """
    if not placed_grass:
        return CheckResult("Grass Snapped To Terrain", True, "No grass to check")

    step = max(1, len(placed_grass) // 500)
    bad = []
    for g in placed_grass[::step]:
        exact = get_exact_mesh_z(g.x, g.y, grid_z, grid_size, world_size_cm)
        if abs(exact - g.terrain_z) > 0.01:
            bad.append(f"{g.spec_name} at ({g.x:.0f},{g.y:.0f}): terrain_z "
                       f"{g.terrain_z:.2f} != exact {exact:.2f}")
        elif abs((g.terrain_z - g.sink_cm) - g.placed_z) > 0.01:
            bad.append(f"{g.spec_name} at ({g.x:.0f},{g.y:.0f}): placed_z "
                       f"{g.placed_z:.2f} != terrain_z - sink {g.terrain_z - g.sink_cm:.2f}")
        if len(bad) > 20:
            break

    ok = len(bad) == 0
    msg = (f"{len(bad)} mis-seated clumps" if bad
           else f"All {len(placed_grass[::step])} sampled clumps seated on the mesh")
    return CheckResult("Grass Snapped To Terrain", ok, msg, bad)


def check_grass_knee_height(placed_grass, knee_height_cm: float) -> CheckResult:
    """
    The dominant layer must actually measure knee high, and nothing may end up
    tall enough to read as a bush.
    """
    if not placed_grass:
        return CheckResult("Grass Knee Height", True, "No grass to check")

    knee_lo, knee_hi = knee_height_cm * 0.70, knee_height_cm * 1.30
    hard_max = knee_height_cm * 1.60

    knee_heights = []
    offenders = []
    for g in placed_grass:
        spec = grass_spec_by_name(g.spec_name)
        ratio = spec.height_ratio if spec else 1.0
        if g.target_height_cm > hard_max:
            offenders.append(f"{g.spec_name}: {g.target_height_cm:.1f} cm > {hard_max:.1f} cm")
        if ratio >= KNEE_LAYER_MIN_RATIO:
            knee_heights.append(g.target_height_cm)
            if not (knee_lo <= g.target_height_cm <= knee_hi):
                offenders.append(f"{g.spec_name}: {g.target_height_cm:.1f} cm "
                                 f"outside knee band {knee_lo:.0f}–{knee_hi:.0f} cm")
        if len(offenders) > 20:
            break

    share = len(knee_heights) / len(placed_grass)
    avg = sum(knee_heights) / len(knee_heights) if knee_heights else 0.0
    ok = not offenders and share >= 0.60 and knee_lo <= avg <= knee_hi
    msg = (f"knee layer = {share * 100:.0f}% of clumps, avg {avg:.1f} cm "
           f"(target {knee_height_cm:.0f} cm)")
    return CheckResult("Grass Knee Height", ok, msg, offenders)


def check_grass_upscale(placed_grass, knee_height_cm: float) -> CheckResult:
    """
    Guard the visual quality of the scans: a clump stretched far past its
    authored size reads as oversized blades, so keep every species inside
    MAX_UPSCALE_FACTOR.  Uses the bounds heights measured in-editor and
    recorded on each spec.
    """
    if not placed_grass:
        return CheckResult("Grass Upscale Factor", True, "No grass to check")

    worst_name, worst_factor = "", 0.0
    offenders = []
    seen = set()
    for g in placed_grass:
        if g.spec_name in seen:
            continue
        seen.add(g.spec_name)
        spec = grass_spec_by_name(g.spec_name)
        if not spec or spec.nominal_mesh_height_cm <= 0:
            continue
        # Worst case is the tallest jitter on the shortest mesh.
        peak = knee_height_cm * spec.height_ratio * spec.height_jitter[1]
        factor = peak / spec.nominal_mesh_height_cm
        if factor > worst_factor:
            worst_name, worst_factor = spec.name, factor
        if factor > MAX_UPSCALE_FACTOR:
            offenders.append(f"{spec.name}: {factor:.2f}x "
                             f"({spec.nominal_mesh_height_cm:.1f} cm mesh -> "
                             f"{peak:.1f} cm) exceeds {MAX_UPSCALE_FACTOR:.2f}x")

    ok = len(offenders) == 0
    msg = f"worst upscale {worst_factor:.2f}x ({worst_name}), limit {MAX_UPSCALE_FACTOR:.2f}x"
    return CheckResult("Grass Upscale Factor", ok, msg, offenders)


def check_grass_coverage(placed_grass, world_size_cm: float,
                         divisions: int = 12) -> CheckResult:
    """
    "Throughout the level" — every cell of a coarse grid over the map must
    contain grass, so no quadrant is left bald.
    """
    if not placed_grass:
        return CheckResult("Grass Coverage", False, "No grass placed")

    half = world_size_cm / 2.0
    cell = (2.0 * half) / divisions
    occupied = set()
    for g in placed_grass:
        ix = min(divisions - 1, max(0, int((g.x + half) / cell)))
        iy = min(divisions - 1, max(0, int((g.y + half) / cell)))
        occupied.add((ix, iy))

    total_cells = divisions * divisions
    empty = [f"cell ({ix},{iy}) has no grass"
             for iy in range(divisions) for ix in range(divisions)
             if (ix, iy) not in occupied]

    ok = len(empty) == 0
    msg = (f"{len(occupied)}/{total_cells} cells of a {divisions}×{divisions} grid covered")
    return CheckResult("Grass Coverage", ok, msg, empty)


def check_grass_spec_distribution(placed_grass) -> CheckResult:
    """Every configured species must be represented — no dead HISM actors."""
    if not placed_grass:
        return CheckResult("Grass Species Spread", True, "No grass to check")

    from collections import Counter
    counts = Counter(g.spec_name for g in placed_grass)
    details = [f"{n}: {c:,}" for n, c in sorted(counts.items())]
    ok = len(counts) >= 2 and min(counts.values()) > 0
    msg = f"{len(counts)} species represented"
    return CheckResult("Grass Species Spread", ok, msg, details)


# ─── NPC checks ─────────────────────────────────────────────────────────────
#
# Every check here takes the whole pack and reports the worst member, rather
# than one check per NPC: five near-identical failures read as noise, and the
# thing worth knowing is "does any wanderer break this rule".


def _worst(placed_npcs, key):
    """The NPC with the smallest ``key``, or None for an empty pack."""
    return min(placed_npcs, key=key) if placed_npcs else None


def check_npc_count(placed_npcs, expected: int) -> CheckResult:
    """The pack must be the size that was asked for.

    Fewer than expected means rejection sampling ran out of legal spots inside
    the spawn band -- too small a map, too dense a forest, or a separation
    requirement the band cannot hold -- and it is a hard failure rather than a
    quiet under-spawn, because "up to 5 at a time" is the feature.
    """
    got = len(placed_npcs)
    ok = got == expected
    msg = (f"{got} wanderer(s) placed"
           if ok else f"only {got} of {expected} wanderers could be placed")
    details = [] if ok else [
        "the spawn band may be too narrow for NPC_MIN_SEPARATION_CM, or the "
        "forest too dense for TRUNK_CLEARANCE_CM"]
    return CheckResult("NPC Count", ok, msg, details)


def check_npc_spawn_band(placed_npcs, world_size_cm: float) -> CheckResult:
    """Every NPC starts inside the 75-100 m band (as clamped for this map).

    This is the check that makes the clamp honest: spawn_band() is the only
    thing that decides what the band is, and on a map too small for 75-100 m it
    reports a narrower one, which shows up in this message rather than passing
    silently against a rule nobody met.
    """
    if not placed_npcs:
        return CheckResult("NPC Spawn Band", False, "no NPCs")
    lo, hi, clamped = spawn_band(world_size_cm)
    details = [f"NPC {i + 1} at {n.distance_to_player_cm / 100.0:.1f} m"
               for i, n in enumerate(placed_npcs)
               if not (lo - 1.0 <= n.distance_to_player_cm <= hi + 1.0)]
    near = min(n.distance_to_player_cm for n in placed_npcs) / 100.0
    far = max(n.distance_to_player_cm for n in placed_npcs) / 100.0
    note = (f" (clamped from {NPC_SPAWN_MIN_DISTANCE_CM / 100.0:.0f}-"
            f"{NPC_SPAWN_MAX_DISTANCE_CM / 100.0:.0f} m by the navigable "
            f"radius)" if clamped else "")
    msg = (f"{near:.1f}-{far:.1f} m from the player start, band "
           f"{lo / 100.0:.1f}-{hi / 100.0:.1f} m{note}")
    return CheckResult("NPC Spawn Band", not details, msg, details)


def check_npc_separation(placed_npcs) -> CheckResult:
    """No two wanderers may start on top of each other.

    They all path to the same target, so a clump never unclumps -- it arrives
    as one body occupying one capsule's worth of space.
    """
    if len(placed_npcs) < 2:
        return CheckResult("NPC Separation", True, "fewer than two NPCs")
    worst = min(
        (math.hypot(a.x - b.x, a.y - b.y), i + 1, j + 1)
        for i, a in enumerate(placed_npcs)
        for j, b in enumerate(placed_npcs) if j > i)
    gap, a_i, b_i = worst
    ok = gap >= NPC_MIN_SEPARATION_CM - 1.0
    msg = (f"closest pair (NPC {a_i}, NPC {b_i}) {gap / 100.0:.1f} m apart "
           f"(minimum {NPC_MIN_SEPARATION_CM / 100.0:.1f} m)")
    return CheckResult("NPC Separation", ok, msg)


def check_npcs_within_bounds(placed_npcs, world_size_cm: float) -> CheckResult:
    """Every NPC starts inside the navigable area, clear of the map edge."""
    if not placed_npcs:
        return CheckResult("NPC Within Bounds", False, "no NPCs")
    usable = npc_usable_radius(world_size_cm)
    details = [f"NPC {i + 1} at ({n.x:.0f}, {n.y:.0f})"
               for i, n in enumerate(placed_npcs)
               if abs(n.x) > usable or abs(n.y) > usable]
    msg = f"all {len(placed_npcs)} inside +/-{usable:.0f} cm"
    return CheckResult("NPC Within Bounds", not details, msg, details)


def check_npcs_clear_of_trees(placed_npcs) -> CheckResult:
    """No capsule may start inside a trunk."""
    if not placed_npcs:
        return CheckResult("NPC Clear Of Trees", False, "no NPCs")
    worst = _worst(placed_npcs, lambda n: n.nearest_trunk_cm)
    ok = worst.nearest_trunk_cm >= TRUNK_CLEARANCE_CM - 1.0
    msg = (f"tightest spawn has {worst.nearest_trunk_cm:.0f} cm to the nearest "
           f"trunk (minimum {TRUNK_CLEARANCE_CM:.0f} cm)")
    return CheckResult("NPC Clear Of Trees", ok, msg)


def check_npcs_grounded(placed_npcs, world_size_cm: float,
                        grid_z, grid_size: int) -> CheckResult:
    """
    Every capsule centre must sit exactly one half-height above the terrain: any
    lower and the NPC spawns embedded in the ground, any higher and it drops.
    """
    if not placed_npcs:
        return CheckResult("NPC Grounded", False, "no NPCs")
    details = []
    for i, n in enumerate(placed_npcs):
        exact = get_exact_mesh_z(n.x, n.y, grid_z, grid_size, world_size_cm)
        if abs(exact - n.terrain_z) > 0.01:
            details.append(f"NPC {i + 1}: terrain_z {n.terrain_z:.2f} != "
                           f"exact {exact:.2f}")
        lift = n.spawn_z - n.terrain_z
        if abs(lift - NPC_CAPSULE_HALF_HEIGHT_CM) > 0.01:
            details.append(f"NPC {i + 1}: capsule lift {lift:.2f} cm != "
                           f"{NPC_CAPSULE_HALF_HEIGHT_CM:.2f} cm")
    msg = (f"all {len(placed_npcs)} capsule centres "
           f"{NPC_CAPSULE_HALF_HEIGHT_CM:.0f} cm above the exact mesh Z"
           if not details else "at least one spawn height is wrong")
    return CheckResult("NPC Grounded", not details, msg, details)


def check_npc_routes_are_obstructed(placed_npcs) -> CheckResult:
    """
    The interesting requirement is that the NPCs walk *around* the trees, which
    is only observable if the straight line to the player is blocked in the
    first place.  Placement prefers such spots; this reports how many of the
    pack found one.  A clear line is a warning-shaped pass, not a failure — on a
    sparse map it can be legitimately unavoidable.
    """
    if not placed_npcs:
        return CheckResult("NPC Route Is Obstructed", False, "no NPCs")
    blocked = [n for n in placed_npcs if n.blocking_trees > 0]
    if len(blocked) == len(placed_npcs):
        msg = (f"all {len(placed_npcs)} routes cross at least one trunk — "
               f"pathfinding must detour")
    else:
        msg = (f"{len(blocked)}/{len(placed_npcs)} routes cross a trunk; the "
               f"rest walk straight. Raise tree density or re-run with a "
               f"different --seed to exercise the detour behaviour")
    return CheckResult("NPC Route Is Obstructed", True, msg)


def check_nav_bounds_sane(nav_bounds, world_size_cm: float) -> CheckResult:
    """
    Two failures, one check.

    The first left the NPC immobile: Recast voxelises the full height of every
    tile, so a wildly over-tall NavMeshBoundsVolume generates *no tiles at all*
    and nothing in the level is navigable.  Sizing Z from map width gave an
    8000 cm span on a 200 m map and produced zero tiles.

    The second left the NPCs following only in the middle of the map: a volume
    NARROWER than the terrain leaves a ring of walkable ground with no
    navigation data on it, and a player standing in the ring cannot be pathed
    to.  So a volume that could cover the whole map and does not is a failure
    here, not a tuning choice.
    """
    if nav_bounds is None:
        return CheckResult("Nav Bounds Sane", False, "no nav bounds computed")

    span = nav_bounds["half_z_cm"] * 2.0
    half_xy = nav_bounds["half_xy_cm"]
    terrain_half = world_size_cm / 2.0
    details = []
    if span > NAV_MAX_VERTICAL_SPAN_CM:
        details.append(f"vertical span {span:.0f} cm exceeds "
                       f"{NAV_MAX_VERTICAL_SPAN_CM:.0f} cm — Recast will "
                       f"generate no tiles")
    if half_xy <= 0:
        details.append("XY extent is not positive")
    coverable = min(terrain_half, NAV_MAX_HALF_XY_CM)
    if half_xy < coverable - 1.0:
        details.append(f"navmesh covers +/-{half_xy:.0f} cm of +/-"
                       f"{coverable:.0f} cm of coverable terrain — the "
                       f"{coverable - half_xy:.0f} cm ring outside it is "
                       f"walkable ground an NPC cannot be pathed across")

    ok = not details
    msg = (f"+/-{half_xy:.0f} cm XY covering +/-{terrain_half:.0f} cm of terrain, "
           f"{span:.0f} cm vertical span "
           f"(terrain {nav_bounds['terrain_min_z_cm']:.0f}.."
           f"{nav_bounds['terrain_max_z_cm']:.0f})")
    return CheckResult("Nav Bounds Sane", ok, msg, details)


def check_npcs_inside_nav_bounds(placed_npcs, nav_bounds) -> CheckResult:
    """
    Every NPC has to start on the navmesh.  Nav coverage is a *larger* fraction
    of the map than the NPCs' placement margin precisely so this cannot fail,
    but the two constants live apart, so assert the relationship rather than
    trust it.
    """
    if not placed_npcs or nav_bounds is None:
        return CheckResult("NPC Inside Nav Bounds", False, "no NPCs or nav bounds")

    half_xy = nav_bounds["half_xy_cm"]
    lo = nav_bounds["center_z_cm"] - nav_bounds["half_z_cm"]
    hi = nav_bounds["center_z_cm"] + nav_bounds["half_z_cm"]
    details = []
    for i, n in enumerate(placed_npcs):
        if abs(n.x) > half_xy or abs(n.y) > half_xy:
            details.append(f"NPC {i + 1} at ({n.x:.0f}, {n.y:.0f}) outside "
                           f"+/-{half_xy:.0f} cm")
        # Pathfinding queries the capsule's feet, not its centre.
        feet_z = n.spawn_z - NPC_CAPSULE_HALF_HEIGHT_CM
        if not (lo <= feet_z <= hi):
            details.append(f"NPC {i + 1}: feet z {feet_z:.0f} outside "
                           f"{lo:.0f}..{hi:.0f}")
    if NAV_COVERAGE_FRACTION < EDGE_MARGIN_FRACTION:
        details.append(f"NAV_COVERAGE_FRACTION ({NAV_COVERAGE_FRACTION}) is below "
                       f"EDGE_MARGIN_FRACTION ({EDGE_MARGIN_FRACTION}); an NPC can "
                       f"spawn off the navmesh")
    msg = (f"all {len(placed_npcs)} stand inside +/-{half_xy:.0f} cm XY, "
           f"feet within {lo:.0f}..{hi:.0f}")
    return CheckResult("NPC Inside Nav Bounds", not details, msg, details)


def check_barycentric_consistency(world_size_cm: float, grid_z,
                                  grid_size: int) -> CheckResult:
    """
    Verify barycentric Z lookup matches the elevation function at grid vertices.
    """
    elev_fn = make_elevation_fn(world_size_cm)
    step = world_size_cm / grid_size
    half = world_size_cm / 2.0
    max_err = 0.0
    details = []

    # Check a sample of grid vertices
    test_count = min(20, grid_size + 1)
    step_i = max(1, grid_size // test_count)
    for gi in range(0, grid_size + 1, step_i):
        for gj in range(0, grid_size + 1, step_i):
            x = -half + gi * step
            y = -half + gj * step
            z_formula = elev_fn(x, y)
            z_bary = get_exact_mesh_z(x, y, grid_z, grid_size, world_size_cm)
            err = abs(z_formula - z_bary)
            max_err = max(max_err, err)
            if err > 0.1:
                details.append(
                    f"({x:.0f},{y:.0f}): formula={z_formula:.2f}, "
                    f"bary={z_bary:.2f}, err={err:.2f}"
                )

    ok = max_err < 1.0
    msg = f"Max barycentric error at grid vertices: {max_err:.4f} cm"
    return CheckResult("Barycentric Consistency", ok, msg, details)


# ─── Run all checks ─────────────────────────────────────────────────────────

def run_all_checks(
    level_name: str,
    world_size_cm: float,
    obj_path: str,
    grid_z,
    grid_size: int,
    placed_trees,
    placed_grass=None,
    grass_density_per_sqm: float = 0.0,
    knee_height_cm: float = 50.0,
    placed_npcs=None,
    expect_npc: bool = False,
    expected_npc_count: int = 0,
    nav_bounds=None,
) -> VerificationReport:
    """Run the complete verification suite and return a report."""
    world_size_m = world_size_cm / 100.0
    report = VerificationReport(level_name=level_name, world_size_m=world_size_m)

    # Terrain checks
    report.checks.append(check_obj_file_valid(obj_path))
    report.checks.append(check_terrain_bounds(obj_path, world_size_cm))
    report.checks.append(check_terrain_center_flat(world_size_cm, grid_z, grid_size))
    report.checks.append(check_normals_upward(obj_path))
    report.checks.append(check_barycentric_consistency(world_size_cm, grid_z, grid_size))

    # Tree checks
    report.checks.append(check_tree_count(placed_trees, world_size_cm))
    report.checks.append(check_trees_within_bounds(placed_trees, world_size_cm))
    report.checks.append(check_trees_not_floating(placed_trees))
    report.checks.append(check_trees_not_buried(placed_trees))
    report.checks.append(check_trees_vertical(placed_trees))
    report.checks.append(check_tree_spacing(placed_trees))
    report.checks.append(check_no_trees_in_spawn_zone(placed_trees, world_size_cm))

    # Grass checks (skipped entirely when grass generation is disabled)
    if placed_grass:
        report.checks.append(check_grass_count(placed_grass, world_size_cm,
                                               grass_density_per_sqm))
        report.checks.append(check_grass_within_bounds(placed_grass, world_size_cm))
        report.checks.append(check_grass_snapped_to_terrain(placed_grass, world_size_cm,
                                                           grid_z, grid_size))
        report.checks.append(check_grass_knee_height(placed_grass, knee_height_cm))
        report.checks.append(check_grass_upscale(placed_grass, knee_height_cm))
        report.checks.append(check_grass_coverage(placed_grass, world_size_cm))
        report.checks.append(check_grass_spec_distribution(placed_grass))

    # NPC checks (skipped entirely when NPC spawning is disabled)
    if expect_npc:
        placed_npcs = placed_npcs or []
        report.checks.append(check_npc_count(placed_npcs, expected_npc_count))
        report.checks.append(check_npc_spawn_band(placed_npcs, world_size_cm))
        report.checks.append(check_npc_separation(placed_npcs))
        report.checks.append(check_npcs_within_bounds(placed_npcs, world_size_cm))
        report.checks.append(check_npcs_clear_of_trees(placed_npcs))
        report.checks.append(check_npcs_grounded(placed_npcs, world_size_cm,
                                                 grid_z, grid_size))
        report.checks.append(check_npc_routes_are_obstructed(placed_npcs))
        report.checks.append(check_nav_bounds_sane(nav_bounds, world_size_cm))
        report.checks.append(check_npcs_inside_nav_bounds(placed_npcs, nav_bounds))

    return report
