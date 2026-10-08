"""The weapon layers over the motion-matching base (task G4): their names.
Constants only; weapon_layers.py authors the anim Blueprint,
gas_locomotion.py links it into the base, verify/weapon_layers.py checks both.

The player's base movement is the Game Animation Sample's anim Blueprint
(gas_locomotion.py), and everything a weapon does to the body is a second
anim Blueprint on the same skeleton, linked into it:

    the base (SandboxCharacter_CMC_ABP)
        ... motion matching -> lean -> aim offset -> Offset Root Bone
        -> Remap Curves -> [Linked Anim Graph: ABP_WeaponLayers]
        -> (the server branch) the feet -> Pose History -> Output

    the layers (ABP_WeaponLayers)
        Input Pose -> the stance clips -> [DefaultSlot, from spine_01]
        -> [HitSlot, from spine_01] -> (its server branch) FullBodySlot
        -> the guard, the hips' lift, the aim's pitch, the support hand
        -> Output

The layer graph has the shape ABP_Unarmed has after anim_blueprint.py, with
an Input Pose where the locomotion state machine was, so every builder
written against that graph (aim_pitch, body_pose, support_hand, stance_clips,
server_anim) and its verifier runs on this one as it is.
"""

from asset_pipeline.metahuman_paths import SOURCED_DIR

# The anim Blueprint the layers are authored in: combat/skin.SKIN_GAS.anim_bp.
LAYERS_ABP = f"{SOURCED_DIR}/ABP_WeaponLayers"
# The tag of the base graph's Linked Anim Graph node: how the weapon component
# and a probe find the layers' instance on a body
# (SkeletalMeshComponent.GetLinkedAnimGraphInstanceByTag).
LAYERS_TAG = "WeaponLayers"

INPUT_CLASS = "AnimGraphNode_LinkedInputPose"
LINK_CLASS = "AnimGraphNode_LinkedAnimGraph"
# The link's pose pins: the layer graph's one Input Pose, by its default name.
LINK_IN_PIN = "InPose"
# The node of the base graph the link follows.
BEFORE_LINK_CLASS = "AnimGraphNode_RemapCurves"

# The anim instance's own switch: a montage played on the body's main anim
# instance (every PlaySlotAnimationAsDynamicMontage the weapon and health
# components make) is what this instance's slots play.
MAIN_MONTAGES = "use_main_instance_montage_evaluation_data"
