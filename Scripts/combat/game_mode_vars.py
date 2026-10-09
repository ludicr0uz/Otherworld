"""What the builders add to BP_ThirdPersonGameMode's member variables, named
once: each row is the name and the pin type (uebp/vars.py). game_state.py
declares TABLE, and says what each is for; all start at zero or false, bar
the two the builder writes.

Server-only state: a client never reads the GameMode (net/state_consts.py
has what moved to the PlayerState and the GameState).
"""

from uebp.vars import BOOL, FLOAT, INT, VECTOR, Var, struct

_STREAM = struct("/Script/CoreUObject.RandomStream")

# The wanderers' numbers, handed out in spawn order.
NpcSpawnCount = Var("NpcSpawnCount", INT)
# The developer switch behind the [COMBAT-TRACE] lines.
CombatTrace = Var("CombatTrace", BOOL)
# The gun drop's two random streams (gun_drop.py) and whether they have been
# seeded this session.
GunDropSeeded = Var("GunDropSeeded", BOOL)
GunDropRollStream = Var("GunDropRollStream", _STREAM)
GunDropPickStream = Var("GunDropPickStream", _STREAM)
# The last noise the player made, for the wanderers to hear (noise.py).
NoiseTime = Var("NoiseTime", FLOAT)
NoiseLocation = Var("NoiseLocation", VECTOR)
NoiseRange = Var("NoiseRange", FLOAT)
NoiseDirection = Var("NoiseDirection", VECTOR)
NoiseConeRange = Var("NoiseConeRange", FLOAT)
NoiseConeCos = Var("NoiseConeCos", FLOAT)
NOISE_FLOATS = (NoiseTime, NoiseRange, NoiseConeRange, NoiseConeCos)
NOISE_VECTORS = (NoiseLocation, NoiseDirection)

# In the order they have always been declared.
TABLE = (NpcSpawnCount, CombatTrace, GunDropSeeded, *NOISE_FLOATS, *NOISE_VECTORS,
         GunDropRollStream, GunDropPickStream)
