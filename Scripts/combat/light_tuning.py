"""Lighting a campfire with matches: the numbers and the names (the graph is
weapon_component/light.py, the item matches.py).

A strike of the matches spends one piece of wood from the bag and leaves a
campfire on the ground in front of the player. The matches are never spent.
What a campfire is and does is survival's (survival/campfire.py): this package
only knows a class to spawn, which build_survival.py fills in.
"""

LIGHTS_VAR = "Lights"                 # on BP_WeaponItem: the fire key strikes it (the matches)

# Where the fire goes: this far in front of the player, on the ground found
# by a trace from above the spot to below it. With no ground (the map's
# edge) it is set down at the height of the player's feet.
CAMPFIRE_AHEAD_CM = 130.0
CAMPFIRE_TRACE_UP_CM = 60.0
CAMPFIRE_TRACE_DOWN_CM = 400.0
CAMPFIRE_FEET_CM = 90.0               # the player's middle above their feet

# The component's variables.
MATCHES_CLASS_VAR = "MatchesClass"    # BP_Matches, issued at BeginPlay
CAMPFIRE_CLASS_VAR = "CampfireClass"  # what a strike spawns; build_survival.py's
LIGHT_WOOD_VAR = "LightWood"          # the piece of wood this strike burns
