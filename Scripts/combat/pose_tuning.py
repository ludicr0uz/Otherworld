"""How often a dedicated server poses a body it never draws (task A4).
Constants only; the C++ is Source/Otherworld/Public/OtherworldServerPose.h,
the one node that hands it these server_pose.py's.

A server judges shots against a body's bones and fires from the gun in its
hand, so it must pose every body; it draws none, so it need not pose one
thirty times a second. The hit history keeps the poses it is given and blends
between them (OtherworldHitHistory.h), so a shot at a body posed ten times a
second is still judged against where its limbs were.
"""

from net.relevancy_consts import CHARACTER

# Within this of another player's body (a load test's bot counts as one), a
# body is posed every frame: this is where a shot is a matter of a limb.
FULL_WITHIN_CM = 3000.0
# Further than that from every player: this often, and blended between.
FAR_HZ = 10.0
# Nobody is near: no client is even sent a body further than the characters'
# relevancy distance from it (net/relevancy_consts.py), so nobody can be
# aiming at it. A ragdoll is posed at this rate too, wherever it lies: its
# bodies are the physics', and its capsule stops no pellet.
NOBODY_BEYOND_CM = CHARACTER.cull_m * 100.0
NOBODY_HZ = 2.0
