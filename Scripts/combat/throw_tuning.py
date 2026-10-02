"""The throw's numbers: speed, angle, where it leaves from, the gravity the arc
and the flight share, how the arc is drawn, how an item tumbles and comes to
rest, what a melee weapon's throw has of its own, what a thrown blade does to
a body and a tree, and when the throw's clip lets go.
Constants only. The throw key itself is THROW_KEY in tuning.py, beside the
other binds, because BIND_VARS lists it.
"""

# The throw (weapon_component/throw.py). The item leaves from a point in front
# of the chest, along the view tipped up a little, at one speed; the arc on
# screen and the flight are the same ballistic curve under the same gravity,
# so it lands where the arc said. 1100 cm/s tipped 30 degrees is a lob: it
# peaks about 1.5 m over the hand and carries a thrown item about 13 m over
# flat ground from a level view.
#
# The tip and the speed are per item: THROW_PITCH_UP_DEG and THROW_SPEED are
# BP_WeaponItem's defaults for THROW_PITCH_VAR and THROW_SPEED_VAR, which the
# launch reads off Held. A gun's own tip is its gun_tuning.csv `throw_arc`
# cell, tuned on the GUN TUNING tab; the food and the water keep the defaults,
# and a melee weapon has MELEE_THROW (below).
THROW_SPEED = 1100.0            # cm/s at release (the default speed)
THROW_SPEED_VAR = "ThrowSpeed"         # on BP_WeaponItem
THROW_PITCH_UP_DEG = 30.0       # added to the view's pitch (the default arc)
THROW_PITCH_COLUMN = "throw_arc"       # the spec / gun_tuning.csv column
THROW_PITCH_VAR = "ThrowArcDegrees"    # on BP_WeaponItem
THROW_MAX_PITCH_DEG = 80.0      # a throw straight up would land on the thrower
THROW_START_FORWARD = 60.0      # cm ahead of the capsule's centre: clear of it
THROW_START_UP = 50.0           # cm above it: about the shoulder
THROW_GRAVITY_Z = -980.0        # cm/s^2, the arc's and the flight's gravity
THROW_ARC_SIM_S = 3.0           # how far ahead the arc is predicted
THROW_ARC_HZ = 20.0             # dots per second of flight: ~55 cm apart
THROW_MAX_FLIGHT_S = 4.0        # a throw into nothing lands where it is by then
THROW_LAND_LIFT = 12.0          # cm above the ground it comes to rest
THROW_BOUNCE_BACK = 15.0        # cm back off a wall, before it drops to the ground
THROW_DOT_CM = 5.0              # each dot of the arc, across
THROW_MARK_CM = (36.0, 36.0, 3.0)   # the flat disc where the arc lands

# The tumble in the air (weapon_component/throw_flight.py): end over end, top
# first, about the level axis across the throw. 540 degrees a second is a turn
# and a half each second: a level throw's ~1.5 s flight turns a bit over twice,
# slow enough to read as the item it is. Per item too: the default for
# THROW_SPIN_VAR, which the flight reads off the item in the air.
THROW_SPIN_DEG_S = 540.0
THROW_SPIN_VAR = "ThrowSpinDegS"       # on BP_WeaponItem

# A melee weapon is thrown, not lobbed: hard and nearly flat, spinning forward
# like a throwing axe or a throwing knife. 1800 cm/s tipped 8 degrees rises
# about 30 cm over the hand and carries about 15 m over flat ground from a
# level view, in under a second, against the lob's 1.5 m rise over 13 m.
# THROW_EDGE_ON_VAR squares the item up as it leaves the hand: its own X along
# the throw and its Y level across it, so the plane its blade lies in (every
# melee model is built blade up, edge towards +X: knife.py, axe.py) is the
# plane it flies in, and the tumble about the across axis turns the blade
# forward over the handle, edge first. Three turns a second is a turn every
# 6 m of the flight.
THROW_MELEE_PITCH_UP_DEG = 8.0
THROW_MELEE_SPEED = 1800.0
THROW_MELEE_SPIN_DEG_S = 1080.0
THROW_EDGE_ON_VAR = "ThrowEdgeOn"      # on BP_WeaponItem, false by default
# What a melee item's builder adds to its defaults (knife.py, axe.py; a sword
# would too).
MELEE_THROW = {
    THROW_PITCH_VAR: THROW_MELEE_PITCH_UP_DEG,
    THROW_SPEED_VAR: THROW_MELEE_SPEED,
    THROW_SPIN_VAR: THROW_MELEE_SPIN_DEG_S,
    THROW_EDGE_ON_VAR: True,
}

# A thrown blade strikes (weapon_component/throw_strike.py). THROW_DAMAGE_VAR is
# what it takes off the first body its flight meets: 0 on the base item, so a
# thrown gun or mushroom does nothing, and more than the slash's 35 on a
# blade, since the throw costs the weapon until it is picked up again.
# Into a tree it lodges: turned by LODGE_TURN_VAR about its own level axis so
# that what goes into the wood (the knife's point, the axe's bit) leads along
# the flight, and set so that LODGE_POINT_VAR, a point of its own frame that
# deep behind the point or the bit, is on the bark (combat/lodge.py works both
# out of the model). Only within LODGE_MAX_HEIGHT_CM of the tree's foot: the
# pick-up reaches INTERACT_RADIUS (250 cm) from the player's middle, so a
# blade any higher could not be taken back; it falls to the foot instead.
THROW_DAMAGE_VAR = "ThrowDamage"       # on BP_WeaponItem, 0 by default
THROW_KNIFE_DAMAGE = 50.0
THROW_AXE_DAMAGE = 75.0
LODGE_TURN_VAR = "LodgeTurn"           # on BP_WeaponItem, a rotator
LODGE_POINT_VAR = "LodgePoint"         # on BP_WeaponItem
LODGE_MAX_HEIGHT_CM = 250.0
LODGE_KNIFE_DEPTH_CM = 7.0      # of the blade's 18.6 cm
LODGE_AXE_DEPTH_CM = 5.0        # of the head's 25 cm from bit to poll

# The clip (weapon_component/throw_windup.py): Quaternius UAL2's OverhandThrow,
# played at its own rate. THROW_RELEASE_S is where its hand lets go, measured
# off the clip on the adventurer: the right hand passes over the head at 0.30 s
# and at 0.35 s is 55 cm ahead of the body at shoulder height, which is the
# launch point (THROW_START_FORWARD, THROW_START_UP), before it comes down.
THROW_RELEASE_S = 0.35
THROW_ANIM_BLEND_S = 0.1
