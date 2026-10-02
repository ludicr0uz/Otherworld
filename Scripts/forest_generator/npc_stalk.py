"""How a wendigo hunts: it roars, comes in round the player from tree to
tree, hiding behind each, and charges once it is close.

Constants only -- no `unreal` import -- like npc_placement.py, npc_agro.py and
npc_strafe.py. The builder is Scripts/npc/stalk.py (the step) and
stalk_cover.py (the next tree), the checks Scripts/npc/verify_stalk.py and, in
the game, Scripts/probes/probe_wendigo_stalk.py.

The hunt is the tree's Stalk step, tried before Chase while the wanderer is
aggro. In order:

  roar    the first pass: it stops, faces the player, and plays its roar clip
          and one of its voices. It stands for NPC_STALK_ROAR_S.
  catch up  further from the player than NPC_STALK_CATCH_UP_CM there is no
          arc and no tree: it runs straight at them, at the speed of a leg,
          and hunts from where that brings it.
  stalk   one leg at a time. A leg ends behind a tree that is closer to the
          player than the wendigo is, and round them from where it stands:
          the path is an arc that closes in. It runs there, faster than it
          chases (NPC_STALK_RUN_SCALE), waits NPC_STALK_HIDE_*_S behind the
          trunk, and picks the next. A leg with no tree to end at is not
          waited at, nor run to its end: NPC_STALK_OPEN_ARRIVE_CM short of
          it the next is picked, so in the open it never stops running.
          The way round is a coin at the roar,
          turned about every NPC_STALK_TURN_*_S: the first leg picked once
          that time is up goes the other way.
  charge  within NPC_STALK_CHARGE_CM the step fails for good, and the tree
          falls through to the ordinary Chase: straight at the player. It
          charges from further off too, rather than stand: when a leg has
          nowhere to end, or it is not moving half a second into one.
  rage    a wendigo the player has hurt (a shot, a blade, a fist: the hurt
          sense's own flag) is Enraged, for good: the step fails first
          thing, with one of its voices the once, so there is no roar, no
          tree and no arc, only the charge. Fire still holds it off
          (npc_ward.py), and after a flight it comes straight back.

FINDING THE TREE. A sphere is swept along a line that points at the player,
NPC_STALK_ARC_DEG round them from the wendigo, from NPC_STALK_ADVANCE_MIN_CM
closer than it stands to NPC_STALK_ADVANCE_MAX_CM closer (never nearer the
player than NPC_STALK_COVER_MIN_CM). The first tree it strikes is the next
cover, and the spot is NPC_STALK_BEHIND_CM past its trunk, seen from the
player. The sphere may have touched no more than the tree's crown, metres
from the trunk, so the spot itself is then held to the same promise: at
least NPC_STALK_GAIN_MIN_CM closer than the wendigo stands, and no nearer
than NPC_STALK_COVER_MIN_CM.

WHAT HIDES IT. A trunk as wide as the wendigo, and nothing less: a sapling's
stem is a few centimetres across and its twigs are seen through. So a tree
is cover only if its trunk at chest height is NPC_STALK_TRUNK_MIN_CM wide,
which is its species' width there (NPC_STALK_TRUNK_CM, measured) times its
own scale: cover_trees() is the scale each mesh has to be. And a line from
the spot to the player has to strike that same tree: a trunk that leans off
its own foot hides nothing, and neither do the leaves of another tree
further off.
Each angle of NPC_STALK_ARC_DEG is tried in turn; with no cover on any of
them the leg ends in the open, NPC_STALK_OPEN_ADVANCE_CM closer on the
first, and is not waited at.

THE LAST TREE is outside the charge range, so every cover is one it reaches
and waits at. From there no closer tree is allowed, the next leg is in the
open, and that run takes it inside the range: the charge.
"""

from forest_generator.npc_placement import NPC_MELEE_RANGE_CM
from forest_generator.tree_placement import DEFAULT_TREE_SPECS

# Who hunts this way, and the clip it roars with: the Mixamo Scary pack's
# zombie scream, retargeted onto the creature by asset_pipeline/
# import_mixamo.py (which checks this literal against mixamo_paths.ROAR).
# A creature without a row chases as before.
NPC_STALK_ROAR = {
    "Wendigo": "/Game/Sourced/Mixamo/Wendigo01/A_Wendigo01_Mx_Scary_ZombieScream",
}

# How long it stands roaring before the first leg. The clip is 2.8 s; the
# last of it blends out as the wendigo sets off.
NPC_STALK_ROAR_S = 2.4
NPC_STALK_ROAR_BLEND_S = 0.2

# Inside this it stops hiding and runs straight at the player. About a second
# and a half of running: close enough that the last tree is a real hiding
# place, far enough that the charge is seen coming.
NPC_STALK_CHARGE_CM = 1000.0

# Round the player per leg, from where the wendigo stands, tried in this
# order. Four or five legs of the first is about a semicircle.
NPC_STALK_ARC_DEG = (35.0, 50.0, 20.0)

# How fast it runs a leg, as a fraction of its run (the chase and the charge):
# the arc is the long way in, and at its run it was easy to keep in the
# sights. It was 1.3, about the player's sprint (900 cm/s); 30% on top of
# that, a tuned 690 cm/s comes to 1166: it outruns them.
NPC_STALK_RUN_SCALE = 1.69

# Further off than this (flat) it does not stalk: it runs straight at the
# player, at the speed of a leg, until it is inside.
NPC_STALK_CATCH_UP_CM = 15000.0

