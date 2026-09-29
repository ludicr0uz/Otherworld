"""
grass_placement.py — Deterministic knee-high grass scattering.

Grass is scattered across the *entire* terrain using a jittered stratified grid
(even coverage, no clumps of empty map) with a patchiness term so the result
does not read as a regular lattice.  Every clump's Z comes from exact
barycentric interpolation on the terrain mesh, matching the tree pipeline.

Sitting on the ground
---------------------
Every clump is rotated to stand along the terrain NORMAL rather than straight
up.  This is not a refinement -- it is the difference between grass that is on
the ground and grass that is not.  Measured on the 200 m map this project
ships (Scripts/forest_generator/terrain.py, seed 42, 33x33 grid):

    slope under a grass clump   p50 16.6 deg   p90 28.3 deg   max 39.6 deg
    clumps on ground > 8 deg    74.3%
    downhill edge of a vertical
    clump, half-width 22 cm     p50 6.5 cm     p90 11.8 cm    max 18.2 cm

against a ``sink_cm`` of 3-4.  So on more than half the map a vertically
planted clump had one edge visibly hanging in the air, which is exactly what
it looked like.  The terrain is hills, not a plane; nothing on it should be
planted plumb.

``max_tilt_deg`` stays, and is now a perturbation ON TOP of the aligned pose
rather than the whole of the rotation -- the field still should not look
stamped, it just should not float.

Height handling
---------------
This module does *not* bake an absolute scale -- the mesh is the import
side's business, and the scans this was written for had no authored size at
all.  Each instance
carries a ``target_height_cm`` (what the clump should measure in world space)
plus independent height/width multipliers.  The generated Unreal script divides
``target_height_cm`` by the mesh's actual bounding-box height to obtain the
unit scale, which makes "knee high" true regardless of the asset's authored
size.
"""

import math
import random
from dataclasses import dataclass

from .foliage_meshes import (
    GRASS_PATCH_A, GRASS_PATCH_B, MI_GRASS, asset_path, mesh_height_cm)
from .grass_cells import GRASS_TIERS
from .terrain import get_exact_mesh_z


# ─── Configuration ───────────────────────────────────────────────────────────

# Knee height on an average adult character, in centimetres.
KNEE_HEIGHT_CM = 50.0


@dataclass
class GrassSpec:
    """Defines one category of grass clump to be instanced."""
    name: str                      # HISM actor label
    mesh_path: str                 # UE content path to StaticMesh
    material_paths: list[str]      # UE content paths to material slots
    weight: float                  # relative share of the total instance budget
    height_ratio: float = 1.0      # 1.0 == knee height, <1 == understory filler
    height_jitter: tuple[float, float] = (0.85, 1.20)
    width_jitter: tuple[float, float] = (0.90, 1.18)
    max_tilt_deg: float = 4.0      # random lean, keeps the field from looking stamped
    sink_cm: float = 4.0           # push the base below the surface at knee height
    # Authored height of the mesh (foliage_meshes.mesh_height_cm).  Only used
    # offline to flag excessive upscaling — the import script re-reads the
    # real bounds at plant time.
    nominal_mesh_height_cm: float = 0.0


# Two generated patch meshes (forest_generator/foliage_meshes.py), each a
# ~1.1 m disc of a few hundred opaque blades authored at knee height -- so
# planting scales them by 0.8-1.1 instead of stretching 15-30 cm scans by up to
# 3x. The patch itself is the thickness: one instance carries what took a
# dozen scanned clumps, so the field is dense at the instance count the scans
# used to be sparse at.
DEFAULT_GRASS_SPECS = [
    GrassSpec("HISM_Grass_Patch_A", asset_path(GRASS_PATCH_A), [MI_GRASS],
              weight=1.25, height_ratio=1.00, height_jitter=(0.85, 1.15),
              width_jitter=(0.85, 1.20), sink_cm=3.0,
              nominal_mesh_height_cm=mesh_height_cm(GRASS_PATCH_A)),
    GrassSpec("HISM_Grass_Patch_B", asset_path(GRASS_PATCH_B), [MI_GRASS],
              weight=0.75, height_ratio=1.00, height_jitter=(0.85, 1.15),
              width_jitter=(0.85, 1.20), sink_cm=3.0,
              nominal_mesh_height_cm=mesh_height_cm(GRASS_PATCH_B)),
]

# Upscaling a patch much past this starts to read as oversized blades.
MAX_UPSCALE_FACTOR = 2.4

# Specs whose height_ratio is at or above this count as the "knee" layer.
KNEE_LAYER_MIN_RATIO = 0.85

# Patches per m² of map with every tier drawn (Ultra); Low draws
# GRASS_TIERS[0].share of it. ~1.1 m² per patch, so ~1.2 layers of blades
# over the ground at Ultra and about half cover on Low.
DEFAULT_DENSITY_PER_SQM = 1.1
DEFAULT_PATCHINESS = 0.25       # 0 = perfectly even, ->1 = heavily clustered
SPAWN_CLEAR_RADIUS_CM = 150.0   # keep the PlayerStart from being submerged
TREE_CLEAR_RADIUS_CM = 90.0     # small bare ring at each trunk


