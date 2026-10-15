"""The drawn MetaHuman's fingers on the gun: the fitted hands of
drawn_grip_consts.CLIP laid over the retarget's fingers in the Body's own
anim Blueprint (asset_pipeline's ABP_MetaHuman_Retarget_UEFN), which is

    Retarget Pose From Mesh -> Output Pose

and becomes

    Retarget -> Layered blend per bone (each right finger from its root,
                    local space, weight GripRight) over Evaluate(clip, GripGun)
             -> Layered blend per bone (each left finger, weight GripLeft) over
                    TwoWay(TwoWay(Evaluate(GripGun), Evaluate(GripGun + 1),
                                  GripSights),
                           Evaluate(GripGun + 2), GripCarry)
             -> Output Pose

The clip holds three frames a gun at one a second (hold, sights, carry), so
an evaluator's explicit time is the frame; each frame is its own evaluator
(a pose is never linked to two inputs: root CLAUDE.md). The fingers are
taken whole from the clip, from the metacarpals and the thumb's first bone
down: they were fitted as the clip has them (drawn_grip_bake.py), the
wrists are the retarget's, pinned to the mannequin's (task 8).

The update copies the five from the pawn's weapon component
(weapon_component/drawn_grip.py writes them; SightBlend is the sights'
weight); with no component, or none fitted in hand, they stay 0 and the
retarget's fingers are drawn.

Authored from nothing each build: every node but the retarget, the output
and the update event is taken out first. build_gas_bridge.py rewrites only
the retarget node's settings, so it keeps this.
"""

import unreal

from asset_pipeline.gas_bridge_paths import ABP_RETARGET_UEFN
from combat.drawn_grip import roots
from combat.drawn_grip_consts import (
    CLIP, GRIP_CARRY_VAR, GRIP_GUN_VAR, GRIP_LEFT_VAR, GRIP_RIGHT_VAR, GRIP_SIGHTS_VAR,
)
from combat.drawn_grip_vars import ANIM
from combat.log import _log
from combat.paths import WEAPON_COMP_BP_PATH
from combat.stance_clips import _blend, _evaluator
from combat.weapon_component import vars as WV
from uebp.g import _G
from uebp.graph import BEL, BGE, PIN, _assets, _connect, _node, _palette, _pin, _set, out, then
from uebp.layout import arrange
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.locomotion import FN_TRY_GET_PAWN_OWNER, NODE_EVENT_UPDATE_ANIM
from uebp.nodes.math import FN_ADD_FF
from uebp.nodes.palette import NODE_LAYERED_BLEND
from uebp.nodes.system import FN_IS_VALID
from uebp.vars import declare_missing

ROOT_CLASS = "AnimGraphNode_Root"
RETARGET_CLASS = "AnimGraphNode_RetargetPoseFromMesh"
LAYERED_CLASS = "AnimGraphNode_LayeredBoneBlend"
UPDATE_EVENT = "BlueprintUpdateAnimation"
COMP_CLASS = f"{WEAPON_COMP_BP_PATH}.{WEAPON_COMP_BP_PATH.rsplit('/', 1)[1]}_C"
# The weapon component's variable each of the anim Blueprint's is copied from.
COPIED = ((GRIP_GUN_VAR, GRIP_GUN_VAR), (GRIP_RIGHT_VAR, GRIP_RIGHT_VAR),
          (GRIP_LEFT_VAR, GRIP_LEFT_VAR), (GRIP_SIGHTS_VAR, str(WV.SightBlend)),
          (GRIP_CARRY_VAR, GRIP_CARRY_VAR))


def _class(node):
    return node.get_class().get_name()


def _the(ed, cls):
    found = [n for n in ed.list_all_nodes() if _class(n) == cls]
    if len(found) != 1:
        raise RuntimeError(f"{ABP_RETARGET_UEFN}: expected one {cls}, found {len(found)}")
    return found[0]


def _fingers(blend, side):
    """Each of ``side``'s fingers from its root down, in local space."""
    filters = []
    for bone in roots(side):
        f = unreal.BranchFilter()
        f.set_editor_property("bone_name", bone)
        f.set_editor_property("blend_depth", 0)
        filters.append(f)
    layer = unreal.InputBlendPose()
    layer.set_editor_property("branch_filters", filters)
    inner = blend.get_editor_property("node")
    inner.set_editor_property("layer_setup", [layer])
    inner.set_editor_property("blend_weights", [0.0])
    inner.set_editor_property("mesh_space_rotation_blend", False)
    blend.set_editor_property("node", inner)
    got = blend.get_editor_property("node").get_editor_property("layer_setup")
    if [str(f.get_editor_property("bone_name")) for f in
            got[0].get_editor_property("branch_filters")] != roots(side):
        raise RuntimeError(f"the {side} hand's filters did not stick")


