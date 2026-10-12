"""What the builders add to BP_ThirdPersonGameMode's member variables, named
once: each row is the name and the pin type (uebp/vars.py). game_state.py
declares TABLE, and says what each is for; all start at zero or false, bar
the two the builder writes.

Server-only state: a client never reads the GameMode (net/state_consts.py
has what moved to the PlayerState and the GameState).
"""

from uebp.vars import BOOL, INT, Var, struct

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
# What the GameMode held until M28: the one noise record. The noises are a
# list of the world's now (combat/noise.py); game_state removes these.
REMOVED = ("NoiseTime", "NoiseLocation", "NoiseRange", "NoiseDirection",
           "NoiseConeRange", "NoiseConeCos")

# In the order they have always been declared.
TABLE = (NpcSpawnCount, CombatTrace, GunDropSeeded, GunDropRollStream, GunDropPickStream)
