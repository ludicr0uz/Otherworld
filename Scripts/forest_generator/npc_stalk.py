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
  stalk   one leg at a time. A leg ends behind a tree that is closer to the
          player than the wendigo is, and round them from where it stands:
          the path is an arc that closes in. It runs there, faster than it
          chases (NPC_STALK_RUN_SCALE), waits NPC_STALK_HIDE_*_S behind the
          trunk, and picks the next. The way round is a coin at the roar,
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
than NPC_STALK_COVER_MIN_CM. And a line from it to the player has to strike
a tree: a sapling, or a trunk that leans off its own foot, hides nothing.
Each angle of NPC_STALK_ARC_DEG is tried in turn; with no cover on any of
them the leg ends in the open, NPC_STALK_OPEN_ADVANCE_CM closer on the
first, and is not waited at.

THE LAST TREE is outside the charge range, so every cover is one it reaches
and waits at. From there no closer tree is allowed, the next leg is in the
open, and that run takes it inside the range: the charge.
"""

from forest_generator.npc_placement import NPC_MELEE_RANGE_CM

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
# sights. A tuned 690 cm/s comes to about the player's sprint (900).
NPC_STALK_RUN_SCALE = 1.3

# The way round is turned about this long after the roar ends, and after
# each turn: one throw per turn. A leg and its wait are 3-8 s, so it is a
# leg or two, sometimes three, each way.
NPC_STALK_TURN_MIN_S = 4.0
NPC_STALK_TURN_MAX_S = 9.0

# How much closer to the player a leg's tree may be.
NPC_STALK_ADVANCE_MIN_CM = 300.0
NPC_STALK_ADVANCE_MAX_CM = 1200.0
# ...and never a spot nearer the player than this: outside the charge range,
# with room for the run round a trunk, or it would charge on its way there.
NPC_STALK_COVER_MIN_CM = 1200.0
# A spot counts only if it is this much closer than the wendigo stands.
NPC_STALK_GAIN_MIN_CM = 100.0
# With no tree to be had, the leg ends this much closer, in the open.
NPC_STALK_OPEN_ADVANCE_CM = 600.0

# The sweep: a sphere this wide, its centre this far above the wendigo's own.
# The ground it stands on and its own body are ignored, so the sphere can be
# wide enough to find a trunk a few metres either side of the line.
NPC_STALK_SWEEP_RADIUS_CM = 200.0
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
# ...or has been running this long (a spot further off than it looked).
NPC_STALK_LEG_TIMEOUT_S = 6.0
# Slower than this, flat, on the pass after a move order (half a second on):
# it has no path, and charges.
NPC_STALK_STALLED_CMS = 20.0
# How long it waits behind a trunk before the next leg.
NPC_STALK_HIDE_MIN_S = 1.0
NPC_STALK_HIDE_MAX_S = 2.5

assert NPC_MELEE_RANGE_CM < NPC_STALK_CHARGE_CM < NPC_STALK_COVER_MIN_CM
# A run in the open from the nearest cover there can be ends inside the
# charge range.
assert NPC_STALK_COVER_MIN_CM - NPC_STALK_OPEN_ADVANCE_CM < NPC_STALK_CHARGE_CM
assert 0.0 < NPC_STALK_GAIN_MIN_CM < NPC_STALK_ADVANCE_MIN_CM
assert NPC_STALK_ADVANCE_MIN_CM < NPC_STALK_OPEN_ADVANCE_CM < NPC_STALK_ADVANCE_MAX_CM
assert NPC_STALK_HIDE_MIN_S < NPC_STALK_HIDE_MAX_S < NPC_STALK_LEG_TIMEOUT_S
assert NPC_STALK_ARRIVE_CM < NPC_STALK_BEHIND_CM
assert NPC_STALK_RUN_SCALE > 1.0
assert 0.0 < NPC_STALK_TURN_MIN_S < NPC_STALK_TURN_MAX_S
