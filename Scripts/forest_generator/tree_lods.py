"""Which levels plant the trees with a LOD chain and an impostor, and which
mesh that is. Pure Python (no ``unreal``).

A tree has two builds. /Game/Forest/Trees is the Nanite one
(tree_meshes.py): one mesh, drawn leaf by leaf out to the cull distance.
/Game/Forest/TreesLOD is cut from it by Scripts/build_game_ready_mesh.py
(mesh_lod/): no Nanite, three mesh LODs and, past the last of them, three
crossed cards carrying a picture of the tree. Same name, same pivot, same
material slots, with the impostor's material in one more slot at the end.

A level named in TREE_LOD_LEVELS is planted from the second.
forest_import/trees.py reads this when it plants and when it verifies, so a
level changes build by a line here and a re-import. The 200 m and probe
levels stay on Nanite: they have a tenth of the trees, and the probes that
measure Nanite's cost run there.

Where each LOD starts is in the mesh (mesh_lod/spec.py, ``lod_distances_m``:
30, 60 and 110 m), worked out for the middle of the scale range the tree is
planted at. A cell's instances switch together, at the distance for the
middle of that cell's own scales, so two cells of one species can differ by
a third. The cull distances (tree_cells.py) are the same for both builds.
"""

from mesh_lod.jobs import TREE_DEST

TREE_LOD_LEVELS = frozenset({"Lvl_Forest_1000m"})

# The fewest LODs a planted LOD tree may have: a mesh and its impostor.
MIN_TREE_LODS = 2

BUILD_COMMAND = "python3 Scripts/build_game_ready_mesh.py trees"


def plants_lods(level):
    """True when ``level`` (a name, or None for a caller that has none)
    plants the LOD build."""
    return level in TREE_LOD_LEVELS


def lod_mesh_path(mesh_path):
    """The LOD build of the Nanite tree at ``mesh_path`` (a package or object
    path)."""
    name = mesh_path.rsplit("/", 1)[-1].split(".")[0]
    return f"{TREE_DEST}/{name}.{name}"
