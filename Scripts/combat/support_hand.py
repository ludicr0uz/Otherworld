"""The support hand: down the sights the player's anim BP holds the left hand
on the gun, so the hand and the gun move as one.

WHAT WAS WRONG
--------------
The gun is rigidly attached to the right hand (grip.py), and nothing tied the
left hand to it: the ready pose puts it under the handguard, and it stayed
there only as long as the two arms moved alike. They do not. The ready pose is
layered over the locomotion in mesh space, so the arms keep the pose's turn but
hang off whatever the legs' clip does to the spine, and the two shoulders move
apart as it twists; the ready clip itself breathes a little differently in
each arm. Measured in the gun's own space, the left hand slid 0.4 cm standing
and 1 cm walking -- and down the sights the camera rides the gun (sights.py),
so the gun stands still in the view and the hand is what is seen to move.

WHAT HOLDS IT
-------------
One Two Bone IK on the left arm, last in the chain, after the aim pitch:

    ... -> ModifyBone(upper) -> TwoBoneIK(left hand) -> ComponentToLocal -> Output

Its effector is a point in the RIGHT HAND's bone space, which is the gun's
space: where the held gun's own ready pose has the left hand at the clip's
start, sampled off the clip (support_at). The point is the gun's
(BP_WeaponItem.SupportPoint, written at build time off its AimPose), and the
weapon component hands the held one's to SupportPoint here: the shotgun's pose
seats the hand on its pump, somewhere the rifle pose's is not, and two points
picked by a flag could not say so. The elbow keeps its side: the joint target is
the forearm bone itself, as the pose left it. The hand's turn is not touched;
it is the pose's, in mesh space, as the right hand's is.

SupportHand is its weight. The weapon component writes both
(weapon_component/support_hand.py): SupportHand is SightBlend, so the hold
eases in with the sights and is nothing at the hip, on the shoulder, or with
no gun in hand. Only down the sights, because that is where the view rides the
gun; elsewhere the upper-body slot also plays things the left hand must be
free for (a throw, a search).

This is the *player's* anim BP (PlayerSkin.anim_bp). aim_pitch.py takes this
node out with its own on a rerun, so the build order is the pitch, the body
poses, then this.
"""

import unreal

from combat.aim_pitch import IK_CLASS, _feeding, _nodes_of
from combat.graph import (
    BEL, BGE, PIN, _assets, _connect, _declare, _float_type, _log, _palette, _pin,
    _struct_type)
from uebp.layout import arrange

SUPPORT_HAND_VAR = "SupportHand"
# The point, on the anim BP; and under the same name, each gun's own on
# BP_WeaponItem.
SUPPORT_POINT_VAR = "SupportPoint"

NODE_TWO_BONE_IK = "Animation|SkeletalControls|TwoBoneIK"
BONE_SPACE = unreal.BoneControlSpace.BCS_BONE_SPACE


def support_at(skin, pose_path):
    """Where the ready pose holds the left hand, in the right hand's bone
    space, at the clip's start: (x, y, z) in cm."""
    anim = _assets().load_asset(pose_path)
    if not anim:
        raise RuntimeError(f"could not load the pose {pose_path}")
    ape = unreal.AnimPoseExtensions
    pose = ape.get_anim_pose_at_time(anim, 0.0, unreal.AnimPoseEvaluationOptions())
    right, left = (ape.get_bone_pose(pose, skin.pose_bones[hand],
                                     unreal.AnimPoseSpaces.WORLD)
                   for hand in ("hand_r", "hand_l"))
    at = unreal.MathLibrary.make_relative_transform(left, right).translation
    return (round(at.x, 3), round(at.y, 3), round(at.z, 3))


def _target(bone):
    target = unreal.BoneSocketTarget()
    ref = unreal.BoneReference()
    ref.set_editor_property("bone_name", bone)
    target.set_editor_property("use_socket", False)
    target.set_editor_property("bone_reference", ref)
    return target


def target_bone(inner, prop):
    """The bone one of the IK node's targets names."""
    return str(inner.get_editor_property(prop).get_editor_property("bone_reference")
               .get_editor_property("bone_name"))


