"""The tree meshes the levels plant: cut-down copies of the scans. Pure Python
(no ``unreal``); forest_import/tree_assets.py builds them.

Why copies. The scans under /Game/Forest/Scanned are kept exactly as they were
imported, for reference: nothing here or in tree_assets.py writes to them. Each
tree planted is a copy under /Game/Forest/Trees, built from a recipe below.

Why cut down. The scans are 0.14-4.2 M triangles each, nearly all of it
foliage: every leaf of an island tree is its own 24-triangle mesh, and there
are 30-44 thousand of them. On this Mac Nanite rasterises everything through
the hardware path (its compute rasteriser does no work, whatever the cvars
say), so the frame pays per triangle drawn, and a tree's leaves are drawn leaf
by leaf out to the cull distance. What was measured on the 1 km map at Medium
(graphisOptimizationStrategy.md), trees' share of the frame:

    the scans, fir_tree_01_a at 1.8-3.8x                   26 ms
    the scan's small fir at its own size                   16 ms
    + every leaf simplified, none dropped                  13 ms
    + half the leaves dropped, the rest 1.4x the size      11 ms
    + Nanite's Preserve Area off (the recipes below)        9 ms
    a quarter of the leaves at twice the size               8 ms (reads coarse)

Simplifying alone buys little, because Nanite already draws a distant leaf
with few triangles; what it cannot do is draw fewer leaves. So a recipe drops
a share of the pieces and grows the survivors until the crown covers the same
area. Preserve Area does the same thing again at run time, further out, and
cost 2 ms for no difference that showed, so it is off.

The fir is fir_tree_01_a, the tall one, at 1.8-3.8x: a 34-72 m tree whose
crown closes over the forest. It is the look the forest was built around, and
the most expensive tree in it: 4.18 M triangles, 812 thousand needle cards. The
numbers above were taken with the scan's small fir (fir_tree_01_c, at its own
size) standing in for it, which cost least and looked thin. Put back at full
size, with the fir at Medium on the same spot:

    the small fir (above)                                  17.5 ms a frame
    fir_tree_01_a, 15% of its cards, all of the area       24.5 ms
    10% of the cards, half the area                        22.5 ms
    6% of the cards, half the area (the recipe below)      21.5 ms
    2.5% of the cards, 30% of the area                     20.5 ms

So the tall fir costs about 4 ms over the small one however far it is cut:
the crowns are 30 m and more overhead, where a card three times the size
reads the same, but a tree that size fills the screen. fir_tree_01_c is 12 m
off its origin in the scan (its place in the scan's line-up was baked in); a
recipe for it needs trunk_base_cm=(1200, 0, 0).
"""

import hashlib
from dataclasses import dataclass

TREE_MESH_DIR = "/Game/Forest/Trees"
_SCANNED = "/Game/Forest/Scanned"
_INSTANCES = "/Game/Forest/Materials/Instances"

# The asset metadata tag a built mesh carries: the recipe it was built from.
RECIPE_TAG = "OW_TreeRecipe"


@dataclass(frozen=True)
class SectionCut:
    """How one material slot's geometry is cut down. A foliage section is
    thousands of disconnected pieces (a leaf, a needle card, a twig), and
    ``triangles_per_piece`` x that count is the triangle budget the section is
    simplified to. Simplifying within the pieces keeps every leaf where it is;
    Nanite's own trim deletes whole leaves instead.

    ``method``: "attribute" keeps UVs and normals true, for leaves and cards;
    "volume" keeps thin tubes from collapsing to nothing, for twigs.
    ``keep_pieces``: the share of the pieces kept at all (1.0 = every one),
    dropped evenly through the crown before the rest are simplified.
    ``restore_area``: grow each piece about its own centre afterwards, until
    the section covers this share of the area it did (True or 1.0: all of it)
    -- for leaves, not for wood. With keep_pieces 0.25 and all of the area
    that is a quarter of the leaves at twice the size. Less than all of it
    thins the crown, which is the one thing that cuts what the masked cards
    cost in pixels rather than in triangles."""
    slot: int
    triangles_per_piece: float | None = None    # None: pieces left as they are
    method: str = "attribute"
    restore_area: float = 0.0
    keep_pieces: float = 1.0


