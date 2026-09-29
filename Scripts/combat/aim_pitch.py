"""The sights' pitch: the player's anim BP tips the upper body onto the aim, so
down the sights the barrel points where the view does when looking up or down.

WHY THE SPINE, AND WHY TWO BONES
--------------------------------
The weapon is rigidly attached to the hand and never rotated on its own (see
grip.py), and there is no aim offset: UBlendSpace has no sample-authoring API,
so one cannot be built from Python. What the AnimGraph *can* take is a
Transform (Modify) Bone node. Two of them, on the skin's ``aim_bones``, each
add half of ``AimPitch`` in component space, so everything above the upper
one -- chest, arms, head and the weapon in the fist -- turns by the whole pitch
as one rigid piece. Rigid is the point: the sight camera sits at the held
weapon's SightOffset (sights.py), so it turns with the gun and the eye stays on
the sight line at any pitch, exactly as it is at level aim. Splitting it over
two joints bends the back rather than folding it at one vertebra.

THE AXIS
--------
The mesh is yawed 270 inside the actor (PlayerSkin.mesh_yaw), so the body's
forward is component +Y and its left is +X. A rotation about X is a Roll, and
Roll(+a) tips +Y *down* -- so looking up by P is Roll(-P). ROLL_PER_DEGREE
carries both the sign and the split.

WHERE IT SITS
-------------
At the very end of the chain, after FullBodySlot and right before the output:

    ... -> Slot(FullBodySlot) -> LocalToComponent -> ModifyBone(lower)
        -> ModifyBone(upper) -> ComponentToLocal -> Output

so it turns whatever the pose is -- the ready pose, a flinch -- and costs
nothing when AimPitch is 0, which it is everywhere but down the sights. The
weapon component writes AimPitch (weapon_component/sight_pitch.py).

This is the *player's* anim BP (PlayerSkin.anim_bp), not ABP_Unarmed: the
adventurer's is a retargeted copy, rebuilt by build_retarget.py, which runs
before this builder in the build order.
"""

import unreal

from combat.graph import (
    BEL, BGE, PIN, _assets, _at, _connect, _declare, _float_type, _log, _node,
    _palette, _pin, _set,
)
from combat.nodes import FN_MAKE_ROT, FN_MUL_FF

AIM_PITCH_VAR = "AimPitch"
# Each of the two bones takes half, and Roll(+a) tips the body's forward down.
ROLL_PER_DEGREE = -0.5

NODE_MODIFY_BONE = "Animation|SkeletalControls|Transform(Modify)Bone"
NODE_TO_COMPONENT = "Animation|ConvertSpaces|LocalToComponent"
NODE_TO_LOCAL = "Animation|ConvertSpaces|ComponentToLocal"
MODIFY_BONE_CLASS = "AnimGraphNode_ModifyBone"
# Everything this module puts in the graph, by class, so a rerun can take it
# out again. The K2 nodes feeding the rotation pins are found by walking back
# from the ModifyBones, since the stock graph has K2 nodes of its own.
OWN_POSE_CLASSES = (MODIFY_BONE_CLASS, "AnimGraphNode_LocalToComponentSpace",
                    "AnimGraphNode_ComponentToLocalSpace")


def _nodes_of(ed, class_name):
    return [n for n in ed.list_all_nodes() if n.get_class().get_name() == class_name]


def _feeding(node):
    """Every K2 node upstream of ``node``'s non-pose inputs."""
    found, stack = [], [node]
    while stack:
        for p in BEL.list_input_pins(stack.pop()):
            for q in PIN.list_connected_pins(p):
                up = PIN.get_owning_node(q)
                if up.get_class().get_name().startswith("K2Node") and up not in found:
                    found.append(up)
                    stack.append(up)
    return found


def _remove_previous(ed, root):
    """Take out an earlier run's chain and rejoin its upstream to the output."""
    mine = [n for c in OWN_POSE_CLASSES for n in _nodes_of(ed, c)]
    if not mine:
        return
    upstream = None
    for n in _nodes_of(ed, "AnimGraphNode_LocalToComponentSpace"):
        fed = PIN.list_connected_pins(_pin(n, "LocalPose"))
        upstream = fed[0] if fed else upstream
    extras = [k for n in _nodes_of(ed, MODIFY_BONE_CLASS) for k in _feeding(n)]
    ed.remove_nodes(mine + extras)
    if upstream is None:
        raise RuntimeError("an earlier aim-pitch chain was fed by nothing; "
                           "refusing to guess what the output should be")
    _connect(upstream, _pin(root, "Result"))


