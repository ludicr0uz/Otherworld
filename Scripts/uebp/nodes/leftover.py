"""uebp.nodes.leftover -- the game's own list of what is left in the world
(C++, the Otherworld module: Source/Otherworld/Public/OtherworldLeftovers.h).
A server's cleanup rule for what players leave behind: a lifetime and a cap
per kind (net/leftover.py authors the nodes, net/leftover_consts.py holds the
numbers). Task M31.
"""

LEFTOVER_LIBRARY = "/Script/Otherworld.OtherworldLeftoverLibrary"

# Actor (the graph's own actor when empty), Kind, LifetimeSeconds, Cap: the
# actor is left in the world from now. Noted on a server alone, and never a
# level actor.
FN_LEFT_IN_WORLD = LEFTOVER_LIBRARY + ".LeftInWorld"
# Actor: no longer left (taken into an inventory).
FN_TAKEN_FROM_WORLD = LEFTOVER_LIBRARY + ".TakenFromWorld"
# For the probes: how many of a Kind are left, the lifetime an actor was
# noted with (-1: not noted), and how many were destroyed by each rule.
FN_LEFT_COUNT = LEFTOVER_LIBRARY + ".LeftCount"
FN_LEFT_LIFETIME = LEFTOVER_LIBRARY + ".LeftLifetime"
FN_LEFT_EXPIRED = LEFTOVER_LIBRARY + ".LeftExpired"
FN_LEFT_EVICTED = LEFTOVER_LIBRARY + ".LeftEvicted"
