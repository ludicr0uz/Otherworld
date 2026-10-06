"""uebp.nodes.move -- the game's own movement library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldMovementLibrary.h). Each takes the
character's actor on its ``Character`` pin, so a graph needs no cast.
"""

MOVE_LIBRARY = "/Script/Otherworld.OtherworldMovementLibrary"

# The wants: called where the player's keys are read (the local gate).
FN_SET_SPRINT_HELD = MOVE_LIBRARY + ".SetSprintHeld"
FN_SET_STANCE = MOVE_LIBRARY + ".SetStance"
FN_SET_AIM_WALK = MOVE_LIBRARY + ".SetAimWalk"

# The state the movement made of them.
# 0 stand, 1 crouch, 2 prone, on any machine (a simulated copy included).
FN_GET_STANCE = MOVE_LIBRARY + ".GetStance"
FN_GET_STAMINA = MOVE_LIBRARY + ".GetStamina"
FN_IS_SPRINTING = MOVE_LIBRARY + ".IsSprinting"
FN_IS_SPRINT_SPENT = MOVE_LIBRARY + ".IsSprintSpent"
FN_IS_SPRINT_AHEAD = MOVE_LIBRARY + ".IsSprintAhead"

# The server's alone (and single player's): nothing on a client.
FN_SET_STAMINA = MOVE_LIBRARY + ".SetStamina"
FN_SPEND_STAMINA = MOVE_LIBRARY + ".SpendStamina"
FN_SET_PACE = MOVE_LIBRARY + ".SetPace"
