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
# And CarryAlso: the clips that are that pose with a gun's own fingers
# (finger_pose.py), which such a gun's HandPose is instead.
CARRY_ALSO_VAR = "CarryAlso"
# And CarrySeated: the fitted clips (finger_pose.clip_for) of the guns whose
# left hand the carry seats where it is down the sights (the support hand's
# IK, weapon_component/support_hand.py), CARRY_SEATED_GUNS' by Blueprint. The
# carry's clips hold a rifle's handguard: on the AK and the sniper the hand is
# within 2.4 to 4.6 cm of its seat, but on the shotgun it lay on the top of the
# receiver's front, 7 to 9 cm from the pump, so its fingers could only rest on
# the outside of the gun (drawn_grip_capture.json, 15 Oct 2026).
CARRY_SEATED_VAR = "CarrySeated"
CARRY_SEATED_GUNS = ("BP_Shotgun",)
