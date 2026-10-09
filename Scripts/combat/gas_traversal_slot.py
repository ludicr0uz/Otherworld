"""Where the sample's traversal montages reach the body (task G5): the
motion-matching anim Blueprint's own Slot(DefaultSlot), in the pose line only
while a traversal plays. Called by gas_locomotion.py, which owns that graph;
gas_traversal.py is the component and the jump key.

The sample has its slot in the line always, in front of the root's offset.
Here it cannot be: the weapon layers' ready and hold poses play in a slot of
the same name (anim_blueprint.AIM_SLOT, upper body only, in the layers'
graph), so with the sample's slot in the line a raised gun or a knife in hand
was the whole body's pose, and the motion matching under it stopped being
updated (found by probe_stance_clips: crouched with the gun up, the body
stood). So:

    pose -+-> Slot(DefaultSlot) -> [true ]
          |                        Blend Poses by bool(OwTraversing) -> Offset Root Bone
          +----------------------> [false]

OwTraversing is the traversal component's DoingTraversalAction, copied each
update by Update_PropertiesFromCharacter. It goes true on the frame the
montage starts (the slot blends it in over the pose itself, so the switch is
at once) and false as the montage starts to blend out (the switch back takes
SLOT_OUT_S). While it is true the weapon component holds the hand's pose off
(weapon_component/carry.py), so the only montage in the slot is the traversal's.
"""

from combat.gas_locomotion_consts import OFFSET_ROOT_CLASS, TRAVERSING
from combat.gas_moves_tuning import DOING_VAR, TRAVERSAL_BP
from combat.server_anim_consts import BRANCH_CLASS, FLAG_PIN
from uebp.graph import BEL, PIN, _connect, _palette, _pin, _set, out
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.palette import NODE_BLEND_BY_BOOL
from uebp.nodes.system import FN_IS_VALID
from uebp.pose_share import fed

TRAVERSAL_CLASS = f"{TRAVERSAL_BP}.{TRAVERSAL_BP.rsplit('/', 1)[1]}_C"
TRUE_PIN, FALSE_PIN = "BlendPose_0", "BlendPose_1"
# Into the slot at once; back to the motion matching over this long.
SLOT_IN_S, SLOT_OUT_S = 0.0, 0.25


def _fed(pin):
    # Read through a cached pose: a verifier calls these walks on the graph
    # as it is worn (uebp/pose_share.py).
    return fed(pin)


def traversal_branches(ed):
    """The blends by bool that OwTraversing drives."""
    found = []
    for node in ed.list_all_nodes():
        if node.get_class().get_name() != BRANCH_CLASS:
            continue
        flags = [PIN.get_owning_node(q) for q in _fed(_pin(node, FLAG_PIN))]
        if any(str(BEL.get_node_title(f)) == f"Get {TRAVERSING}" for f in flags):
            found.append(node)
    return found


def remove_traversal_slot(ed, slot):
    """Take the branch out and join the pose to what it fed; the slot is left
    out of the line, as gas_locomotion._remove_slot leaves it."""
    for branch in traversal_branches(ed):
        source, onward = _fed(_pin(branch, FALSE_PIN)), _fed(out(branch, "Pose"))
        flags = [PIN.get_owning_node(q) for q in _fed(_pin(branch, FLAG_PIN))]
        ed.remove_nodes([branch] + flags)
        PIN.break_pin_links(_pin(slot, "Source"))
        PIN.break_pin_links(out(slot, "Pose"))
        for pin in onward:
            _connect(source[0], pin)


def author_traversal_slot(ed, slot):
    """Put ``slot`` (out of the line) on the true arm of a blend by
    OwTraversing, in front of the root's offset."""
    offsets = [n for n in ed.list_all_nodes()
               if n.get_class().get_name() == OFFSET_ROOT_CLASS]
    if len(offsets) != 1:
        raise RuntimeError(f"expected one {OFFSET_ROOT_CLASS}, found {len(offsets)}")
    into = _pin(offsets[0], "Source")
    source = _fed(into)
    if not source:
        raise RuntimeError("the root's offset is fed by nothing")
    PIN.break_pin_links(into)
    branch = _palette(ed, NODE_BLEND_BY_BOOL)
    flag = ed.add_get_member_variable_node(TRAVERSING)
    _connect(out(flag, TRAVERSING), _pin(branch, FLAG_PIN))
    _connect(source[0], _pin(slot, "Source"))
    _connect(out(slot, "Pose"), _pin(branch, TRUE_PIN))
    _connect(source[0], _pin(branch, FALSE_PIN))
    inner = branch.get_editor_property("node")
    inner.set_editor_property("blend_time", [SLOT_IN_S, SLOT_OUT_S])
    branch.set_editor_property("node", inner)
    _set(branch, "BlendTime_0", SLOT_IN_S)
    _set(branch, "BlendTime_1", SLOT_OUT_S)
    _connect(out(branch, "Pose"), into)
    ed.add_comment_to_nodes(
        f"The sample's traversal montages (G5): its own slot is in the line only while "
        f"{TRAVERSING} (the traversal component is doing one). The weapon layers' ready "
        "and hold poses play in a slot of the same name, upper body only, in their own "
        "graph: here they would be the whole body's. Scripts/combat/gas_traversal_slot.py.",
        [branch, flag, slot])


def author_traversing_flag(g, char, execs):
    """OwTraversing = the pawn's traversal component's DoingTraversalAction,
    behind an IsValid (an anim instance in a preview has no such pawn)."""
    comp = g.call(FN_GET_COMP, self=char)
    _pin(comp, "ComponentClass").set_pin_value(TRAVERSAL_CLASS)
    there, _ = g.branch(out(g.call(FN_IS_VALID, Object=out(comp))), execs)
    return g.put(TRAVERSING, g.iget(out(comp), DOING_VAR, TRAVERSAL_CLASS), [there])