@dataclass(frozen=True)
class TreeMeshRecipe:
    """One derived tree mesh."""
    name: str                   # asset name under TREE_MESH_DIR
    source_path: str            # the scan it is copied from; never modified
    material_paths: tuple       # one per material slot, in the scan's order
    trunk_base_cm: tuple = (0.0, 0.0, 0.0)  # where the trunk stands in the scan
    cuts: tuple = ()            # SectionCuts; a slot without one is kept whole
    # Nanite build settings. keep_triangles is Nanite's own trim (1.0 = none):
    # tried, it deletes leaves where a cut simplifies them. preserve_area
    # widens what is left of the foliage as distance thins it (module
    # docstring). fallback_triangles is the share kept for the non-Nanite
    # fallback mesh; None is the engine's automatic one.
    keep_triangles: float = 1.0
    preserve_area: bool = False
    fallback_triangles: float | None = None
    triangle_budget: int = 0    # the built mesh may not exceed this; 0 = any
    revision: int = 1           # bump to rebuild when tree_assets.py changes

    @property
    def path(self):
        return f"{TREE_MESH_DIR}/{self.name}"

    @property
    def object_path(self):
        return f"{self.path}.{self.name}"

    @property
    def stamp(self):
        """What a built asset is tagged with; a different stamp is rebuilt."""
        return hashlib.sha1(repr(self).encode()).hexdigest()[:16]


def _scan(folder, mesh):
    return f"{_SCANNED}/{folder}/{folder}_1k/StaticMeshes/{mesh}"


def _foliage(slot, triangles_per_piece, keep_pieces):
    return SectionCut(slot, triangles_per_piece, "attribute", True, keep_pieces)


# Slots: bark (the boughs), trunk, twig cards (4 triangles each, 812 k of
# them), dead branches. The cards kept are grown 3x, to half the area the
# crown had.
FIR_A = TreeMeshRecipe(
    name="SM_Fir_A",
    source_path=_scan("fir_tree_01", "fir_tree_01_a_LOD0"),
    material_paths=(
        f"{_INSTANCES}/MI_FirTree01_Bark",
        f"{_INSTANCES}/MI_FirTree01_TrunkA",
        f"{_INSTANCES}/MI_FirTree01_Twig",
        f"{_INSTANCES}/MI_FirTree01_Bark",
    ),
    cuts=(SectionCut(2, 3, "attribute", 0.5, 0.06), SectionCut(1, 800, "volume")),
    triangle_budget=210_000,
)

# Slots: trunk, leaves (24 triangles each), twigs (33-132 each).
ISLAND_01 = TreeMeshRecipe(
    name="SM_IslandTree_01",
    source_path=_scan("island_tree_01", "SM_island_tree_01"),
    material_paths=(
        f"{_INSTANCES}/MI_IslandTree01_Trunk",
        f"{_INSTANCES}/MI_IslandTree01_Leaves",
        f"{_INSTANCES}/MI_IslandTree01_Branches",
    ),
    cuts=(_foliage(1, 5, 0.5), SectionCut(2, 10, "volume", False, 0.6)),
    triangle_budget=200_000,
)

ISLAND_02 = TreeMeshRecipe(
    name="SM_IslandTree_02",
    source_path=_scan("island_tree_02", "SM_island_tree_02"),
    material_paths=(
        f"{_INSTANCES}/MI_IslandTree02_Trunk",
        f"{_INSTANCES}/MI_IslandTree02_Leaves",
        f"{_INSTANCES}/MI_IslandTree02_Branches",
    ),
    cuts=(_foliage(1, 5, 0.5), SectionCut(2, 10, "volume", False, 0.6)),
    triangle_budget=140_000,
)

# Slots: bark, twig cards (7-20 triangles each).
PINE_SAPLING_A = TreeMeshRecipe(
    name="SM_PineSapling_A",
    source_path=_scan("pine_sapling_small", "pine_sapling_small_a"),
    material_paths=(
        f"{_INSTANCES}/MI_PineSapling_Bark",
        f"{_INSTANCES}/MI_PineSapling_Twig",
    ),
    cuts=(_foliage(1, 6, 0.6),),
    triangle_budget=35_000,
)

# Slots: branches, leaves (single leaves of 15-19 triangles and sprays of
# 170), trunk.
TREE_SMALL_02 = TreeMeshRecipe(
    name="SM_TreeSmall_02",
    source_path=_scan("tree_small_02", "SM_tree_small_02"),
    material_paths=(
        f"{_INSTANCES}/MI_TreeSmall02_Branches",
        f"{_INSTANCES}/MI_TreeSmall02_Leaves",
        f"{_INSTANCES}/MI_TreeSmall02_Trunk",
    ),
    cuts=(_foliage(1, 12, 0.5), SectionCut(0, 40, "volume")),
    triangle_budget=245_000,
)

TREE_MESH_RECIPES = (FIR_A, ISLAND_01, ISLAND_02, PINE_SAPLING_A, TREE_SMALL_02)

# How far a built mesh's bounds centre may sit from its pivot, in XY. A crown
# is lopsided (an island tree's by 90 cm); a pivot left where the scan's
# small fir has it is 12 m out.
PIVOT_TOLERANCE_CM = 120.0