# The way round is turned about this long after the roar ends, and after
# each turn: one throw per turn. A leg and its wait are 3-8 s, so it is a
# leg or two, sometimes three, each way.
NPC_STALK_TURN_MIN_S = 4.0
NPC_STALK_TURN_MAX_S = 9.0

# How much closer to the player a leg's tree may be.
NPC_STALK_ADVANCE_MIN_CM = 300.0
NPC_STALK_ADVANCE_MAX_CM = 1800.0
# ...and never a spot nearer the player than this: outside the charge range,
# with room for the run round a trunk, or it would charge on its way there.
NPC_STALK_COVER_MIN_CM = 1200.0
# A spot counts only if it is this much closer than the wendigo stands.
NPC_STALK_GAIN_MIN_CM = 100.0
# With no tree to be had, the leg ends this much closer, in the open.
NPC_STALK_OPEN_ADVANCE_CM = 600.0

# The sweep: a sphere this wide, its centre this far above the wendigo's own.
# The ground it stands on and its own body are ignored, so the sphere can be
# wide enough to find a trunk a few metres either side of the line. Both the
# reach above and this were half as much again smaller (12 m, 2 m).
NPC_STALK_SWEEP_RADIUS_CM = 300.0
NPC_STALK_SWEEP_LIFT_CM = 60.0

# Where it stands: this far past the trunk's centre, seen from the player.
# Clear of the trunk (TRUNK_CLEARANCE_CM is for a spawn, in the open) and
# still in its shadow.
NPC_STALK_BEHIND_CM = 170.0
# The spot is snapped onto the navmesh within this box; one that is not on
# it is no cover.
NPC_STALK_NAV_EXTENT_CM = (100.0, 100.0, 400.0)
# A spot in the open has no trunk to stay behind, and its height is a guess
# (the wendigo's own): a wider, taller box.
NPC_STALK_OPEN_NAV_EXTENT_CM = (200.0, 200.0, 600.0)

# A leg is over when the wendigo is within this of its spot (flat distance)...
NPC_STALK_ARRIVE_CM = 150.0
# ...and one that ends in the open this far short of it: more than it runs
# between two passes of the tree (half a second), so the next leg is picked
# while it is still running, and it does not stop.
NPC_STALK_OPEN_ARRIVE_CM = 700.0
# ...or has been running this long (a spot further off than it looked).
NPC_STALK_LEG_TIMEOUT_S = 6.0
# Slower than this, flat, on the pass after a move order (half a second on):
# it has no path, and charges.
NPC_STALK_STALLED_CMS = 20.0
# How long it waits behind a trunk before the next leg.
NPC_STALK_HIDE_MIN_S = 1.0
NPC_STALK_HIDE_MAX_S = 2.5

# How wide a trunk has to be, at chest height, to hide a wendigo.
NPC_STALK_TRUNK_MIN_CM = 45.0
# How wide each species' trunk is there at scale 1, by its TreeSpec's name
# (tree_placement.DEFAULT_TREE_SPECS): what a line trace across the trunk
# 90 cm up measured, over five trees of each on Lvl_Forest_200m, divided by
# the tree's scale. The island trees fork low and lean, so theirs is the
# median. A new species needs a row (the verifier checks), measured the same
# way; one without a row is no cover.
NPC_STALK_TRUNK_CM = {
    "HISM_Tree_Fir_A": 24.0,
    "HISM_Tree_Leafy_Island_01": 24.0,
    "HISM_Tree_Leafy_Island_02": 26.0,
    "HISM_Tree_Deciduous": 14.0,
    "HISM_Tree_Pine_A": 1.2,
}
# The one that is never cover, whatever its scale: the verifier's example.
NPC_STALK_SAPLING = "HISM_Tree_Pine_A"


def cover_trees(specs=DEFAULT_TREE_SPECS):
    """``[(mesh object path, the least scale at which its trunk is cover)]``,
    for the meshes ``specs`` plant that can be cover at all: a species whose
    largest tree is still too thin is left out."""
    found = []
    for spec in specs:
        width = NPC_STALK_TRUNK_CM.get(spec.name)
        if width and NPC_STALK_TRUNK_MIN_CM / width <= spec.scale_max:
            found.append((spec.mesh_path, round(NPC_STALK_TRUNK_MIN_CM / width, 3)))
    return found


assert NPC_MELEE_RANGE_CM < NPC_STALK_CHARGE_CM < NPC_STALK_COVER_MIN_CM
assert NPC_STALK_CHARGE_CM < NPC_STALK_CATCH_UP_CM
assert NPC_STALK_ARRIVE_CM < NPC_STALK_OPEN_ARRIVE_CM
assert cover_trees()
# A run in the open from the nearest cover there can be ends inside the
# charge range.
assert NPC_STALK_COVER_MIN_CM - NPC_STALK_OPEN_ADVANCE_CM < NPC_STALK_CHARGE_CM
assert 0.0 < NPC_STALK_GAIN_MIN_CM < NPC_STALK_ADVANCE_MIN_CM
assert NPC_STALK_ADVANCE_MIN_CM < NPC_STALK_OPEN_ADVANCE_CM < NPC_STALK_ADVANCE_MAX_CM
assert NPC_STALK_HIDE_MIN_S < NPC_STALK_HIDE_MAX_S < NPC_STALK_LEG_TIMEOUT_S
assert NPC_STALK_ARRIVE_CM < NPC_STALK_BEHIND_CM
assert NPC_STALK_RUN_SCALE > 1.0
assert 0.0 < NPC_STALK_TURN_MIN_S < NPC_STALK_TURN_MAX_S
