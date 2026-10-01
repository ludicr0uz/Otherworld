"""The carry's numbers and names: when a gun in hand is lowered and how long a
shot keeps it up. Constants only; the graph is weapon_component/carry.py.
"""

# A gun is carried lowered: the ready pose is not played, and the locomotion
# (idle, walk, jog) comes through the upper-body blend with the gun in the
# right hand, as it always has while sprinting. It is raised into its ready
# pose while an aim key or the guard is held, and by a shot or a reload.
#
# A shot or a reload keeps it up until this long after the gun could fire
# again (Held.NextFireTime, which both write). Long enough that the gun stays
# up between the shots of a fight and through a pump or a reload; short
# enough that it is down again a few strides after the last one.
CARRY_RAISE_HOLD_S = 1.5

# Where a shot starts while the gun is lowered. The first shot leaves on the
# frame of the click, before the gun is up, and the reticle's wall check runs
# on every frame it is down: from the real muzzle, at the knee and pointing at
# the ground, both would start at the feet (a round at a wanderer's chest went
# in 47 cm low, through its capsule). They start where the muzzle is about to
# be instead: this point, the fist of the ready pose in the body's frame
# (forward, right, up of the capsule's centre, cm), plus Held's MuzzleOffset.
# Measured standing (probes/probe_carry.py): the shotgun's fist is at
# (27, 18, 52) and the pistol's at (55, 14, 60). The nearer of the two is
# used, so the start is never past the real muzzle: a start 13 cm too far
# forward was inside a wanderer stood 150 cm away, and a trace that starts
# inside its target does not stop on it.
CARRY_GRIP = (27.0, 16.0, 54.0)

# BP_WeaponComponent's variables. Lowered is what the ready pose should
# reflect this frame: sprinting, or a gun nothing is holding up. PoseLowered
# is what it reflects now; the pair makes the change edge-triggered
# (weapon_component/ready_pose.py).
LOWERED_VAR = "Lowered"
POSE_LOWERED_VAR = "PoseLowered"
# A probe's stand-in for an aim key held: no key can be injected into a
# headless game. False in every real game.
RAISE_FORCED_VAR = "RaiseForced"
