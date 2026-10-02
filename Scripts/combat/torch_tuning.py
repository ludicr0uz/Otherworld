"""The stick that burns: the numbers and the names (the item is stick.py, the
graph weapon_component/torch.py, the key weapon_component/use.py).

A stick used within reach of a campfire takes its fire and is a torch for
STICK_BURN_S, wherever it then is: in the hand, in the bag or on the ground.
Burnt out it is a stick again, and can be lit again. With a burning one in
hand the use key holds it out in front of the player, which is the FireWard a
creature afraid of fire reads (npc/ward.py).
"""

# On BP_WeaponItem.
BURNS_VAR = "Burns"                   # the use key lights it at a fire (the stick)
LIT_VAR = "Lit"                       # it is burning
BURN_OUT_VAR = "BurnOutTime"          # the world time its fire goes out
USE_POSE_VAR = "UsePose"              # the pose it is raised in while it wards

# How long a stick burns, and how near a campfire it has to be used to light
# (the player's middle to the fire's, flat or not: a strike of the matches
# puts the fire 130 cm ahead).
STICK_BURN_S = 120.0
STICK_LIGHT_RADIUS_CM = 300.0

# The component's variables.
STICK_CLASS_VAR = "StickClass"        # BP_Stick, issued at BeginPlay
NEAR_FIRE_VAR = "NearFire"            # this press found a campfire in reach
WARD_ITEM_VAR = "WardItem"            # the stick raised in its UsePose
WARD_CARRY_VAR = "WardCarryPose"      # its AimPose from before it was raised