def _layer(ed, base, pose, weight, side):
    blend = _palette(ed, NODE_LAYERED_BLEND)
    _fingers(blend, side)
    _connect(base, _pin(blend, "BasePose"))
    _connect(pose, _pin(blend, "BlendPoses_0"))
    _connect(weight, _pin(blend, "BlendWeights_0"))
    return out(blend, "Pose")


def _author_anim_graph(ed, clip):
    root, retarget = _the(ed, ROOT_CLASS), _the(ed, RETARGET_CLASS)
    keep = {root.get_name(), retarget.get_name()}
    stale = [n for n in ed.list_all_nodes() if n.get_name() not in keep]
    if stale:
        ed.remove_nodes(stale)
    PIN.break_pin_links(_pin(root, "Result"))

    def get(var):
        return out(ed.add_get_member_variable_node(var), var)

    def frame(k):
        if not k:
            return out(_evaluator(ed, clip, get(GRIP_GUN_VAR)), "Pose")
        at = _plus(ed, get(GRIP_GUN_VAR), float(k))
        return out(_evaluator(ed, clip, at), "Pose")

    right = _layer(ed, out(retarget, "Pose"), frame(0), get(GRIP_RIGHT_VAR), "r")
    sights = _blend(ed, frame(0), frame(1), get(GRIP_SIGHTS_VAR))
    left_pose = _blend(ed, out(sights, "Pose"), frame(2), get(GRIP_CARRY_VAR))
    left = _layer(ed, right, out(left_pose, "Pose"), get(GRIP_LEFT_VAR), "l")
    _connect(left, _pin(root, "Result"))
    ed.add_comment_to_nodes(
        f"The fingers fitted to each gun ({clip.get_name()}: three frames a gun, hold, "
        "sights, carry) over the retarget's, each finger from its root in local space: "
        f"the right by {GRIP_RIGHT_VAR}, the left by {GRIP_LEFT_VAR}. "
        "Scripts/combat/drawn_grip_graph.py.",
        [n for n in ed.list_all_nodes() if n.get_name() not in keep])


def _plus(ed, a, b):
    """a + the literal b, as a pin (the constant on B)."""
    n = _node(ed, FN_ADD_FF)
    _connect(a, _pin(n, "A"))
    _set(n, "B", b)
    return out(n)


def _author_update(events):
    update = [n for n in events.list_all_nodes()
              if UPDATE_EVENT in str(BEL.get_node_title(n)).replace(" ", "")]
    if len(update) > 1:
        raise RuntimeError(f"{len(update)} {UPDATE_EVENT} events")
    update = update[0] if update else _palette(events, NODE_EVENT_UPDATE_ANIM)
    stale = [n for n in events.list_all_nodes() if n.get_name() != update.get_name()]
    if stale:
        events.remove_nodes(stale)
    g = _G(events)
    pawn = out(g.call(FN_TRY_GET_PAWN_OWNER))
    comp = g.call(FN_GET_COMP, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(COMP_CLASS)
    there, _none = g.branch(out(g.call(FN_IS_VALID, Object=out(comp))),
                            [then(update)])
    tail = there
    for var, theirs in COPIED:
        tail = g.put(var, g.iget(out(comp), theirs, COMP_CLASS), [tail])
    events.add_comment_to_nodes(
        "The drawn hands' weights, copied off the pawn's weapon component, which writes "
        "them (Scripts/combat/weapon_component/drawn_grip.py).", g.made)


def patch_drawn_grip():
    """Lay the fitted hands over the drawn body's fingers. After the weapon
    component, whose variables the update reads."""
    eas = _assets()
    if not eas.does_asset_exist(CLIP):
        raise RuntimeError(f"no {CLIP}: run Scripts/build_drawn_grip.py")
    if not unreal.load_class(None, COMP_CLASS):
        raise RuntimeError(f"{COMP_CLASS} did not load")
    clip, bp = eas.load_asset(CLIP), eas.load_asset(ABP_RETARGET_UEFN)
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    events = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed or not events:
        raise RuntimeError(f"{ABP_RETARGET_UEFN} lacks its AnimGraph or its EventGraph")
    declare_missing(ed, ANIM)
    _author_anim_graph(ed, clip)
    _author_update(events)
    arrange(ed)
    arrange(events)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{ABP_RETARGET_UEFN} failed to compile after the drawn grip")
    eas.save_loaded_asset(bp)
    _log(f"{bp.get_name()}: {clip.get_name()} over the fingers, right from "
         f"{', '.join(roots('r'))}, left from {', '.join(roots('l'))}")
    return bp
