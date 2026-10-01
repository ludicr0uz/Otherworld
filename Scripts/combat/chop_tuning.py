"""Chopping a tree for wood: the numbers and the names (the graph is
weapon_component/chop.py, the item wood.py).

A tree gives a piece of wood every CHOPS_PER_WOOD blows of the axe, and never
runs out: a tree is one instance of a level-wide instanced mesh, which the game
cannot fell or mark. The count belongs to the tree being cut (ChopTree +
ChopItem), so turning to another tree starts over.
"""

CHOPS_VAR = "Chops"            # on BP_WeaponItem: its blow bites a tree (the axe)

CHOPS_PER_WOOD = 3             # blows on one tree for one piece of wood

# Where the wood lands, from the point of the trunk the axe struck: out towards
# the player and turned to one side or the other, so it lies beside the trunk
# and not under the player's feet. Under 90 degrees: past that the point swings
# back round into a thick trunk.
WOOD_OUT_CM = 80.0
WOOD_SIDE_DEG = (40.0, 80.0)
WOOD_GROUND_CM = 400.0         # how far below the blow the ground is looked for
WOOD_LIFT_CM = 3.5             # the log's half thickness: it rests on the ground
# BP_Wood stands on end in its own frame (wood.py says why); the spawn tips it
# over, so what the tree gives lies flat, at a random heading.
WOOD_LIE_PITCH_DEG = 90.0

# The component's variables.
CHOP_TREE_VAR = "ChopTree"     # the instanced mesh component last struck
CHOP_ITEM_VAR = "ChopItem"     # ...and which of its instances
CHOP_COUNT_VAR = "ChopCount"   # blows landed on that tree since its last wood
WOOD_SPOT_VAR = "WoodSpot"     # where this piece lands, before the ground trace
WOOD_CLASS_VAR = "WoodClass"   # BP_Wood, a default set by build.py
