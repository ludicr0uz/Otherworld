"""
bush_placement.py — Deterministic, intermittent walk-through bushes.

Bushes come in loose clusters -- one to four around a centre -- scattered on
a coarse jittered grid with a good share of grid cells left empty, so the
forest floor alternates between open grass and thickets instead of carrying a
bush every few metres. They never block: forest_import/bushes.py plants them
with no collision, so the player and the wanderers walk straight through, and
the navmesh never sees them.

The meshes are generated (forest_generator/foliage_meshes.py) at their real
size, so the scale here is only jitter around 1.0.

A bush stands halfway between plumb and the terrain normal: fully aligned on
a 30-degree slope it leans out over the hill like it is falling, fully plumb
its downhill stems hang in the air. The sink covers what is left.
"""

import math
import random
from dataclasses import dataclass

from .foliage_meshes import BUSH_ROUND, BUSH_TALL, MI_BUSH, asset_path
from .grass_placement import _build_tree_grid, _near_tree, terrain_pose
from .terrain import get_exact_mesh_z


@dataclass
class BushSpec:
    name: str                      # HISM actor label prefix
    mesh_path: str
    material_paths: list
    weight: float
    scale_jitter: tuple = (0.80, 1.25)
    width_jitter: tuple = (0.90, 1.15)   # on top of scale, per axis pair
    sink_cm: float = 6.0


DEFAULT_BUSH_SPECS = [
    BushSpec("HISM_Bush_Round", asset_path(BUSH_ROUND), [MI_BUSH], weight=1.3),
    BushSpec("HISM_Bush_Tall", asset_path(BUSH_TALL), [MI_BUSH], weight=0.7,
             scale_jitter=(0.85, 1.15)),
]

# Cluster centres per hectare before the empty share is taken out, and how
# many of the grid cells stay empty. That is ~26 thickets and ~80 bushes per
# hectare -- a thicket every 20 m or so, open grass between.
BUSH_CLUSTERS_PER_HA = 40.0
BUSH_EMPTY_SHARE = 0.35
BUSH_PER_CLUSTER = (1, 4)
BUSH_CLUSTER_RADIUS_CM = 260.0
BUSH_MIN_SEPARATION_CM = 110.0     # within a cluster, crown centres apart
BUSH_TREE_CLEAR_CM = 160.0         # a bush does not grow out of a trunk
BUSH_SPAWN_CLEAR_CM = 600.0        # the player does not start inside one
BUSH_ALIGN_TO_SLOPE = 0.5          # 0 plumb, 1 along the terrain normal


@dataclass
class PlacedBush:
    spec_name: str
    x: float
    y: float
    terrain_z: float
    placed_z: float
    yaw_deg: float
    pitch_deg: float
    roll_deg: float
    scale_xy: float
    scale_z: float
    sink_cm: float


def bush_spec_by_name(name, specs=None):
    for s in specs or DEFAULT_BUSH_SPECS:
        if s.name == name:
            return s
    return None


def scatter_bushes(world_size_cm, grid_z, grid_size, seed=42, placed_trees=None,
                   clusters_per_ha=BUSH_CLUSTERS_PER_HA, specs=None,
                   coverage_fraction=0.95):
    """Scatter bush clusters over the map. Returns PlacedBush records."""
    specs = specs or DEFAULT_BUSH_SPECS
    if clusters_per_ha <= 0 or not specs:
        return []
    rng = random.Random(seed ^ 0xB054)

    half = world_size_cm / 2.0 * coverage_fraction
    cell_cm = math.sqrt(10000.0 / clusters_per_ha) * 100.0   # ha -> m² -> cm
    n_cells = max(1, int(math.floor(2.0 * half / cell_cm)))
    tree_grid = _build_tree_grid(placed_trees, max(cell_cm, BUSH_TREE_CLEAR_CM))
    tree_cell = max(cell_cm, BUSH_TREE_CLEAR_CM)
    weights = [s.weight for s in specs]

    placed = []
    for iy in range(n_cells):
        for ix in range(n_cells):
            if rng.random() < BUSH_EMPTY_SHARE:
                continue
            cx = -half + (ix + rng.random()) * cell_cm
            cy = -half + (iy + rng.random()) * cell_cm
            cluster = []
            for _ in range(rng.randint(*BUSH_PER_CLUSTER) * 3):  # tries
                if len(cluster) >= BUSH_PER_CLUSTER[1]:
                    break
                r = BUSH_CLUSTER_RADIUS_CM * math.sqrt(rng.random())
                a = rng.uniform(0.0, math.tau)
                x = max(-half, min(half, cx + r * math.cos(a)))
                y = max(-half, min(half, cy + r * math.sin(a)))
                if x * x + y * y < BUSH_SPAWN_CLEAR_CM ** 2:
                    continue
                if tree_grid and _near_tree(tree_grid, tree_cell, x, y,
                                            BUSH_TREE_CLEAR_CM):
                    continue
                if any((x - b.x) ** 2 + (y - b.y) ** 2 < BUSH_MIN_SEPARATION_CM ** 2
                       for b in cluster):
                    continue
                cluster.append(_place_one(rng, specs, weights, x, y, grid_z,
                                          grid_size, world_size_cm))
            placed.extend(cluster)
    return placed


def _place_one(rng, specs, weights, x, y, grid_z, grid_size, world_size_cm):
    spec = rng.choices(specs, weights=weights, k=1)[0]
    z = get_exact_mesh_z(x, y, grid_z, grid_size, world_size_cm)
    yaw = rng.uniform(0.0, 360.0)
    pitch, roll, _n = terrain_pose(x, y, yaw, grid_z, grid_size, world_size_cm)
    scale = rng.uniform(*spec.scale_jitter)
    sink = spec.sink_cm * scale
    return PlacedBush(
        spec_name=spec.name, x=x, y=y, terrain_z=z, placed_z=z - sink,
        yaw_deg=yaw, pitch_deg=pitch * BUSH_ALIGN_TO_SLOPE,
        roll_deg=roll * BUSH_ALIGN_TO_SLOPE,
        scale_xy=scale * rng.uniform(*spec.width_jitter), scale_z=scale,
        sink_cm=sink)
