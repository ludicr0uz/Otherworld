"""Fire holds a wendigo off: while the player holds a lit stick out at it, it
does not attack. It circles, to come at them from the side or behind, and
after long enough of being held off it runs away.

Constants only -- no `unreal` import -- like npc_stalk.py and npc_strafe.py.
The builder is Scripts/npc/ward.py, the checks Scripts/npc/verify_ward.py
and, in the game, Scripts/probes/probe_wendigo_ward.py.

It is the tree's Ward step, tried before the attack (stalk, chase, swing)
while the wanderer is aggro:

  held off  the player holds fire out (FireWard on their weapon component),
            the wendigo is within NPC_WARD_RANGE_CM, and it stands within
            NPC_WARD_HALF_ANGLE_DEG of where the player faces. It does not
            swing. It circles them NPC_WARD_RING_CM off, NPC_WARD_ARC_DEG
            further round on every pass, facing them, one way round for the
            whole hold (the other way when something stops it).
  flanked   it has come further round than NPC_WARD_HALF_ANGLE_DEG: the
            fire is no longer between them, the step fails, and the attack
            runs. A player who turns with it holds it off again.
  flees     held off for NPC_WARD_HOLD_S in all (a break shorter than
            NPC_WARD_GRACE_S is the same hold), it runs straight away from
            the player for NPC_WARD_FLEE_S, and then hunts again from where
            that left it.
"""

from forest_generator.npc_placement import NPC_MELEE_RANGE_CM
from forest_generator.npc_stalk import NPC_STALK_CHARGE_CM

# Who is afraid of fire. A creature without a row walks through it.
NPC_WARD_FEARS = ("Wendigo",)

# The fire matters inside this, flat: a few strides, not the whole clearing.
NPC_WARD_RANGE_CM = 700.0
# "In front of" the player: this far either side of where their body faces.
# Further round than this and the wendigo has got past the fire.
NPC_WARD_HALF_ANGLE_DEG = 90.0

# Where it circles: this far from the player, out of its own reach...
NPC_WARD_RING_CM = 400.0
# ...this much further round them on each pass of the tree (half a second)...
NPC_WARD_ARC_DEG = 50.0
# ...at this share of its run: a prowl, quick enough to beat a slow turn.
NPC_WARD_SPEED_SCALE = 0.6
# Slower than this, flat, on a pass of a hold already under way: something
# is in its way (a trunk, a ledge), and it goes round the other way.
NPC_WARD_STALLED_CMS = 20.0

# Held off this long, it gives up and runs.
NPC_WARD_HOLD_S = 30.0
# A hold it broke (it got round, or the fire went down) and was back in
# within this is the same hold, and the count carries on.
NPC_WARD_GRACE_S = 2.0
# How long it runs, and how far ahead of itself each move order is put.
NPC_WARD_FLEE_S = 12.0
NPC_WARD_FLEE_STEP_CM = 1500.0
# The spot it runs to is snapped onto the navmesh within this box: tall,
# because its height is a guess (the wendigo's own) fifteen metres off.
NPC_WARD_FLEE_NAV_EXTENT_CM = (300.0, 300.0, 1000.0)

# Kept out of reach, and stopped before the ring.
assert NPC_MELEE_RANGE_CM < NPC_WARD_RING_CM < NPC_WARD_RANGE_CM
# A charge is under way before the fire can stop it.
assert NPC_WARD_RANGE_CM < NPC_STALK_CHARGE_CM
assert 0.0 < NPC_WARD_HALF_ANGLE_DEG < 180.0
assert 0.0 < NPC_WARD_ARC_DEG < NPC_WARD_HALF_ANGLE_DEG
assert 0.0 < NPC_WARD_SPEED_SCALE <= 1.0
assert 0.0 < NPC_WARD_GRACE_S < NPC_WARD_HOLD_S