# ─── Placement record ───────────────────────────────────────────────────────

@dataclass
class PlacedGrass:
    """One grass clump instance after placement."""
    spec_name: str
    x: float
    y: float
    terrain_z: float        # exact mesh Z at (x, y)
    placed_z: float         # final Z after sinking the base
    yaw_deg: float
    pitch_deg: float
    roll_deg: float
    height_scale: float     # multiplier on the spec's target height
    width_scale: float      # multiplier on the spec's target width
    target_height_cm: float # final intended world height of this clump
    sink_cm: float
    tier: int = 0           # grass_cells.GRASS_TIERS index


# ─── Scatter ─────────────────────────────────────────────────────────────────

# How far apart the two probes of the central difference sit when measuring the
# ground's slope.  The mesh this samples has 6 m triangles on a 200 m map, so
# anything much smaller than this just measures one facet and anything much
# larger smooths across a whole hill.  50 cm is under a clump's own footprint,
# which is the scale the clump has to sit flat at.
SLOPE_PROBE_CM = 25.0


def terrain_pose(x, y, yaw_deg, grid_z, grid_size, world_size_cm,
                 probe_cm: float = SLOPE_PROBE_CM):
    """The (pitch, roll) that stands a clump along the terrain normal at (x, y).

    ``yaw_deg`` has to be passed in rather than applied afterwards: an Unreal
    FRotator applies roll, then pitch, then YAW about the world Z, so spinning
    an already-tilted clump moves the direction it leans in.  Solving for pitch
    and roll in the yawed frame is what makes the two independent -- the clump
    can face any way and still lie flat.

    Derivation.  For a rotator (P, Y, R) Unreal's up vector is

        up = (-sinP cosY cosR + sinY sinR,
              -sinP sinY cosR - cosY sinR,
               cosP cosR)

    Rotating the wanted normal back by -Y reduces that to the Y = 0 case,
    where it inverts directly:

        n' = Rz(-Y) n      R = asin(-n'y)      P = asin(-n'x / cosR)

    ``check_grass_follows_terrain`` in verification.py asserts the result by
    reconstructing the up vector and comparing it to the normal, so this cannot
    silently drift.
    """
    zx = (get_exact_mesh_z(x + probe_cm, y, grid_z, grid_size, world_size_cm)
          - get_exact_mesh_z(x - probe_cm, y, grid_z, grid_size, world_size_cm)) / (2.0 * probe_cm)
    zy = (get_exact_mesh_z(x, y + probe_cm, grid_z, grid_size, world_size_cm)
          - get_exact_mesh_z(x, y - probe_cm, grid_z, grid_size, world_size_cm)) / (2.0 * probe_cm)

    inv = 1.0 / math.sqrt(zx * zx + zy * zy + 1.0)
    nx, ny, nz = -zx * inv, -zy * inv, inv

    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    nx_r = nx * cy + ny * sy
    ny_r = -nx * sy + ny * cy

    roll = math.asin(max(-1.0, min(1.0, -ny_r)))
    cr = math.cos(roll)
    pitch = math.asin(max(-1.0, min(1.0, -nx_r / cr))) if abs(cr) > 1e-6 else 0.0
    return math.degrees(pitch), math.degrees(roll), (nx, ny, nz)


def up_vector_from_rotator(pitch_deg, yaw_deg, roll_deg):
    """Unreal's own up vector for a rotator -- the inverse of ``terrain_pose``.

    Here so the check can be an assertion about Unreal's convention rather than
    a restatement of the code above.
    """
    p, y, r = (math.radians(v) for v in (pitch_deg, yaw_deg, roll_deg))
    return (-math.sin(p) * math.cos(y) * math.cos(r) + math.sin(y) * math.sin(r),
            -math.sin(p) * math.sin(y) * math.cos(r) - math.cos(y) * math.sin(r),
            math.cos(p) * math.cos(r))


def _build_tree_grid(placed_trees, cell_cm: float):
    """Bucket tree XY positions into a hash grid for O(1) proximity queries."""
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for t in placed_trees or []:
        key = (int(math.floor(t.x / cell_cm)), int(math.floor(t.y / cell_cm)))
        grid.setdefault(key, []).append((t.x, t.y))
    return grid


def _near_tree(grid, cell_cm: float, x: float, y: float, radius_cm: float) -> bool:
    cx = int(math.floor(x / cell_cm))
    cy = int(math.floor(y / cell_cm))
    r2 = radius_cm * radius_cm
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for (tx, ty) in grid.get((cx + dx, cy + dy), ()):
                if (tx - x) ** 2 + (ty - y) ** 2 < r2:
                    return True
    return False


