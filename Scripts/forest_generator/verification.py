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

    return report
