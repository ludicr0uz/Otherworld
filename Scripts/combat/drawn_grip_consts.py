"""The names and numbers of the drawn MetaHuman's grip (drawn_grip*.py): the
clip of fitted hands, the frames in it, each gun's trigger, and the
variables that choose and weigh them.

Pure constants: no ``unreal``.
"""

# The clip of fitted hands, on the MetaHuman's skeleton: FRAMES_PER_GUN frames
# for each gun of GUNS, keyed at one frame a second so a frame's time is its
# number (drawn_grip_graph plays it by explicit time, never forward).
CLIP = "/Game/Sourced/MetaHuman/A_DrawnGrip"
CLIP_FPS = 1
# The guns, in the order of their frames: the five weapon_models.GUN_FINGERS
# fits, by their Blueprints (what the capture and the mesh are read by).
GUNS = ("BP_AssaultRifle", "BP_SniperRifle", "BP_Shotgun", "BP_Pistol", "BP_SMG")
# A gun's frames: its right hand with the left hand as the ready pose has it
# ("hold"), down the sights ("sights": the IK holds it on the support point,
# level and pitched), and in the carry's clips (a long gun lowered). The
# right hand is the same in all three (the gun is rigid in it).
FRAMES = ("hold", "sights", "carry")
FRAMES_PER_GUN = len(FRAMES)
# Which of probe_drawn_grip's states each frame is fitted against, and the
# state whose finger locals it starts from (the first). A handgun lowered is
# held in one hand: its "carry" frame is its "hold" (the weight is 0 there).
FRAME_STATES = {
    "hold": (("raised",), "raised"),
    "sights": (("ads level", "ads pitch up", "ads pitch down"), "ads level"),
    "carry": (("standing", "walking", "crouched", "sprinting"), "standing"),
}
HANDGUNS = ("BP_Pistol", "BP_SMG")

# Each gun's trigger in its actor's frame (cm, +X down the barrel, +Z up): a
# segment just in front of the trigger's face, in the gun's middle plane,
# read off sections of its mesh (y = 0). The fit draws the right index's pad
# to the nearest point of it, laid a finger_fit.SKIN_CM off the face
# (drawn_grip_bake.trigger). The shotgun's is under its receiver, 5 cm below
# the ready pose's index (combat/CLAUDE.md: its fist is on the stock's wrist).
TRIGGER = {
    "BP_AssaultRifle": ((6.3, 0.0, 4.2), (6.8, 0.0, 3.1)),
    "BP_SniperRifle": ((7.1, 0.0, 5.2), (7.5, 0.0, 4.0)),
    "BP_Shotgun": ((7.8, 0.0, -1.9), (8.0, 0.0, -2.9)),
    "BP_Pistol": ((5.6, 0.0, 3.1), (5.6, 0.0, 1.9)),
    "BP_SMG": ((5.0, 0.0, 3.4), (5.3, 0.0, 2.0)),
}
# Where the right thumb's tip rests on a gun whose thumb the retarget leaves
# standing up behind its slide, over the rear sight (combat/drawn_thumb.py):
# a segment beside the frame's left side (-Y), under the slide (its bottom
# at z 5.5 and its top at 7.5 on the 1911), laid a finger_fit.SKIN_CM off the
# mesh as the trigger's is. And how high the thumb's skin may rise there (the
# gun's +Z, cm): 1.5 cm under the slide's top, so the sights are clear.
THUMB_REST = {
    "BP_Pistol": ((0.0, -3.0, 4.2), (3.0, -3.0, 4.2)),
}
THUMB_CEILING_CM = 6.0
# probe_drawn_grip's bounds on it: the tip within THUMB_NEAR_CM of its rest
# (a skin off it), and no point of the thumb's skin above THUMB_CEILING_CM.
THUMB_NEAR_CM = 1.0
# probe_drawn_grip's bound on it: the index's pad within this of a skin off
# the trigger's face (cm); the shotgun's own, whose trigger is below the hand.
TRIGGER_NEAR_CM = 1.0
TRIGGER_NEAR_CM_BY_GUN = {"BP_Shotgun": 2.0}

# The fitted fingers in the running game (probe_drawn_grip), each finger's
# skin a finger_fit.SKIN_CM off its bones: no finger of a hand on the gun
# deeper in its mesh than PRESSED_CM raised or down the sights, or
# CARRY_PRESSED_CM in a long gun's carry, and none further off it than OFF_CM
# (CARRY_OFF_CM carried). The carry's are wider because its wrist is the
# clip's, not pinned to a seat, and one frame serves the carry's clips
# (standing, walking, jogging, crouched), which hold the hand apart: the fit
# keeps the fingers out of the gun in all of them, so crouched the shotgun's
# left little finger stands 1.7 cm off.
PRESSED_CM = 0.3
CARRY_PRESSED_CM = 1.5
OFF_CM = 1.0
CARRY_OFF_CM = 2.0
# A gun whose left hand's own knuckle is in its mesh where the wrist is pinned,
# raised, so that no turn of the finger's metacarpal (drawn_grip.fit_finger's
# cup and lift) brings the finger's first point out: the shotgun's little
# finger on the pump (0.44 cm, measured 15 Oct 2026) and the SMG's index on
# the magazine well (0.38). Down the sights both are clear.
PRESSED_CM_BY_GUN = {"BP_Shotgun": 0.5, "BP_SMG": 0.5}
# The fingers a long gun's carry leaves off it: the carry's clips (the Animation
# Starter Pack's, carry_pose.py) hold the left thumb along the side of the
# stock, 6 to 9 cm off the wood, and the wrist is the clip's there, not pinned
# to a seat; the thumb is fitted where it is clear, so nothing pulls it on.
CARRY_OFF = (("left", "thumb"),)

# The drawn anim Blueprint's variables, written from the weapon component's
# own on its Update: which gun (its frame block's first frame), the right
# hand's weight, the left's, and the two blends among the left's frames.
GRIP_GUN_VAR = "GripGun"
GRIP_RIGHT_VAR = "GripRight"
GRIP_LEFT_VAR = "GripLeft"
GRIP_SIGHTS_VAR = "GripSights"
GRIP_CARRY_VAR = "GripCarry"