def scatter_grass(
    world_size_cm: float,
    grid_z,
    grid_size: int,
    seed: int = 42,
    density_per_sqm: float = DEFAULT_DENSITY_PER_SQM,
    knee_height_cm: float = KNEE_HEIGHT_CM,
    patchiness: float = DEFAULT_PATCHINESS,
    grass_specs: list[GrassSpec] | None = None,
    placed_trees=None,
    spawn_clear_radius_cm: float = SPAWN_CLEAR_RADIUS_CM,
    tree_clear_radius_cm: float = TREE_CLEAR_RADIUS_CM,
    coverage_fraction: float = 0.97,
    tiers=GRASS_TIERS,
) -> list[PlacedGrass]:
    """
    Scatter grass patches across the whole terrain, one layer per density tier
    (grass_cells.GRASS_TIERS).

    Each tier is its own jittered stratified grid at its share of
    ``density_per_sqm``, with its own random stream, so every tier on its own
    covers the map evenly -- Low, which draws only the first, is thinner but
    never bald. ``patchiness`` drops and doubles grid cells at equal rates, so
    the expected density is preserved while the field gains thin and thick
    patches.

    Returns a list of PlacedGrass records for verification.
    """
    if grass_specs is None:
        grass_specs = DEFAULT_GRASS_SPECS
    if density_per_sqm <= 0 or not grass_specs:
        return []

    placed: list[PlacedGrass] = []
    for tier_index, tier in enumerate(tiers):
        # Decorrelated from tree placement, and each tier from the others.
        rng = random.Random((seed ^ 0x6A55) + 7919 * tier_index)
        placed.extend(_scatter_layer(
            rng, tier_index, density_per_sqm * tier.share, world_size_cm,
            grid_z, grid_size, knee_height_cm, patchiness, grass_specs,
            placed_trees, spawn_clear_radius_cm, tree_clear_radius_cm,
            coverage_fraction))
    return placed


def _scatter_layer(rng, tier, density_per_sqm, world_size_cm, grid_z, grid_size,
                   knee_height_cm, patchiness, grass_specs, placed_trees,
                   spawn_clear_radius_cm, tree_clear_radius_cm,
                   coverage_fraction) -> list[PlacedGrass]:
    """One tier's even layer of patches; see scatter_grass."""
    half = world_size_cm / 2.0 * coverage_fraction
    cell_cm = math.sqrt(1.0 / density_per_sqm) * 100.0  # density is per m²
    n_cells = max(1, int(math.floor((2.0 * half) / cell_cm)))
    origin = -half

    weights = [s.weight for s in grass_specs]
    tree_grid = _build_tree_grid(placed_trees, max(cell_cm, tree_clear_radius_cm))
    tree_cell = max(cell_cm, tree_clear_radius_cm)
    spawn_r2 = spawn_clear_radius_cm * spawn_clear_radius_cm

    placed: list[PlacedGrass] = []

    for iy in range(n_cells):
        for ix in range(n_cells):
            # Patchiness: equal chance of dropping the cell or doubling it,
            # which leaves the expected count per cell at exactly 1.
            roll = rng.random()
            if roll < patchiness:
                n_here = 0
            elif roll > 1.0 - patchiness:
                n_here = 2
            else:
                n_here = 1

            for _ in range(n_here):
                gx = origin + (ix + rng.random()) * cell_cm
                gy = origin + (iy + rng.random()) * cell_cm

                if gx * gx + gy * gy < spawn_r2:
                    continue
                if tree_grid and _near_tree(tree_grid, tree_cell, gx, gy, tree_clear_radius_cm):
                    continue

                spec = rng.choices(grass_specs, weights=weights, k=1)[0]

                gz = get_exact_mesh_z(gx, gy, grid_z, grid_size, world_size_cm)

                # Stand it along the ground, then lean it a little. The lean is
                # added to the aligned pose rather than replacing it, so the
                # field keeps its variety and keeps its feet.
                yaw = rng.uniform(0.0, 360.0)
                pitch, roll, _n = terrain_pose(gx, gy, yaw, grid_z, grid_size,
                                               world_size_cm)
                pitch += rng.uniform(-spec.max_tilt_deg, spec.max_tilt_deg)
                roll += rng.uniform(-spec.max_tilt_deg, spec.max_tilt_deg)

                h_scale = rng.uniform(*spec.height_jitter)
                w_scale = rng.uniform(*spec.width_jitter)
                target_h = knee_height_cm * spec.height_ratio * h_scale
                sink = spec.sink_cm * h_scale

                placed.append(PlacedGrass(
                    spec_name=spec.name,
                    x=gx, y=gy,
                    terrain_z=gz,
                    placed_z=gz - sink,
                    yaw_deg=yaw,
                    pitch_deg=pitch,
                    roll_deg=roll,
                    height_scale=h_scale,
                    width_scale=w_scale,
                    target_height_cm=target_h,
                    sink_cm=sink,
                    tier=tier,
                ))

    return placed


def grass_spec_by_name(name: str, grass_specs: list[GrassSpec] | None = None) -> GrassSpec | None:
    for s in (grass_specs or DEFAULT_GRASS_SPECS):
        if s.name == name:
            return s
    return None
