"""One table of what a server sends about each kind of actor, and how often
(task A2): the cull distance, within which a connection is sent the actor,
and the update rates. The builders write each row onto its class's defaults
(net/relevancy.py), and the server's replication graph reads them off the
CDOs (Source/Otherworld/Public/OtherworldReplicationGraph.h). The GameState
and the PlayerStates keep the engine's defaults: always relevant, at its
rates.

In standalone nothing is culled (there is one connection, none) and the
rates are read by no one: single player is untouched.
"""

from collections import namedtuple

# cull_m: how far, in metres, a player may be from the actor and still be
# sent it. update_hz / min_hz: the most and the least often a second the
# server considers the actor for a connection it is relevant to.
Relevancy = namedtuple("Relevancy", "cull_m update_hz min_hz")

# A player's character and a wanderer: seen from far, and in motion.
CHARACTER = Relevancy(cull_m=150.0, update_hz=30.0, min_hz=5.0)
# An item lying in the world: near, and still (dormant once it lies there).
ITEM = Relevancy(cull_m=60.0, update_hz=10.0, min_hz=1.0)
# A campfire: near, and lit once; it changes nothing after.
CAMPFIRE = Relevancy(cull_m=60.0, update_hz=10.0, min_hz=1.0)

M_TO_CM = 100.0


def cull_cm2(row):
    """The row's cull distance as the engine keeps it: cm, squared."""
    return (row.cull_m * M_TO_CM) ** 2


# The class defaults a row is written to, in the engine's Python names.
CULL_PROPERTY = "net_cull_distance_squared"
RATE_PROPERTY = "net_update_frequency"
MIN_RATE_PROPERTY = "min_net_update_frequency"
