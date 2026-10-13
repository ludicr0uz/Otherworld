"""The long gun's carry pose: its names and numbers. Constants only; the anim
graph is carry_pose.py, the weights' targets weapon_component/carry_weights.py.
"""

# The weapon layers' weights (anim_vars.CARRY), eased by the weapon component
# on every machine's copy. CarryPose is how far the upper body is in the
# carry: a long gun in hand that nothing holds up, standing. CarrySprint is
# how far the carry is the sprint's.
CARRY_POSE = "CarryPose"
CARRY_SPRINT = "CarrySprint"
# FInterpTo speeds. The carry comes in and goes out with the ready pose's own
# blend (a montage's, 0.2 s or so), so the two cross over; the sprint's takes
# the stride or two the legs take to get there.
CARRY_BLEND_SPEED = 10.0
CARRY_SPRINT_BLEND_SPEED = 6.0
# The ground speed at which the carry is the jog's clip whole (cm/s): under
# it, standing and walking, the standing clip is blended in. Not the tuned
# jog speed (a menu row, 0.5 to 4 m/s): a walk is half way there.
CARRY_JOG_FULL_CM_S = 250.0
# The same for the crouched carry's walk: the crouch goes at 0.45 of the jog
# (180 cm/s at the default pace), and half of that is already a walk.
CARRY_CROUCH_WALK_FULL_CM_S = 120.0

# BP_WeaponComponent's CarryFor: the ready pose whose guns are carried so (the
# rifle's, which the sniper and the shotgun are held in too). HandPose is
# compared with it, which every machine's copy has (look.py).
CARRY_FOR_VAR = "CarryFor"