def _two_bone_ik(ed, skin):
    """The IK on the left hand: effector in the right hand's space, the elbow
    held where the pose has it."""
    bones = skin.pose_bones
    ik = _palette(ed, NODE_TWO_BONE_IK)
    inner = ik.get_editor_property("node")
    ref = unreal.BoneReference()
    ref.set_editor_property("bone_name", bones["hand_l"])
    inner.set_editor_property("ik_bone", ref)
    inner.set_editor_property("effector_location_space", BONE_SPACE)
    inner.set_editor_property("effector_target", _target(bones["hand_r"]))
    inner.set_editor_property("joint_target_location_space", BONE_SPACE)
    inner.set_editor_property("joint_target", _target(bones["forearm_l"]))
    inner.set_editor_property("joint_target_location", unreal.Vector(0.0, 0.0, 0.0))
    inner.set_editor_property("allow_stretching", False)
    inner.set_editor_property("take_rotation_from_effector_space", False)
    inner.set_editor_property("maintain_effector_rel_rot", False)
    ik.set_editor_property("node", inner)
    back = ik.get_editor_property("node")
    got = (str(back.get_editor_property("ik_bone").get_editor_property("bone_name")),
           target_bone(back, "effector_target"), target_bone(back, "joint_target"),
           back.get_editor_property("effector_location_space"),
           back.get_editor_property("joint_target_location_space"))
    want = (bones["hand_l"], bones["hand_r"], bones["forearm_l"], BONE_SPACE, BONE_SPACE)
    if got != want:
        raise RuntimeError(f"the support hand's IK did not keep its settings: {got}")
    return ik


def _remove_previous(ed):
    """Take out an earlier run's IK and join the pose round it again."""
    for ik in _nodes_of(ed, IK_CLASS):
        fed = PIN.list_connected_pins(_pin(ik, "ComponentPose"))
        feeds = PIN.list_connected_pins(_pin(ik, "Pose", is_input=False))
        ed.remove_nodes([ik] + _feeding(ik))
        if fed and feeds:
            _connect(fed[0], feeds[0])


def patch_support_hand(skin):
    """Insert the left hand's IK before the ComponentToLocal that ends
    ``skin``'s anim BP's chain. Re-running replaces the previous one."""
    bp = _assets().load_asset(skin.anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {skin.anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    to_ls = _nodes_of(ed, "AnimGraphNode_ComponentToLocalSpace") if ed else []
    if len(to_ls) != 1:
        raise RuntimeError(f"{skin.anim_bp}: expected the aim pitch's one "
                           f"ComponentToLocal, found {len(to_ls)} -- run "
                           "patch_aim_pitch first")
    skeleton = bp.get_editor_property("target_skeleton")
    have = {str(b) for b in unreal.AnimPoseExtensions.get_bone_names(
        unreal.AnimPoseExtensions.get_reference_pose(skeleton))}
    arm = [skin.pose_bones[b] for b in ("hand_r", "hand_l", "forearm_l", "upperarm_l")]
    missing = [b for b in arm if b not in have]
    if missing:
        raise RuntimeError(f"{skeleton.get_name()} has no {missing}; the support "
                           "hand would hold nothing")

    _remove_previous(ed)
    _declare(ed, SUPPORT_HAND_VAR, _float_type())
    _declare(ed, SUPPORT_POINT_VAR, _struct_type(unreal.Vector.static_struct()))

    pose_in = _pin(to_ls[0], "ComponentPose")
    fed = PIN.list_connected_pins(pose_in)
    if not fed:
        raise RuntimeError("the ComponentToLocal is fed by nothing")
    upstream = fed[0]
    PIN.break_pin_links(pose_in)

    ik = _two_bone_ik(ed, skin)
    _connect(upstream, _pin(ik, "ComponentPose"))
    _connect(_pin(ik, "Pose", is_input=False), pose_in)

    weight = ed.add_get_member_variable_node(SUPPORT_HAND_VAR)
    _connect(_pin(weight, SUPPORT_HAND_VAR, is_input=False), _pin(ik, "Alpha"))
    point = ed.add_get_member_variable_node(SUPPORT_POINT_VAR)
    _connect(_pin(point, SUPPORT_POINT_VAR, is_input=False),
             _pin(ik, "EffectorLocation"))
    ed.add_comment_to_nodes(
        f"Down the sights the left hand holds the gun: a Two Bone IK puts "
        f"{skin.pose_bones['hand_l']} at {SUPPORT_POINT_VAR}, a point in "
        f"{skin.pose_bones['hand_r']}'s space (the gun is rigid to that hand): "
        "where the held gun's ready pose has it at its start. "
        f"{SUPPORT_HAND_VAR} (0..1, SightBlend) is its weight. BP_WeaponComponent "
        "writes both. See Scripts/combat/support_hand.py.", [ik, weight, point])

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{skin.anim_bp} failed to compile after the support hand")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: {SUPPORT_HAND_VAR} holds {skin.pose_bones['hand_l']} at "
         f"{SUPPORT_POINT_VAR}, the held gun's point in "
         f"{skin.pose_bones['hand_r']}'s space")
    return bp
