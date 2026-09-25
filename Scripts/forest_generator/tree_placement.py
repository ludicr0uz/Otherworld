"""
tree_placement.py — Deterministic tree scattering with exact terrain snapping.

Places trees using radial distribution with configurable density, scaling to
the world_size.  Every tree's Z is computed via exact barycentric interpolation
on the terrain mesh grid, and roots are sunk below the surface.
"""

import math
import random
from dataclasses import dataclass, field

from .terrain import get_exact_mesh_z


# ─── Configuration ───────────────────────────────────────────────────────────

@dataclass
class TreeSpec:
    """Defines one category of tree to be instanced."""
    name: str                     # HISM actor label
    mesh_path: str                # UE content path to StaticMesh
    material_paths: list[str]     # UE content paths to material slots
    count_per_hectare: float      # trees per 10 000 m² (density)
    scale_min: float = 2.0
    scale_max: float = 3.6
    sink_base_cm: float = 40.0   # root sink at scale 1.0
    sink_ref_scale: float = 2.5  # reference scale for sink computation
    min_dist_from_center: float = 700.0  # cm — keep spawn zone clear


# The five tree categories matching the Lvl_Forest style
DEFAULT_TREE_SPECS = [
    # Broadleaf island trees (leafy canopy)
    TreeSpec(
        name="HISM_Tree_Leafy_Island_01",
        mesh_path="/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01",
        material_paths=[
            "/Game/Forest/Materials/Instances/MI_IslandTree01_Trunk",
            "/Game/Forest/Materials/Instances/MI_IslandTree01_Leaves",
            "/Game/Forest/Materials/Instances/MI_IslandTree01_Branches",
        ],
        count_per_hectare=7.0,
        scale_min=2.0, scale_max=3.6,
        sink_base_cm=40.0, sink_ref_scale=2.5,
    ),
    TreeSpec(
        name="HISM_Tree_Leafy_Island_02",
        mesh_path="/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02",
        material_paths=[
            "/Game/Forest/Materials/Instances/MI_IslandTree02_Trunk",
            "/Game/Forest/Materials/Instances/MI_IslandTree02_Leaves",
            "/Game/Forest/Materials/Instances/MI_IslandTree02_Branches",
        ],
        count_per_hectare=7.0,
        scale_min=2.0, scale_max=3.6,
        sink_base_cm=40.0, sink_ref_scale=2.5,
    ),
    # Evergreen fir
    TreeSpec(
        name="HISM_Tree_Fir_A",
        mesh_path="/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0",
        material_paths=[
            "/Game/Forest/Materials/Instances/MI_FirTree01_Bark",
            "/Game/Forest/Materials/Instances/MI_FirTree01_TrunkA",
            "/Game/Forest/Materials/Instances/MI_FirTree01_Twig",
            "/Game/Forest/Materials/Instances/MI_FirTree01_Bark",
        ],
        count_per_hectare=11.0,
        scale_min=1.8, scale_max=3.8,
        sink_base_cm=45.0, sink_ref_scale=2.5,
    ),
    # Pine saplings
    TreeSpec(
        name="HISM_Tree_Pine_A",
        mesh_path="/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a",
        material_paths=[
            "/Game/Forest/Materials/Instances/MI_PineSapling_Bark",
            "/Game/Forest/Materials/Instances/MI_PineSapling_Twig",
        ],
        count_per_hectare=5.0,
        scale_min=3.0, scale_max=5.5,
        sink_base_cm=35.0, sink_ref_scale=4.0,
    ),
    # Deciduous small trees
    TreeSpec(
        name="HISM_Tree_Deciduous",
        mesh_path="/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
        material_paths=[
            "/Game/Forest/Materials/Instances/MI_TreeSmall02_Branches",
            "/Game/Forest/Materials/Instances/MI_TreeSmall02_Leaves",
            "/Game/Forest/Materials/Instances/MI_TreeSmall02_Trunk",
        ],
        count_per_hectare=4.0,
        scale_min=2.5, scale_max=4.2,
        sink_base_cm=40.0, sink_ref_scale=3.0,
    ),
]


# ─── Placement record ───────────────────────────────────────────────────────

@dataclass
class PlacedTree:
    """One tree instance after placement."""
    spec_name: str
    x: float
    y: float
    terrain_z: float     # exact mesh Z at (x, y)
    placed_z: float      # final Z after sinking roots
    yaw_deg: float
    scale: float
    sink_cm: float


# ─── Scatter ─────────────────────────────────────────────────────────────────

def scatter_trees(
    world_size_cm: float,
    grid_z,
    grid_size: int,
    tree_specs: list[TreeSpec] | None = None,
    seed: int = 42,
) -> list[PlacedTree]:
    """
    Scatter trees across the terrain.

    Tree count per spec is derived from ``count_per_hectare`` × map area.
    Every tree is placed at a random polar coordinate and snapped to the
    exact mesh facet via barycentric interpolation.

    Returns a list of PlacedTree records for verification.
    """
    if tree_specs is None:
        tree_specs = DEFAULT_TREE_SPECS

    rng = random.Random(seed)

    area_hectares = (world_size_cm / 100.0) ** 2 / 10_000.0
    half = world_size_cm / 2.0
    max_dist = half * 0.85  # keep trees inside 85% of the map edge

    placed: list[PlacedTree] = []

    for spec in tree_specs:
        count = max(1, int(round(spec.count_per_hectare * area_hectares)))
        for _ in range(count):
            dist = rng.uniform(spec.min_dist_from_center, max_dist)
            theta = rng.uniform(0, 2 * math.pi)
            tx = dist * math.cos(theta)
            ty = dist * math.sin(theta)

            # Clamp to map bounds
            tx = max(-half * 0.95, min(half * 0.95, tx))
            ty = max(-half * 0.95, min(half * 0.95, ty))

            tz = get_exact_mesh_z(tx, ty, grid_z, grid_size, world_size_cm)

            scale_val = rng.uniform(spec.scale_min, spec.scale_max)
            yaw = rng.uniform(0.0, 360.0)
            sink = spec.sink_base_cm * (scale_val / spec.sink_ref_scale)

            placed.append(PlacedTree(
                spec_name=spec.name,
                x=tx, y=ty,
                terrain_z=tz,
                placed_z=tz - sink,
                yaw_deg=yaw,
                scale=scale_val,
                sink_cm=sink,
            ))

    return placed
