"""Wind in the grass and the trees: the numbers. Pure Python (no ``unreal``).

forest_import/wind.py writes them into the materials as world-position
offset (WPO); the graphics menu's tuner (graphics_menu/gfx_tuner_wind.py)
switches it per component and sets MPC_Wind's two scalars at runtime.

    MPC_Wind.Strength   x every amplitude below (1 = these numbers; 0 = still)
    MPC_Wind.Speed      x every frequency below (1 = these numbers)

DIRECTION is only the prevailing wind. Nothing is pushed straight along it:
the heading each thing is pushed along veers off it, by a field that drifts
over the ground (two crossing waves, so it changes in patches, not in
stripes) plus an angle of the instance's own (PerInstanceRandom). Two clumps
side by side lean a little apart, and one clump swings left and right of the
wind as the field passes over it. The gusts are two crossing wave trains
too, so a gust is a patch that travels, not a wall across the map.

    grass and bushes   (M_ProcFoliage) lean along their heading and sway,
                       weighted by the vertex colour's alpha (0 at the root,
                       1 at the tip: foliage_meshes.py), in gusts that roll
                       across the field (crests every GRASS_WAVE_CM and
                       GRASS_CROSS_WAVE_CM, on GUST_HEADINGS)
    trees              (M_Master_Bark and M_Master_Foliage, so trunk,
                       branches and leaves bend together) bend by
                       (height / TREE_REF_HEIGHT_CM)^2 of the mesh's own
                       height above its trunk base, each tree on its own
                       phase (PerInstanceRandom), with slow gusts rolling
                       through the forest (crests every TREE_GUST_CM and
                       TREE_CROSS_GUST_CM). A tree also rocks across its
                       heading (TREE_CROSS_SWAY of its own sway, at another
                       rate), so its top draws a loop and not a line
    leaves             (M_Master_Foliage alone) flutter on top, mostly up
                       and down, ramping in over the first LEAF_REF_CM

Angles are in turns (1 = 360 degrees), like every phase here.

Frequencies are in cycles per second and wave numbers in cycles per cm: a
material Sine with its default period of 1 takes cycles.

A speed nudge restarts nothing but moves every phase (time x speed), so the
sway jumps once when the speed changes. Strength scales smoothly.
"""

import math

# /Game/Forest/Materials holds the masters it patches; the collection sits
# beside them.
MPC_DIR = "/Game/Forest/Materials"
MPC_NAME = "MPC_Wind"
MPC_PATH = f"{MPC_DIR}/{MPC_NAME}"
PARAM_STRENGTH = "Strength"
PARAM_SPEED = "Speed"
MPC_DEFAULTS = {PARAM_STRENGTH: 1.0, PARAM_SPEED: 1.0}

# The materials with wind, and which part each carries.
PROC_FOLIAGE = "/Game/Forest/Procedural/M_ProcFoliage"   # grass, rebuilt whole
MASTER_BARK = "/Game/Forest/Materials/M_Master_Bark"     # sway, patched
MASTER_FOLIAGE = "/Game/Forest/Materials/M_Master_Foliage"   # sway + flutter, patched
# Every expression the wind adds to a patched master carries this desc, so a
# re-run deletes exactly those and nothing of the master's own.
EXPR_TAG = "OW_Wind"

DIRECTION = (0.8, 0.6, 0.0)          # the prevailing wind: unit, on the ground
CROSSWIND = (-DIRECTION[1], DIRECTION[0], 0.0)   # 90 degrees left of it


def heading(turns):
    """The unit vector ``turns`` round from DIRECTION, on the ground."""
    c, s = math.cos(2 * math.pi * turns), math.sin(2 * math.pi * turns)
    return tuple(c * d + s * x for d, x in zip(DIRECTION, CROSSWIND))


# The two wave trains every gust and every veer field is the sum of: what
# share of it each carries, and the heading it travels on. Both run downwind,
# 100 degrees apart, so their crests cross.
GUST_HEADINGS = ((0.6, heading(-0.10)), (0.4, heading(0.18)))
# The second train's rate, as a multiple of the first's: never in step.
CROSS_RATE = 1.37

GRASS_AMP_CM = 8.0       # a tip's reach at strength 1
GRASS_SWAY_HZ = 0.45
GRASS_WAVE_CM = 600.0
GRASS_CROSS_WAVE_CM = 430.0
GRASS_FLUTTER_HZ = 1.7
GRASS_FLUTTER = 0.2      # of the amplitude
# How far a clump's heading swings off the prevailing wind: the drifting
# field's share (crests every GRASS_VEER_CM and GRASS_CROSS_VEER_CM, turning
# at GRASS_VEER_HZ) and the clump's own fixed share, each way.
GRASS_VEER_TURNS = 0.11          # 40 degrees
GRASS_SCATTER_TURNS = 0.07       # 25 degrees
GRASS_VEER_HZ = 0.13
GRASS_VEER_CM = 900.0
GRASS_CROSS_VEER_CM = 1400.0

TREE_REF_HEIGHT_CM = 1500.0
TREE_AMP_CM = 30.0       # at TREE_REF_HEIGHT_CM, strength 1
TREE_SWAY_HZ = 0.22
TREE_GUST_HZ = 0.07
TREE_GUST_CM = 4000.0
TREE_CROSS_GUST_CM = 2900.0
TREE_OWN_SWAY = 0.3      # of the amplitude: the tree's own rocking
TREE_CROSS_SWAY = 0.5    # of that, across its heading
TREE_CROSS_SWAY_RATE = 0.81      # x TREE_SWAY_HZ
# A tree's heading, as the grass's. The field is far wider than a crown, so
# a tree turns whole and is not wrung.
TREE_VEER_TURNS = 0.07           # 25 degrees
TREE_SCATTER_TURNS = 0.06        # 22 degrees
TREE_VEER_HZ = 0.05
TREE_VEER_CM = 7000.0
TREE_CROSS_VEER_CM = 11000.0

LEAF_AMP_CM = 3.0
LEAF_HZ = 2.4
LEAF_REF_CM = 300.0
LEAF_AXIS = (0.25, 0.2, 1.0)
# Per-leaf phase: cycles per cm along each axis, so neighbouring leaves differ.
LEAF_SCATTER = (0.013, 0.017, 0.011)

# The tuner's strength stat tops out at 500%: the bound a material's WPO is
# clamped to (and Nanite's culling bounds grow by), with room for that.
MAX_STRENGTH = 5.0
GRASS_MAX_DISPLACEMENT_CM = GRASS_AMP_CM * (1 + GRASS_FLUTTER) * MAX_STRENGTH
TREE_MAX_DISPLACEMENT_CM = (
    TREE_AMP_CM * (1 + TREE_OWN_SWAY * TREE_CROSS_SWAY) + LEAF_AMP_CM) * MAX_STRENGTH
