"""The trees on the title's stage: the play level's own, from its middle.
Pure Python (no ``unreal``).

The forest's scatter draws each tree's distance from the centre evenly
(forest_generator/tree_placement.py), so the trees stand thickest in the
middle of the map and thin towards its rim. The title is that middle: the
same scatter, at the play level's size, seed and density, kept within
TREE_RADIUS_CM. It is the same trees, one for one, as the generated import
of the play level plants there (a dev unit test holds the two together),
each sunk into a flat floor instead of the terrain. The clearing every
species keeps round the centre (7 m) is where the figure and the camera are.
"""

import math

from forest_generator.tree_placement import (
    DEFAULT_TREE_DENSITY, DEFAULT_TREE_SPECS, scatter_trees)
from title import paths as P

# What the play level (P.PLAY_LEVEL) was generated with:
# generate_forest_level.py --size 1000, its default seed and tree density.
PLAY_WORLD_SIZE_CM = 100000.0
PLAY_SEED = 42
# A flat terrain: one quad at z = 0.
_FLAT = ((0.0, 0.0), (0.0, 0.0))


def trees(radius_cm=P.TREE_RADIUS_CM):
    """The placements forest_import/trees.plant_trees takes: dicts of spec,
    x, y, z, yaw and scale."""
    placed = scatter_trees(PLAY_WORLD_SIZE_CM, _FLAT, 1, seed=PLAY_SEED,
                           density=DEFAULT_TREE_DENSITY)
    return [{"spec": t.spec_name, "x": round(t.x, 2), "y": round(t.y, 2),
             "z": round(t.placed_z, 2), "yaw": round(t.yaw_deg, 2),
             "scale": round(t.scale, 3)}
            for t in placed if math.hypot(t.x, t.y) <= radius_cm]


def configs():
    """Each species' mesh and materials, as plant_trees takes them."""
    return {s.name: {"mesh": s.mesh_path, "mats": list(s.material_paths)}
            for s in DEFAULT_TREE_SPECS}


def counts(placements):
    """How many of each species ``placements`` holds."""
    found = {}
    for t in placements:
        found[t["spec"]] = found.get(t["spec"], 0) + 1
    return found
