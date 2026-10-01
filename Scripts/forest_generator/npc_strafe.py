"""What a hunting wanderer does between two swings: it gives ground and steps
round the player instead of standing where the last blow landed.

Constants only -- no `unreal` import -- like npc_placement.py and npc_agro.py.
The builder is Scripts/npc/strafe.py, the checks Scripts/npc/verify_strafe.py
and, in the game, Scripts/probes/probe_npc_strafe.py.

A swing arms the cooldown (TuneMeleeInterval). For the first NPC_STRAFE_SHARE
of it the Chase step sends the wanderer not at the player but to a point
NPC_STRAFE_*_DISTANCE_CM from them, NPC_STRAFE_*_ANGLE_DEG round from where
it stands, to the left or the right; it faces the player the whole way. The
rest of the cooldown is the ordinary chase, which brings it back into reach
as the next swing comes due -- so the swing rate is what it was.
"""

from forest_generator.npc_placement import (
    NPC_ACCEPTANCE_RADIUS_CM, NPC_MELEE_RANGE_CM,
)

# The part of the cooldown spent off the player. The remainder has to cover
# the run back in: 0.4 x 1.5 s at the run speed is 3.6 m, against a step out
# of under 3.
NPC_STRAFE_SHARE = 0.6

# How far from the player the step ends, centre to centre. Past the melee
# range, or backing off would be no more than a shuffle on the spot (the
# chase stops at NPC_ACCEPTANCE_RADIUS_CM); "slightly", so about a metre.
NPC_STRAFE_MIN_DISTANCE_CM = 210.0
NPC_STRAFE_MAX_DISTANCE_CM = 280.0

# How far round the player, from where the wanderer stands, either way.
NPC_STRAFE_MIN_ANGLE_DEG = 25.0
NPC_STRAFE_MAX_ANGLE_DEG = 60.0

# Of the run speed: a sidestep is a step, not a sprint.
NPC_STRAFE_SPEED_SCALE = 0.45

# A player further off than this has broken away, and is chased, not circled.
NPC_STRAFE_ENGAGE_CM = 450.0

assert NPC_ACCEPTANCE_RADIUS_CM < NPC_MELEE_RANGE_CM < NPC_STRAFE_MIN_DISTANCE_CM
assert NPC_STRAFE_MAX_DISTANCE_CM < NPC_STRAFE_ENGAGE_CM
assert 0.0 < NPC_STRAFE_SHARE < 1.0 and 0.0 < NPC_STRAFE_SPEED_SCALE < 1.0
