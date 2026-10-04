"""The glimmer over an item lying on the ground: its component's name, the
material's and the collection's paths, and the numbers of its look.

Constants only (no unreal import): glimmer.py builds from them, the world
package's Tick step writes the collection's scalar, and the verifiers and the
probe read the same table.
"""

from combat.paths import WEAPON_DIR

# The sprite on BP_WeaponItem (and on BP_AmmoPickup): a camera-facing quad
# drawn with MAT_ITEM_GLIMMER, shown only while the item is Dropped.
GLIMMER = "Glimmer"

MAT_ITEM_GLIMMER = f"{WEAPON_DIR}/M_ItemGlimmer"
MPC_NAME = "MPC_ItemGlimmer"
MPC_ITEM_GLIMMER = f"{WEAPON_DIR}/{MPC_NAME}"
MPC_OBJECT_PATH = f"{MPC_ITEM_GLIMMER}.{MPC_NAME}"
# The collection's one scalar: 1 = every glimmer shines, 0 = none does. The
# day/night cycle writes it from its ItemHighlight (world/item_highlight.py,
# the WORLD SETTINGS tab's row); as built it is on, so a level without a
# cycle still glimmers.
PARAM_HIGHLIGHT = "Highlight"
HIGHLIGHT_DEFAULT = 1.0

# Half the sprite's width and height, in cm: a glint about 18 cm across.
GLIMMER_HALF_SIZE_CM = 9.0
# The sprite is drawn this far above the item's origin and this far towards
# the camera, so the ground and the item's own model do not swallow it.
GLIMMER_LIFT_CM = 10.0
GLIMMER_PULL_CM = 12.0
# A pale gold, linear.
GLIMMER_COLOUR = (1.0, 0.86, 0.55)
# What the brightest texel emits at the top of a flash. The material divides
# the exposure out (EyeAdaptationInverse), so this reads the same under the
# noon sun and at midnight. It is added to what is behind it. At 8, with a
# 28 cm star resting at 0.3 of that, it was a lamp over every item in sight;
# at 2.5 and seen from any distance it was lost over sunlit ground, which is
# why it now shows only from close by.
GLIMMER_EMISSIVE = 3.0
# One flash every GLIMMER_PERIOD_S; between flashes it rests at
# GLIMMER_REST of the flash: 0, so the glint appears and is gone.
# GLIMMER_SHARPNESS narrows the flash.
GLIMMER_PERIOD_S = 3.0
GLIMMER_REST = 0.0
GLIMMER_SHARPNESS = 6.0
# How thin the star's four rays are: bigger = thinner.
GLIMMER_RAY_THIN = 7.0
# Only an item the character is near glimmers. The material measures from the
# camera (it has no way to know the pawn), which stands camera.CAMERA_ARM
# (2.6 m) behind the character: whole within GLIMMER_NEAR_CM of the camera,
# fading to nothing at GLIMMER_FAR_CM, so about 3 m and 6 m ahead of the
# character.
GLIMMER_NEAR_CM = 550.0
GLIMMER_FAR_CM = 850.0
