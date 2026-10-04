"""bone_map -- which Meshy bone answers to which mannequin bone.  Constants.

Meshy's rigger returns the same 24 bones for every humanoid (skeleton_probe),
named the Mixamo way with one quirk: its spine is numbered downwards, so the
joint above the hips is Spine02 and the top one is Spine.  The mannequin mesh
has 89.  The tables below say, for each Meshy bone, what its joint places
(LANDMARKS), how it is turned into the mannequin's pose (see repose.py) and
where its weight goes (see weights.py).

A rig with a bone not listed here is refused: a wendigo's extra joint is not
something to guess at.
"""

# (mannequin suffix, Meshy prefix)
SIDES = (("l", "Left"), ("r", "Right"))

MESHY_BONES = frozenset(
    ["Hips", "Spine02", "Spine01", "Spine", "neck", "Head", "head_end",
     "headfront"]
    + [f"{side}{part}" for _s, side in SIDES
       for part in ("Shoulder", "Arm", "ForeArm", "Hand",
                    "UpLeg", "Leg", "Foot", "ToeBase")])

# Meshy joint -> the mannequin bone that joint places.
LANDMARKS = {"Hips": "pelvis", "neck": "neck_01", "Head": "head"}
for _s, _side in SIDES:
    LANDMARKS.update({
        f"{_side}Shoulder": f"clavicle_{_s}", f"{_side}Arm": f"upperarm_{_s}",
        f"{_side}ForeArm": f"lowerarm_{_s}", f"{_side}Hand": f"hand_{_s}",
        f"{_side}UpLeg": f"thigh_{_s}", f"{_side}Leg": f"calf_{_s}",
        f"{_side}Foot": f"foot_{_s}", f"{_side}ToeBase": f"ball_{_s}"})

# The trunk is not matched joint for joint (three spine joints against five):
# the mannequin's are laid along Meshy's line at the mannequin's own spacing.
MESHY_SPINE_LINE = ("Hips", "Spine02", "Spine01", "Spine", "neck")
MANNEQUIN_SPINE_LINE = ("pelvis", "spine_01", "spine_02", "spine_03",
                        "spine_04", "spine_05", "neck_01")
MESHY_NECK_LINE = ("neck", "Head")
MANNEQUIN_NECK_LINE = ("neck_01", "neck_02", "head")

# Limb segments: Meshy bone -> (its child, mannequin bone, mannequin child,
# upper).  These are the bones turned onto the mannequin's lines, and the
# ones whose weight is shared with the mannequin's twist bones.  ``upper``
# says which end of the segment the main bone keeps: a twist bone takes the
# twist OUT near the joint that does not twist (shoulder, hip), so the main
# bone's own weight sits at the far end of an upper segment and at the near
# end of a lower one.
LIMBS = {}
for _s, _side in SIDES:
    LIMBS[f"{_side}Arm"] = (f"{_side}ForeArm", f"upperarm_{_s}", f"lowerarm_{_s}", True)
    LIMBS[f"{_side}ForeArm"] = (f"{_side}Hand", f"lowerarm_{_s}", f"hand_{_s}", False)
    LIMBS[f"{_side}UpLeg"] = (f"{_side}Leg", f"thigh_{_s}", f"calf_{_s}", True)
    LIMBS[f"{_side}Leg"] = (f"{_side}Foot", f"calf_{_s}", f"foot_{_s}", False)

HANDS = {f"{side}Hand": s for s, side in SIDES}
FEET = {f"{side}Foot": (f"{side}ToeBase", s) for s, side in SIDES}

# Weight that moves to one mannequin bone as it is.
DIRECT = {"Hips": "pelvis", "Head": "head", "head_end": "head", "headfront": "head"}
for _s, _side in SIDES:
    DIRECT.update({f"{_side}Shoulder": f"clavicle_{_s}",
                   f"{_side}Foot": f"foot_{_s}", f"{_side}ToeBase": f"ball_{_s}"})
SPINE_WEIGHT = ("Spine02", "Spine01", "Spine")
NECK_WEIGHT = ("neck",)

FINGERS = ("thumb", "index", "middle", "ring", "pinky")
FINGER_JOINTS = (1, 2, 3)
# The four whose first joints are the knuckle line.
KNUCKLE_FINGERS = ("index", "middle", "ring", "pinky")


def finger_bone(finger, joint, s):
    return f"{finger}_{joint:02d}_{s}"


def finger_bones(s):
    return [finger_bone(f, j, s) for f in FINGERS for j in FINGER_JOINTS]
