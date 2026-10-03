"""How grass is cut into map cells, and how far each cell and clump is drawn.
Trees use the same cells (forest_generator/tree_cells.py).

Pure Python (no ``unreal``): the generator, the in-editor planting code
(forest_import/grass.py) and the graphics menu all read these, so a label, the
tag and the distances cannot drift apart.

Why cells. One HISM per species used to cover the whole map -- nine actors
holding 1.1 million clumps on the 1 km map. Every one of those nine bounds
contains the camera, so no view (the main one, or any shadow cascade) can ever
skip one; all the culling has to happen per instance. Cut into cells, whole
cells behind the camera or out of range drop out at the primitive level before
any instance is looked at.

Both distances below are scaled by r.ViewDistanceScale -- 0.4 at Low, 0.6
Medium, 0.8 High, 1.0 Epic (BaseScalability.ini) -- on the instance cull
(InstancedStaticMesh.cpp, and Nanite's copy in PrimitiveUniformShaderParameters)
and on the primitive max draw distance (SceneVisibility.cpp) alike. So the Low
tier of grass fades at 18-28 m on Low and 45-70 m on High and Ultra.
"""

import math
from collections import namedtuple

# Actor tag every grass and bush cell carries; the graphics menu finds them by
# it to switch their lighting with the preset.
GRASS_TAG = "OW_Grass"

# Cell edge. 100 m makes 100 cells on the 1 km map (x 2 grass species x 4
# tiers, plus 2 bush species = up to 1000 actors) and 4 on the 200 m map.
# Smaller cells cull tighter but multiply the actor count, and every one of
# them is a primitive the renderer tracks.
GRASS_CELL_CM = 10000.0

# ─── Density tiers: how grass scales with the quality preset ────────────────
#
# Every grass patch belongs to one tier, and a tier is drawn from its
# ``min_preset`` up (graphics_menu/gfx_stats.py: 0 Low, 1 Medium, 2 High,
# 3 Ultra; that is each preset's default "grass layers", which the M panel's
# GRAPHICS SETTINGS tab can change). Each tier is its own evenly spread layer, so Low is a thinner field,
# not a field with holes, and each preset above it lays another layer on top.
#
# The upper tiers also fade out closer. Thickness only reads near the player;
# far off, one layer and fifty look the same through the night fog. So Ultra is
# 2.5x Low's density inside 15 m and the same density at 60 m -- the triangles
# go where they show.
#
# A tier above Low is saved HIDDEN IN GAME -- the Low state, as the grass is
# saved unlit (forest_import/grass.py) -- and the menu unhides it -- see graphics_menu/gfx_tuner_foliage.py.
# Hidden in game, not invisible: the editor viewport still shows every tier.
#
#   min_preset  share of the total density   instance fade start / end (cm)
GrassTier = namedtuple("GrassTier", "min_preset share cull_start_cm cull_end_cm")
GRASS_TIERS = (
    GrassTier(0, 0.40, 4500, 7000),
    GrassTier(1, 0.20, 3500, 5000),
    GrassTier(2, 0.20, 2500, 3500),
    GrassTier(3, 0.20, 1500, 2500),
)
assert abs(sum(t.share for t in GRASS_TIERS) - 1.0) < 1e-9
assert [t.min_preset for t in GRASS_TIERS] == sorted(t.min_preset for t in GRASS_TIERS)


def tier_tag(tier):
    """Actor tag of every cell in one tier above Low; the menu finds them by it."""
    return f"OW_GrassTier{tier}"


def tier_spec(spec_name, tier):
    """The species-and-tier name a cell's label is built from."""
    return f"{spec_name}_T{tier}"


def tier_of_label(label):
    """Inverse of tier_spec, from a cell label or its species part."""
    return int(spec_of_label(label).rsplit("_T", 1)[1])


# ─── Bushes ──────────────────────────────────────────────────────────────────
#
# Bushes are drawn at every preset -- a bush you can hide behind on Ultra must
# be there on Low -- and further out than grass, since at 1-1.7 m tall they
# read against the trunks. They share the grass tag, so Ultra lights them too.
BUSH_CULL_START_CM = 8000
BUSH_CULL_END_CM = 11000

# The lowest r.ViewDistanceScale a preset uses (Low).
MIN_VIEW_DISTANCE_SCALE = 0.4



def cell_max_draw_cm(cull_end_cm, vertical_slack_cm):
    """Max draw distance for one cell whose instances fade out by ``cull_end_cm``.

    A cell's max draw distance is measured to the centre of its bounds, but the
    instance nearest the camera can sit a half-diagonal away from that centre --
    and that slack does NOT shrink with the view-distance scale while the draw
    distance does. Sized for the worst case (Low), so no cell ever vanishes
    while an instance in it is still inside its own fade range.
    ``vertical_slack_cm`` covers how far the bounds centre can sit above or
    below an instance: hilly terrain, plus the height of what is planted.
    """
    reach = GRASS_CELL_CM * math.sqrt(0.5) + vertical_slack_cm
    return round(cull_end_cm + reach / MIN_VIEW_DISTANCE_SCALE)


# 5 m: hilly terrain; a patch itself is knee-high.
GRASS_TIER_MAX_DRAW_CM = tuple(cell_max_draw_cm(t.cull_end_cm, 500.0)
                               for t in GRASS_TIERS)
# 5 m of terrain plus a bush's height.
BUSH_CELL_MAX_DRAW_CM = cell_max_draw_cm(BUSH_CULL_END_CM, 700.0)


def cell_of(x_cm, y_cm):
    """The (ix, iy) cell a point falls in. Cells are anchored on the map
    origin, so the spawn is always at a cell corner and cells are stable
    across map sizes."""
    return (math.floor(x_cm / GRASS_CELL_CM), math.floor(y_cm / GRASS_CELL_CM))


def cell_label(spec_name, cell):
    """Actor label of one species' HISM in one cell.

    Keeps the ``HISM_Grass`` prefix the import script's cleanup sweeps on, and
    ``<spec>__`` so everything of one species is found with one startswith.
    """
    ix, iy = cell
    return f"{spec_name}__{ix:+03d}_{iy:+03d}"


def spec_of_label(label):
    """Inverse of cell_label's species part."""
    return label.split("__", 1)[0]