def _modify_bone(ed, bone, pitch_out, x, y):
    """A ModifyBone adding Roll(AimPitch * ROLL_PER_DEGREE) to ``bone``."""
    mb = _at(_palette(ed, NODE_MODIFY_BONE), x, y)
    inner = mb.get_editor_property("node")
    ref = unreal.BoneReference()
    ref.set_editor_property("bone_name", bone)
    inner.set_editor_property("bone_to_modify", ref)
    inner.set_editor_property("rotation_mode",
                              unreal.BoneModificationMode.BMM_ADDITIVE)
    inner.set_editor_property("rotation_space",
                              unreal.BoneControlSpace.BCS_COMPONENT_SPACE)
    mb.set_editor_property("node", inner)
    back = mb.get_editor_property("node")
    if (str(back.get_editor_property("bone_to_modify").get_editor_property("bone_name"))
            != bone or back.get_editor_property("rotation_mode")
            != unreal.BoneModificationMode.BMM_ADDITIVE):
        raise RuntimeError(f"the ModifyBone on {bone} did not keep its settings")

    half = _at(_node(ed, FN_MUL_FF), x - 520, y + 260)
    _connect(pitch_out, _pin(half, "A"))
    _set(half, "B", ROLL_PER_DEGREE)
    rot = _at(_node(ed, FN_MAKE_ROT), x - 260, y + 260)
    _connect(_pin(half, "ReturnValue", is_input=False), _pin(rot, "Roll"))
    _connect(_pin(rot, "ReturnValue", is_input=False), _pin(mb, "Rotation"))
    return mb


def patch_aim_pitch(skin):
    """Insert the two-bone pitch before the output of ``skin``'s anim BP.

    Re-running removes the previous chain first, so it never stacks.
    """
    bp = _assets().load_asset(skin.anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {skin.anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    roots = _nodes_of(ed, "AnimGraphNode_Root") if ed else []
    if len(roots) != 1:
        raise RuntimeError(f"{skin.anim_bp}: expected one output pose, found "
                           f"{len(roots)}")
    root = roots[0]
    skeleton = bp.get_editor_property("target_skeleton")
    bones = {str(b) for b in unreal.AnimPoseExtensions.get_bone_names(
        unreal.AnimPoseExtensions.get_reference_pose(skeleton))}
    missing = [b for b in skin.aim_bones if b not in bones]
    if missing:
        raise RuntimeError(f"{skeleton.get_name()} has no {missing}; the pitch "
                           "would turn nothing")

    _remove_previous(ed, root)
    _declare(ed, AIM_PITCH_VAR, _float_type())

    fed = PIN.list_connected_pins(_pin(root, "Result"))
    if not fed:
        raise RuntimeError("the output pose is fed by nothing")
    upstream = fed[0]
    PIN.break_pin_links(_pin(root, "Result"))

    pitch = _at(ed.add_get_member_variable_node(AIM_PITCH_VAR), -1100, 1500)
    pitch_out = _pin(pitch, AIM_PITCH_VAR, is_input=False)
    to_cs = _at(_palette(ed, NODE_TO_COMPONENT), -800, 1200)
    _connect(upstream, _pin(to_cs, "LocalPose"))
    pose = _pin(to_cs, "ComponentPose", is_input=False)
    made = [pitch, to_cs]
    for i, bone in enumerate(skin.aim_bones):
        mb = _modify_bone(ed, bone, pitch_out, -400 + i * 320, 1200)
        _connect(pose, _pin(mb, "ComponentPose"))
        pose = _pin(mb, "Pose", is_input=False)
        made.append(mb)
    to_ls = _at(_palette(ed, NODE_TO_LOCAL), 300, 1200)
    _connect(pose, _pin(to_ls, "ComponentPose"))
    _connect(_pin(to_ls, "Pose", is_input=False), _pin(root, "Result"))
    made.append(to_ls)
    ed.add_comment_to_nodes(
        f"Down the sights, the upper body tips onto the aim: {AIM_PITCH_VAR} "
        f"(degrees up, written by BP_WeaponComponent) split over "
        f"{' and '.join(skin.aim_bones)}, as a component-space roll -- the "
        "body faces component +Y. See Scripts/combat/aim_pitch.py.", made)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{skin.anim_bp} failed to compile after the aim pitch")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: {AIM_PITCH_VAR} pitches "
         f"{' + '.join(skin.aim_bones)} before the output pose")
    return bp
