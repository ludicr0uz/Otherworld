"""Which trees have leaves low enough to walk into, so that passing one is
heard as passing a bush is (Sound/sound_world.py, the rustle). Pure Python
(no ``unreal``).

Whether a walker meets a tree's leaves is a matter of how low they start:

    mesh               leaf slot   lowest leaf   x the largest scale planted
    SM_Fir_A               2         577 cm         21.9 m
    SM_IslandTree_01       1          62 cm          2.2 m
    SM_IslandTree_02       1         124 cm          4.5 m
    SM_PineSapling_A       1          22 cm          1.2 m
    SM_TreeSmall_02        1         147 cm          6.2 m

(the built mesh's leaf section, its bounds from the pivot at the trunk's foot;
verify/sound_states.py measures them again). A species has low leaves when
every tree of it, the largest too, has leaves under WALKER_HEAD_CM: the pine
sapling, whose needles start at the knee and reach 47 cm from the stem at
scale 1, which is its bounds (40 x 37 cm) and a little. The first island tree
is left out: only its smallest (under scale 2.9) have a leaf under 1.8 m, one
bough on one side, 1.5 m from the trunk, and its bounds are the whole crown's.

The rustle asks an instance's bounds, so a tree belongs here only if its
bounds are its low leaves': a crown on a bare trunk would rustle everywhere
under it.

THE LEAVES ARE NOT AIR. A tree collides by its complex collision, cooked from
its Nanite fallback (the LOD build: from its last mesh LOD), and the fallback
keeps some of the leaves: 2,919 of the sapling's 32,814 needle triangles. So a
walker pushes into a sapling's needles and is stopped part of the way in, at
places as far as the stem (Sound/sound_world.py has the distances). Making
the needles truly walked through would be a collision mesh of the wood alone:
not done here, it changes where a player and a bullet can go.
"""

from forest_generator.tree_lods import lod_mesh_path
from forest_generator.tree_meshes import (
    FIR_A, ISLAND_01, ISLAND_02, PINE_SAPLING_A, TREE_SMALL_02)
from forest_generator.tree_placement import DEFAULT_TREE_SPECS

# A walker's head over the ground they stand on.
WALKER_HEAD_CM = 180.0

# recipe name -> (the material slot that is its leaves, the lowest of them
# over the pivot at scale 1, in cm).
LEAVES = {
    FIR_A.name: (2, 577.1),
    ISLAND_01.name: (1, 62.4),
    ISLAND_02.name: (1, 124.1),
    PINE_SAPLING_A.name: (1, 21.5),
    TREE_SMALL_02.name: (1, 146.7),
}


def _name(spec):
    return spec.mesh_path.rsplit(".", 1)[-1]


def lowest_leaf_cm(spec):
    """The lowest leaf of the largest tree ``spec`` plants, over the ground."""
    return LEAVES[_name(spec)][1] * spec.scale_max


LOW_LEAF_TREE_SPECS = tuple(s for s in DEFAULT_TREE_SPECS
                            if lowest_leaf_cm(s) < WALKER_HEAD_CM)


def low_leaf_mesh_paths():
    """The object paths of the meshes walked through: each low-leaved tree's
    Nanite build, then its LOD build (tree_lods.py: a level plants one or the
    other)."""
    paths = [s.mesh_path for s in LOW_LEAF_TREE_SPECS]
    return paths + [lod_mesh_path(p) for p in paths]
