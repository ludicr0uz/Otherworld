"""How far trees are drawn, and the cells they are planted in.

Pure Python (no ``unreal``), like grass_cells.py, whose cells, labels and
max-draw arithmetic this reuses -- a tree cell is the same 100 m square.

Why. Trees used to be one HISM per species covering the whole map, with no
cull distance: all ~3400 trees on the 1 km map were drawn (and shadowed) out to
the horizon, and since every one of the five bounds contained the camera,
nothing could be skipped short of testing each tree. Per-cell HISMs let whole
cells drop out; the cull distance makes them drop out at all.

The distances are scaled by r.ViewDistanceScale like grass (see
grass_cells.py): 0.4 Low, 0.6 Medium, 1.0 High and Ultra. So trees are gone by
120 m on Low, 180 m on Medium and 300 m on High/Ultra. Nanite does not dither
the fade, so a tree pops at the end distance; at night the fog hides it.
Tune these two numbers by eye.
"""

from forest_generator.grass_cells import (  # noqa: F401 -- re-exported
    cell_label, cell_max_draw_cm, cell_of, spec_of_label)

TREE_CULL_START_CM = 25000
TREE_CULL_END_CM = 30000

# 20 m: hilly terrain plus half a tree's height -- a cell's bounds centre sits
# up in the trunks, not at the ground a tree stands on.
TREE_CELL_MAX_DRAW_CM = cell_max_draw_cm(TREE_CULL_END_CM, 2000.0)

# Past this distance Nanite draws the leaves WITHOUT their opacity mask
# (UPrimitiveComponent::NanitePixelProgrammableDistance): the leaf cards become
# solid shapes instead of being alpha-tested pixel by pixel. The leaves are
# masked, two-sided cards, and masked is Nanite's expensive "programmable"
# raster path -- this is the biggest per-pixel saving the canopy has, and the
# cost is that distant canopy reads as solid clumps rather than lacy leaves.
# 60 m is inside the night fog; tune it by eye. Not scaled by
# r.ViewDistanceScale. 0 would mean "mask at every distance".
TREE_LEAF_MASK_DISTANCE_CM = 6000.0
