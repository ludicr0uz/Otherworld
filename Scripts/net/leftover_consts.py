"""One table of what a server does with each kind of thing left in the world
(task M31): how long it lies there, and how many of the kind may exist. A
server runs for days and players arrive at any time, so what was left must be
there for a latecomer and must not pile up without limit. The builders write
a row onto the node that notes the actor (net/leftover.py); the server's list
(Source/Otherworld/Public/OtherworldLeftovers.h) destroys one at the end of
its lifetime, and the oldest of a kind while there are more than its cap.

In standalone nothing is noted: single player keeps what is left until it is
taken, as before (serversupportsysdesign.md 4.8, the mode table). A corpse
and a campfire have lifespans of their own in both modes (combat/death.py,
survival/tuning.py), so their rows hold only the cap.
"""

from collections import namedtuple

# kind: the name the server's list counts by. lifetime_s: seconds it lies
# there before the server destroys it (0: the actor's own lifespan). cap: the
# most of the kind a server keeps (the oldest goes first).
Leftover = namedtuple("Leftover", "kind lifetime_s cap")

# An item set down, thrown, lodged in a tree or a body, or cut from a tree.
# 20 minutes: long enough to come back for what was dropped in a fight, short
# enough that a day's play leaves nothing behind. 300: every lying item ticks
# on the server (about 2 us each, W0's trace), and 64 players leaving five
# things each are inside it.
ITEM = Leftover("Item", 1200.0, 300)
# A dead wanderer or a dead player's body: gone by its own CORPSE_SECONDS.
# The cap is for a massacre: a ragdoll is a skeletal mesh on every client
# near it.
CORPSE = Leftover("Corpse", 0.0, 48)
# A campfire: burns out by its own CAMPFIRE_BURN_S. One a player.
CAMPFIRE = Leftover("Campfire", 0.0, 64)

ROWS = (ITEM, CORPSE, CAMPFIRE)
