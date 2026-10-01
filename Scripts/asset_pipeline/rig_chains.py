"""rig_chains -- the IK Rig chain tables: mannequin, Meshy, Mixamo and the
Quaternius UAL side by side.

Constants only.  Chain names are identical on both sides so the retargeter maps
them by exact string match (see build_retarget.py's docstring for why the chains
are written out by hand).
"""


# ─── Fingers ────────────────────────────────────────────────────────────────
#
# Meshy's rigger returns no finger bones; finger_rig.py adds them, named the
# Mixamo way the rest of the Meshy rig is named (LeftHandIndex1..3).  Three
# joints per finger on both sides.  The mannequin's metacarpals are left out of
# the chains: Meshy's palm is the hand bone itself, and a metacarpal only moves
# when the palm cups, which the hand bone already carries.
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")
FINGER_JOINTS = 3
# (mannequin suffix, Meshy side, mannequin hand, Meshy hand)
HANDS = (("l", "Left", "hand_l", "LeftHand"),
         ("r", "Right", "hand_r", "RightHand"))


def mannequin_finger_bone(finger, joint, suffix):
    return f"{finger.lower()}_{joint:02d}_{suffix}"


def meshy_finger_bone(finger, joint, side):
    return f"{side}Hand{finger}{joint}"


def meshy_finger_bones():
    """Every finger bone finger_rig.py adds, in parent-before-child order."""
    return [meshy_finger_bone(f, j, side) for _s, side, _mh, _h in HANDS
            for f in FINGERS for j in range(1, FINGER_JOINTS + 1)]


def _finger_chains(bone_of, meshy):
    return {f"{side}{f}": (bone_of(f, 1, side if meshy else suffix),
                           bone_of(f, FINGER_JOINTS, side if meshy else suffix))
            for suffix, side, _mh, _h in HANDS for f in FINGERS}


# name -> (start bone, end bone).  Identical keys on both sides: auto_map_chains
# then pairs them by exact string match and never has to guess.
CHAINS_MANNEQUIN = {
    "Spine":         ("spine_01", "spine_05"),
    "Neck":          ("neck_01", "neck_02"),
    "Head":          ("head", "head"),
    "LeftClavicle":  ("clavicle_l", "clavicle_l"),
    "LeftArm":       ("upperarm_l", "hand_l"),
    "RightClavicle": ("clavicle_r", "clavicle_r"),
    "RightArm":      ("upperarm_r", "hand_r"),
    "LeftLeg":       ("thigh_l", "ball_l"),
    "RightLeg":      ("thigh_r", "ball_r"),
    **_finger_chains(mannequin_finger_bone, meshy=False),
}

# Note the Spine entry: start Spine02 (the child of Hips), end Spine (the top).
# That is not a typo, it is Meshy's inverted numbering.
CHAINS_MESHY = {
    "Spine":         ("Spine02", "Spine"),
    "Neck":          ("neck", "neck"),
    "Head":          ("Head", "Head"),
    "LeftClavicle":  ("LeftShoulder", "LeftShoulder"),
    "LeftArm":       ("LeftArm", "LeftHand"),
    "RightClavicle": ("RightShoulder", "RightShoulder"),
    "RightArm":      ("RightArm", "RightHand"),
    "LeftLeg":       ("LeftUpLeg", "LeftToeBase"),
    "RightLeg":      ("RightUpLeg", "RightToeBase"),
    **_finger_chains(meshy_finger_bone, meshy=True),
}

RETARGET_ROOT_MANNEQUIN = "pelvis"
RETARGET_ROOT_MESHY = "Hips"

# The mannequin separates travel into a dedicated ``root`` bone and leaves the
# pelvis bobbing in place.  Meshy has no such bone -- its hierarchy starts at
# ``Hips`` -- so there is nowhere for root motion to land.  Left unset, the
# Root Motion op falls back to bone 0, which on the Meshy rig IS the pelvis: it
# overwrote the pelvis track, pinning the hips to z=0 and sliding the whole
# creature forward 4.3 m over a walk cycle.  So the mannequin gets its root
# bone named explicitly, and root motion is switched off for the target.
ROOT_MOTION_BONE_MANNEQUIN = "root"

# ─── Mixamo (X Bot), the source side of RTG_<Monster>_from_XBot ─────────────
#
# Same chain names again, so the mapping onto CHAINS_MESHY is exact.  Mixamo
# numbers its spine the usual way round (Spine is the lowest, Spine2 the top),
# which Meshy -- for all its Mixamo-style names -- does not.  X Bot's fingers
# have four joints; the fourth is the tip's end effector, which never animates,
# so the chains stop at 3 like the Meshy ones.
CHAINS_MIXAMO = {
    "Spine":         ("Spine", "Spine2"),
    "Neck":          ("Neck", "Neck"),
    "Head":          ("Head", "Head"),
    "LeftClavicle":  ("LeftShoulder", "LeftShoulder"),
    "LeftArm":       ("LeftArm", "LeftHand"),
    "RightClavicle": ("RightShoulder", "RightShoulder"),
    "RightArm":      ("RightArm", "RightHand"),
    "LeftLeg":       ("LeftUpLeg", "LeftToeBase"),
    "RightLeg":      ("RightUpLeg", "RightToeBase"),
    **_finger_chains(meshy_finger_bone, meshy=True),
}

RETARGET_ROOT_MIXAMO = "Hips"

# ─── Quaternius UAL, the source side of RTG_<Character>_from_UAL1/2 ──────────
#
# The Universal Animation Library's rig is named the mannequin's way, but it is
# a smaller tree: three spine joints (spine_01..03, not five), one neck joint,
# ``Head`` capitalised, no twist bones, and four joints per finger where the
# fourth (_04_leaf) is the tip's end effector.  The finger chains stop at 3
# like every other table here.
CHAINS_UAL = {
    "Spine":         ("spine_01", "spine_03"),
    "Neck":          ("neck_01", "neck_01"),
    "Head":          ("Head", "Head"),
    "LeftClavicle":  ("clavicle_l", "clavicle_l"),
    "LeftArm":       ("upperarm_l", "hand_l"),
    "RightClavicle": ("clavicle_r", "clavicle_r"),
    "RightArm":      ("upperarm_r", "hand_r"),
    "LeftLeg":       ("thigh_l", "ball_l"),
    "RightLeg":      ("thigh_r", "ball_r"),
    **_finger_chains(mannequin_finger_bone, meshy=False),
}

RETARGET_ROOT_UAL = "pelvis"
ROOT_MOTION_BONE_UAL = "root"
