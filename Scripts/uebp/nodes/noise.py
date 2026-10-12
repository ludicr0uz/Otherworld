"""uebp.nodes.noise -- the game's own noise list (C++, the Otherworld module:
Source/Otherworld/Public/OtherworldNoise.h). The recent noises the wanderers
can hear, the server's alone: one node writes one (combat/noise.py), one asks
whether a listener hears any (npc/senses.py). Task M28.
"""

NOISE_LIBRARY = "/Script/Otherworld.OtherworldNoiseLibrary"

# Maker, Location, Reach, Direction, ConeReach, ConeCos, HoldSeconds. Lands
# only with authority; replaces only its maker's own noise, and that only if
# it is stale or no louder.
FN_MAKE_NOISE = NOISE_LIBRARY + ".MakeNoise"
# Listener, HearingScale, HoldSeconds -> ReturnValue (heard), Maker (a pawn,
# or none), Location: the nearest noise that reaches the listener.
FN_HEAR_NOISE = NOISE_LIBRARY + ".HearNoise"
# For the probes: the list as it stands, and what has landed and been refused.
FN_NOISES_HELD = NOISE_LIBRARY + ".NoisesHeld"
FN_NOISES_MADE = NOISE_LIBRARY + ".NoisesMade"
FN_NOISES_REFUSED = NOISE_LIBRARY + ".NoisesRefused"
