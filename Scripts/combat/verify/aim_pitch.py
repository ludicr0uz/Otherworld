"""verify.aim_pitch -- down the sights the upper body pitches with the view: the
player's anim BP turns two spine bones by AimPitch, and the weapon component
writes AimPitch from the view's pitch scaled by SightBlend.
"""

import unreal

from combat.aim_pitch import AIM_PITCH_VAR, IK_CLASS, MODIFY_BONE_CLASS, ROLL_PER_DEGREE
from combat.skin import player_skin
from combat.verify.common import BEL, PIN, cdo, check, graph, load, num_pin
from combat.verify.fixtures import wg


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeds(pin, limit=100):
    """Every node feeding this pin through data links."""
    seen, stack = [], [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node not in seen:
                seen.append(node)
                stack.extend(x for x in BEL.list_input_pins(node)
                             if str(PIN.get_pin_name(x)) != "execute")
    return seen


def _driven(node):
    """A body-pose ModifyBone (body_pose.py): its Alpha is wired to a weight."""
    return bool(PIN.list_connected_pins(BEL.find_input_pin(node, "Alpha")))


def _pose_source(node, pin_name):
    fed = PIN.list_connected_pins(BEL.find_input_pin(node, pin_name))
    return PIN.get_owning_node(fed[0]) if fed else None


def check_anim_bp_pitch():
    skin = player_skin()
    abp = load(skin.anim_bp)
    anim = graph(abp, "AnimGraph")
    nodes = anim.list_all_nodes() if anim else []
    pitch = cdo(abp).get_editor_property(AIM_PITCH_VAR)
    check(f"{abp.get_name()} declares {AIM_PITCH_VAR} as a float, resting at 0",
          isinstance(pitch, float) and pitch == 0.0, repr(pitch))

    # Output <- ComponentToLocal <- [the support hand's IK, support_hand.py]
    #        <- ModifyBone(upper) <- ModifyBone(lower)
    #        <- [the body poses, body_pose.py] <- LocalToComponent: the whole
    # pose, whatever it is, turns last.
    roots = [n for n in nodes if n.get_class().get_name() == "AnimGraphNode_Root"]
    chain, node, pin = [], roots[0] if roots else None, "Result"
    while node is not None and len(chain) < 64:
        node = _pose_source(node, pin)
        if node is None:
            break
        name = node.get_class().get_name()
        if name == MODIFY_BONE_CLASS and _driven(node):
            chain.append("body pose")
        else:
            chain.append(name)
        if name == "AnimGraphNode_LocalToComponentSpace":
            break
        pin = "ComponentPose"
    while chain.count("body pose") > 1:
        chain.remove("body pose")
    if IK_CLASS in chain:
        chain.remove(IK_CLASS)
    check("the output pose is the last pose, pitched on two bones in component "
          "space", chain[:3] == ["AnimGraphNode_ComponentToLocalSpace",
                                 MODIFY_BONE_CLASS, MODIFY_BONE_CLASS]
          and chain[-1] == "AnimGraphNode_LocalToComponentSpace"
          and len(chain) <= 5, str(chain))

    bones = unreal.AnimPoseExtensions.get_bone_names(
        unreal.AnimPoseExtensions.get_reference_pose(
            abp.get_editor_property("target_skeleton")))
    mods = [n for n in nodes if n.get_class().get_name() == MODIFY_BONE_CLASS
            and not _driven(n)]
    check("exactly two pitch ModifyBones -- a rerun must not stack a third",
          len(mods) == 2, str(len(mods)))
    turned = sorted(str(m.get_editor_property("node").get_editor_property(
        "bone_to_modify").get_editor_property("bone_name")) for m in mods)
    check(f"they turn {', '.join(skin.aim_bones)}, which the skeleton has",
          turned == sorted(skin.aim_bones)
          and all(unreal.Name(b) in bones for b in turned), str(turned))
    for m in mods:
        inner = m.get_editor_property("node")
        bone = inner.get_editor_property("bone_to_modify").get_editor_property("bone_name")
        check(f"{bone}: the rotation is ADDED in component space, so the bones "
              "above turn with it as one piece",
              inner.get_editor_property("rotation_mode")
              == unreal.BoneModificationMode.BMM_ADDITIVE
              and inner.get_editor_property("rotation_space")
              == unreal.BoneControlSpace.BCS_COMPONENT_SPACE)
        # Roll(+a) tips the body's forward (component +Y) down, so AimPitch up
        # is a negative roll, halved because two bones share it.
        make = _pose_source(m, "Rotation")
        roll_in = [n for n in _feeds(BEL.find_input_pin(make, "Roll"))] if make else []
        scale = [num_pin(n, "B") for n in roll_in if num_pin(n, "B") is not None]
        check(f"{bone}: roll = {AIM_PITCH_VAR} x {ROLL_PER_DEGREE:g}",
              f"Get {AIM_PITCH_VAR}" in {_title(n) for n in roll_in}
              and scale == [ROLL_PER_DEGREE], f"{[_title(n) for n in roll_in]} {scale}")


def check_component_writes_pitch():
    writes = [n for n in wg if _title(n) == f"Set {AIM_PITCH_VAR}"]
    check(f"BP_WeaponComponent writes the anim BP's {AIM_PITCH_VAR} once a frame",
          len(writes) == 1, str(len(writes)))
    if len(writes) != 1:
        return
    src = {_title(n) for n in _feeds(BEL.find_input_pin(writes[0], AIM_PITCH_VAR))}
    # SightBlend, not the key: the body eases in with the camera's travel, and
    # the hip and shoulder aims (SightBlend 0) keep the level pose.
    check("...from the view's signed pitch scaled by SightBlend",
          {"GetControlRotation", "NormalizeAxis", "Get SightBlend"} <= src,
          str(sorted(src)))
    target = _feeds(BEL.find_input_pin(writes[0], "self"), limit=3)
    check("...onto the player's anim instance, cast to the player's anim BP",
          any(n.get_class().get_name() == "K2Node_DynamicCast" for n in target),
          str([_title(n) for n in target]))


def run():
    check_anim_bp_pitch()
    check_component_writes_pitch()
