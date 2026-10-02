"""verify.support_hand -- down the sights the left hand holds the gun: the
player's anim BP ends its chain in a Two Bone IK on the left hand, aimed at a
point in the right hand's space, and the weapon component writes its weight
from SightBlend and its pose from HeldTwoHanded.
"""

import unreal

from combat.aim_pitch import IK_CLASS
from combat.skin import player_skin
from combat.support_hand import (
    SUPPORT_HAND_VAR, SUPPORT_RIFLE_VAR, support_at, target_bone,
)
from combat.verify.aim_pitch import _feeds, _pose_source, _title
from combat.verify.common import BEL, PIN, cdo, check, graph, load, num_pin
from combat.verify.fixtures import wg
from combat.weapon_component.pose_weights import HELD_TWO_HANDED
from combat.weapon_specs import _weapon_specs

BONE_SPACE = unreal.BoneControlSpace.BCS_BONE_SPACE


def _point(make):
    """A MakeVector's three literals. One equal to its pin's default (0) is
    not saved, and reads back as nothing from disk."""
    return tuple(num_pin(make, axis) or 0.0 for axis in "XYZ")


def check_anim_bp_support_hand():
    skin = player_skin()
    bones = skin.pose_bones
    abp = load(skin.anim_bp)
    anim = graph(abp, "AnimGraph")
    nodes = anim.list_all_nodes() if anim else []
    weight = cdo(abp).get_editor_property(SUPPORT_HAND_VAR)
    check(f"{abp.get_name()} declares {SUPPORT_HAND_VAR} as a float, resting at 0",
          isinstance(weight, float) and weight == 0.0, repr(weight))
    rifle = cdo(abp).get_editor_property(SUPPORT_RIFLE_VAR)
    check(f"...and {SUPPORT_RIFLE_VAR} as a bool", isinstance(rifle, bool), repr(rifle))

    iks = [n for n in nodes if n.get_class().get_name() == IK_CLASS]
    check("exactly one Two Bone IK -- a rerun must not stack a second",
          len(iks) == 1, str(len(iks)))
    if len(iks) != 1:
        return
    ik = iks[0]
    inner = ik.get_editor_property("node")
    held = str(inner.get_editor_property("ik_bone").get_editor_property("bone_name"))
    check(f"it moves {bones['hand_l']}, the left hand", held == bones["hand_l"], held)
    check(f"...to a point in {bones['hand_r']}'s bone space: the gun is rigid to "
          "that hand, so the point is one on the gun",
          inner.get_editor_property("effector_location_space") == BONE_SPACE
          and target_bone(inner, "effector_target") == bones["hand_r"],
          target_bone(inner, "effector_target"))
    check(f"...the elbow held where the pose has it ({bones['forearm_l']} itself is "
          "the joint target)",
          inner.get_editor_property("joint_target_location_space") == BONE_SPACE
          and target_bone(inner, "joint_target") == bones["forearm_l"]
          and inner.get_editor_property("joint_target_location").length() == 0.0
          and not PIN.list_connected_pins(BEL.find_input_pin(ik, "JointTargetLocation")),
          target_bone(inner, "joint_target"))
    check("...the arm never stretched and the hand's turn left to the pose",
          not inner.get_editor_property("allow_stretching")
          and not inner.get_editor_property("take_rotation_from_effector_space")
          and not inner.get_editor_property("maintain_effector_rel_rot"))

    alpha = {_title(n) for n in _feeds(BEL.find_input_pin(ik, "Alpha"))}
    check(f"its weight is {SUPPORT_HAND_VAR} and nothing else",
          alpha == {f"Get {SUPPORT_HAND_VAR}"}, str(sorted(alpha)))
    pick = _pose_source(ik, "EffectorLocation")
    picked = {_title(n) for n in _feeds(BEL.find_input_pin(pick, "bPickA"))} if pick else set()
    check(f"the point is picked by {SUPPORT_RIFLE_VAR}: the rifle pose's or the "
          "pistol's", picked == {f"Get {SUPPORT_RIFLE_VAR}"}, str(sorted(picked)))
    for pin, pose, clip in (("A", "rifle", skin.aim_rifle), ("B", "pistol", skin.aim_pistol)):
        make = _pose_source(pick, pin) if pick else None
        got = _point(make) if make else None
        want = support_at(skin, clip)
        check(f"...the {pose} pose's: where its clip holds the left hand at its "
              "start, re-measured",
              got is not None and max(abs(g - w) for g, w in zip(got, want)) < 0.01,
              f"{got} against {want}")
    after = PIN.list_connected_pins(BEL.find_output_pin(ik, "Pose"))
    check("it is the last thing done to the pose: it feeds the ComponentToLocal",
          len(after) == 1 and PIN.get_owning_node(after[0]).get_class().get_name()
          == "AnimGraphNode_ComponentToLocalSpace")


def check_component_writes_support_hand():
    skin = player_skin()
    for var, source, why in (
            (SUPPORT_HAND_VAR, "SightBlend",
             "the hold eases in with the sights and is off at the hip"),
            (SUPPORT_RIFLE_VAR, HELD_TWO_HANDED,
             "the component's own copy, so nothing reads off an empty hand")):
        writes = [n for n in wg if _title(n) == f"Set {var}"]
        check(f"BP_WeaponComponent writes the anim BP's {var} once a frame",
              len(writes) == 1, str(len(writes)))
        if len(writes) != 1:
            continue
        src = {_title(n) for n in _feeds(BEL.find_input_pin(writes[0], var))}
        check(f"...from {source} alone: {why}", src == {f"Get {source}"},
              str(sorted(src)))
        target = _feeds(BEL.find_input_pin(writes[0], "self"), limit=3)
        check("...onto the player's anim instance, cast to the player's anim BP",
              any(n.get_class().get_name() == "K2Node_DynamicCast" for n in target),
              str([_title(n) for n in target]))
    odd = [s["display"] for s in _weapon_specs()
           if s["two_handed"] != (s["aim"] == skin.aim_rifle)]
    check(f"every gun held in the rifle pose is two-handed, and no other: "
          f"{HELD_TWO_HANDED} names the pose", not odd, str(odd))


def run():
    check_anim_bp_support_hand()
    check_component_writes_support_hand()
