"""The throw's numbers: speed, angle, where it leaves from, the gravity the arc
and the flight share, how the arc is drawn and how an item comes to rest.
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
# The tip is per item: THROW_PITCH_UP_DEG is BP_WeaponItem's default for
# THROW_PITCH_VAR, which the launch reads off Held. A gun's own is its
# gun_tuning.csv `throw_arc` cell, tuned on the GUN TUNING tab; the knife, the
# food and the water keep the default.
THROW_SPEED = 1100.0            # cm/s at release
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
