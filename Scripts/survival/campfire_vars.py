"""BP_Campfire's member variables, named once: each row is the name, the
pin type and the default (uebp/vars.py). campfire.py declares TABLE.
"""

from uebp.vars import FLOAT, Var
from survival.tuning import CAMPFIRE_WARM_PER_S, CAMPFIRE_WARM_RADIUS_CM

# How near a player is warmed, and by how much a second.
WarmRadius = Var("WarmRadius", FLOAT, CAMPFIRE_WARM_RADIUS_CM)
WarmPerSecond = Var("WarmPerSecond", FLOAT, CAMPFIRE_WARM_PER_S)

TABLE = (WarmRadius, WarmPerSecond)
