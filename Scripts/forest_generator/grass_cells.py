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
and on the primitive max draw distance (SceneVisibility.cpp) alike. So grass
fades at 24-36 m on Low and 60-90 m on High and Ultra.
"""

import math

# Actor tag every grass cell carries; the graphics menu finds cells by it.
GRASS_TAG = "OW_Grass"

# Cell edge. 100 m makes 100 cells on the 1 km map (x 9 species = up to 900
# actors) and 4 on the 200 m map. Smaller cells cull tighter but multiply the
# actor count, and every one of them is a primitive the renderer tracks.
GRASS_CELL_CM = 10000.0

# Per-instance fade, unchanged from when grass was one HISM per species.
GRASS_CULL_START_CM = 6000
GRASS_CULL_END_CM = 9000

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


# 5 m: hilly terrain; a clump itself is knee-high.
GRASS_CELL_MAX_DRAW_CM = cell_max_draw_cm(GRASS_CULL_END_CM, 500.0)


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
