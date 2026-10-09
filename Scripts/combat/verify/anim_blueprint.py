"""verify.anim_blueprint -- ABP_Unarmed: the two layered blends and the three slots, wired in order.
"""

from combat.server_anim_consts import BRANCH_CLASS, CLIENT_PIN
from combat.anim_blueprint import (
    AIM_SLOT, FULL_BODY_SLOT, HIT_SLOT, UPPER_BODY_ROOT,
)
from combat.paths import ABP_PATH
from combat.skin import player_skin
from combat.verify.common import BEL, PIN, check, graph, load
from uebp.pose_share import fed as linked


# ─── The AnimGraph patch ─────────────────────────────────────────────────────

def check_anim_graph_patch():
    abp = load(ABP_PATH)
    anim = graph(abp, "AnimGraph")
    anim_nodes = anim.list_all_nodes() if anim else []
    rigs = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_ControlRig"]
    blends = [n for n in anim_nodes
              if n.get_class().get_name() == "AnimGraphNode_LayeredBoneBlend"]
    # Two now, not one: the aim pose's, and the hit reaction's behind it. Both are
    # filtered at the same spine root, and BOTH filters are checked -- an
    # unresolvable branch filter contributes no bones, so a blend that lost its
    # filter plays its slot at zero weight, which is invisible on screen and
    # indistinguishable in a log from a montage that never started.
    check("ABP_Unarmed has exactly two layered bone blends (aim, then hit)",
          len(blends) == 2, str(len(blends)))

    slots = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_Slot"]
    slot_names = {str(n.get_editor_property("node").get_editor_property("slot_name")): n
                  for n in slots}
    check(f"all three slots exist: {AIM_SLOT} (aim), {HIT_SLOT} (flinch) and "
          f"{FULL_BODY_SLOT}",
          {AIM_SLOT, HIT_SLOT, FULL_BODY_SLOT} <= set(slot_names),
          str(sorted(slot_names)))
    check("exactly three slots -- a rerun must not stack a fourth on the chain",
          len(slots) == 3, str(len(slots)))


    def _fed_blend(slot_node):
        """The LayeredBoneBlend a Slot node's pose runs into, or None."""
        fed = linked(BEL.find_output_pin(slot_node, "Pose"))
        if not fed:
            return None
        owner = PIN.get_owning_node(fed[0])
        return owner if owner.get_class().get_name() == "AnimGraphNode_LayeredBoneBlend" \
            else None


    aim_blend = _fed_blend(slot_names[AIM_SLOT]) if AIM_SLOT in slot_names else None
    hit_blend = _fed_blend(slot_names[HIT_SLOT]) if HIT_SLOT in slot_names else None
    check("the aim slot and the hit slot feed two DIFFERENT blends",
          aim_blend is not None and hit_blend is not None and aim_blend != hit_blend)

    # The locomotion state machine -- or, when the body worn on this anim
    # blueprint has stance clips (one bound to the mannequin's skeleton:
    # combat/skin.SKIN_BOUND), the blend stance_clips.py puts over it.
    skin = player_skin()
    over_locomotion = ("AnimGraphNode_TwoWayBlend"
                       if skin.anim_bp == ABP_PATH and skin.stance_clips
                       else "AnimGraphNode_StateMachine")
    for label, blend, want_base in (("aim", aim_blend, over_locomotion),
                                    ("hit", hit_blend, "AnimGraphNode_LayeredBoneBlend")):
        if blend is None:
            continue
        layers = blend.get_editor_property("node").get_editor_property("layer_setup")
        bones = [str(f.get_editor_property("bone_name"))
                 for l in layers for f in l.get_editor_property("branch_filters")]
        check(f"the {label} blend is filtered at {UPPER_BODY_ROOT} (upper body only)",
              bones == [UPPER_BODY_ROOT], str(bones))
        # The regression that put the barrel 21 degrees left: in local space the
        # aim pose's arms hang off the locomotion hips and lose their own pelvis
        # yaw. Runtime, before the fix: body yaw 44.6, gun yaw 23.3, every frame.
        check(f"the {label} blend runs in mesh space, so its pose keeps its own "
              f"direction",
              blend.get_editor_property("node").get_editor_property(
                  "mesh_space_rotation_blend"))
        base_src = [PIN.get_owning_node(q).get_class().get_name()
                    for q in linked(
                        BEL.find_input_pin(blend, "BasePose"))]
        check(f"the {label} blend's base pose comes from {want_base}",
              base_src == [want_base], str(base_src))

    # The hit slot's SOURCE is the aim blend's output, i.e. the same pose as its own
    # blend's base. That is what makes the second blend free at rest -- both inputs
    # are the same pose, so its weight cannot matter until a montage is playing.
    if hit_blend is not None:
        src = [PIN.get_owning_node(q) for q in linked(
            BEL.find_input_pin(slot_names[HIT_SLOT], "Source"))]
        base = [PIN.get_owning_node(q) for q in linked(
            BEL.find_input_pin(hit_blend, "BasePose"))]
        check(f"{HIT_SLOT} passes through the same pose its blend uses as a base, "
              f"so the insertion is a no-op until something is hit",
              src == base and src == [aim_blend],
              f"{[n.get_name() for n in src]} vs {[n.get_name() for n in base]}")

    # ...and the flinch is DOWNSTREAM of the aim pose, not upstream: a reaction has
    # to win over the ready pose for its second, not be overwritten by it.
    if aim_blend is not None and hit_blend is not None:
        onward = [PIN.get_owning_node(q) for q in linked(
            BEL.find_output_pin(aim_blend, "Pose"))]
        check(f"the aim blend feeds the hit blend, so {HIT_SLOT} overrides the "
              f"ready pose rather than the other way round",
              hit_blend in onward, str([n.get_name() for n in onward]))
    # The full-body slot has to sit AFTER both layered blends, or it is filtered to
    # the upper body like the other two and whatever plays into it reaches the chest
    # only.
    if FULL_BODY_SLOT in slot_names and rigs:
        feeding = [PIN.get_owning_node(q) for q in linked(
            BEL.find_input_pin(rigs[0], "Source"))]
        # Through the server branch (server_anim.py), on its client pin: a
        # dedicated server takes the pose from before the slot.
        if len(feeding) == 1 and feeding[0].get_class().get_name() == BRANCH_CLASS:
            feeding = [PIN.get_owning_node(q) for q in linked(
                BEL.find_input_pin(feeding[0], CLIENT_PIN))]
        check(f"{FULL_BODY_SLOT} feeds the ControlRig, downstream of both blends",
              feeding == [slot_names[FULL_BODY_SLOT]],
              str([n.get_class().get_name() for n in feeding]))
        behind = [PIN.get_owning_node(q) for q in linked(
            BEL.find_input_pin(slot_names[FULL_BODY_SLOT], "Source"))]
        check(f"the hit blend -- the last one -- feeds {FULL_BODY_SLOT}",
              behind == [hit_blend],
              str([n.get_class().get_name() for n in behind]))


def run():
    check_anim_graph_patch()
