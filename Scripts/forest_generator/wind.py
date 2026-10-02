"""Wind in the grass and the trees: the numbers. Pure Python (no ``unreal``).

forest_import/wind.py writes them into the materials as world-position
offset (WPO); the graphics menu's tuner (graphics_menu/gfx_tuner_wind.py)
switches it per component and sets MPC_Wind's two scalars at runtime.

    MPC_Wind.Strength   x every amplitude below (1 = these numbers; 0 = still)
    MPC_Wind.Speed      x every frequency below (1 = these numbers)

What moves, all of it along DIRECTION (the wind's heading, on the ground):

    grass and bushes   (M_ProcFoliage) lean downwind and sway, weighted by
                       the vertex colour's alpha (0 at the root, 1 at the
                       tip: foliage_meshes.py), in waves that roll across
                       the field (a crest every GRASS_WAVE_CM)
    trees              (M_Master_Bark and M_Master_Foliage, so trunk,
                       branches and leaves bend together) bend by
                       (height / TREE_REF_HEIGHT_CM)^2 of the mesh's own
                       height above its trunk base, each tree on its own
                       phase (PerInstanceRandom), with slow gusts rolling
                       through the forest (a crest every TREE_GUST_CM)
    leaves             (M_Master_Foliage alone) flutter on top, mostly up
                       and down, ramping in over the first LEAF_REF_CM

Frequencies are in cycles per second and wave numbers in cycles per cm: a
material Sine with its default period of 1 takes cycles.

A speed nudge restarts nothing but moves every phase (time x speed), so the
sway jumps once when the speed changes. Strength scales smoothly.
"""

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

DIRECTION = (0.8, 0.6, 0.0)          # unit, on the ground

GRASS_AMP_CM = 8.0       # a tip's reach at strength 1
GRASS_SWAY_HZ = 0.45
GRASS_WAVE_CM = 600.0
GRASS_FLUTTER_HZ = 1.7
GRASS_FLUTTER = 0.2      # of the amplitude

TREE_REF_HEIGHT_CM = 1500.0
TREE_AMP_CM = 30.0       # at TREE_REF_HEIGHT_CM, strength 1
TREE_SWAY_HZ = 0.22
TREE_GUST_HZ = 0.07
TREE_GUST_CM = 4000.0

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
TREE_MAX_DISPLACEMENT_CM = (TREE_AMP_CM + LEAF_AMP_CM) * MAX_STRENGTH
