"""Lag compensation for shots (task M22): how far back the server judges a
remote shooter's shot. Constants only; the C++ is
Source/Otherworld/Public/OtherworldShotLibrary.h and OtherworldHitHistory.h,
the one node that uses them firing.py's pellet trace.

The server keeps one sample per frame of every character's capsule and
physics bodies, a second back. A shot from a client is traced against those
as they stood (its connection's round trip + EXTRA_REWIND_S) ago: the round
trip is how old the shooter's view of the server was plus how long its ask
took to arrive, and the extra is what its copy of another character lags
behind that (the engine's smoothing of a simulated proxy). A local shooter
(single player, a listen host's own player) gets no rewind at all: the same
two traces the graph had before.
"""

# The cap: no shot is judged further back than this, however slow the
# connection. A player on a worse line is at a disadvantage, not the one they
# shoot at.
MAX_REWIND_S = 0.4
# Added to the round trip: how far the shooter's view of another character
# lags the server's record of it beyond the network's own delay. Measured
# (probe_net_lag_hits, which prints per shot the rewind that would have put
# the shot where the shooter saw the chest): with 150 ms of lag the round
# trip read 170 ms and the shots wanted 140-225, about 180; without lag it
# read 33 and they wanted 25-55, about 40. Ten milliseconds over the trip
# sits in the middle of both.
EXTRA_REWIND_S = 0.01
