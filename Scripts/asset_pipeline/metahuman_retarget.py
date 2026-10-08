"""metahuman_retarget -- the two pieces every bridge onto the MetaHuman body
is made of: a retargeter between two A-posed rigs, and the retargeting anim
blueprint pointed at it.  Shared by build_metahuman_retarget.py (the
mannequin's bridge) and build_gas_bridge.py (the UEFN mannequin's).
"""

import unreal

from asset_pipeline.metahuman_paths import ABP_RETARGET, ABP_RETARGET_SAMPLE
from asset_pipeline.rig_util import _load, _log, _reuse_or_create

EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary


def build_retargeter(source_rig, target_rig, pkg, target_mesh, align=False):
    """Source -> target with the default op stack and an exact chain map.
    Nothing is aligned unless ``align``: the mannequin and the MetaHuman
    both rest in Epic's A-pose.  ``align`` turns the target's chains onto
    the source's in the retarget pose, for a source that rests otherwise."""
    name = pkg.rsplit("/", 1)[1]
    rtg = _reuse_or_create(pkg, unreal.IKRetargeter, unreal.IKRetargetFactory())
    ctl = unreal.IKRetargeterController.get_controller(rtg)
    ctl.remove_all_ops()
    ctl.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_rig)
    ctl.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_rig)
    # The preview is what the retarget pose is measured on; the rig's own
    # mesh would do, but the body the player wears is the honest one.
    ctl.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_mesh)
    ctl.add_default_ops()
    ctl.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
    ctl.reset_retarget_pose(ctl.get_current_retarget_pose_name(
        unreal.RetargetSourceOrTarget.TARGET), [], unreal.RetargetSourceOrTarget.TARGET)
    if align:
        ctl.auto_align_all_bones(unreal.RetargetSourceOrTarget.TARGET,
                                 unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
    ops = [str(ctl.get_op_name(i)) for i in range(ctl.get_num_retarget_ops())]
    _log(f"{name}: ops {ops}")
    EAL.save_asset(pkg)
    return rtg


def _retarget_node(bp):
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
    if not ed:
        raise RuntimeError(f"{bp.get_name()} has no AnimGraph")
    nodes = [n for n in ed.list_all_nodes()
             if n.get_class().get_name() == "AnimGraphNode_RetargetPoseFromMesh"]
    if len(nodes) != 1:
        raise RuntimeError(f"{bp.get_name()}: expected one Retarget Pose From "
                           f"Mesh node, found {len(nodes)}")
    return nodes[0]


def build_anim_blueprint(rtg, pkg=ABP_RETARGET):
    """The sample's retargeting anim BP, duplicated as ``pkg`` and pointed
    at ``rtg``."""
    if not EAL.does_asset_exist(pkg):
        if not EAL.duplicate_asset(ABP_RETARGET_SAMPLE, pkg):
            raise RuntimeError(f"could not duplicate {ABP_RETARGET_SAMPLE}")
    bp = _load(pkg)
    node = _retarget_node(bp)
    inner = node.get_editor_property("node")
    inner.set_editor_property("ik_retargeter_asset", rtg)
    # Read the parent component's pose: the mannequin the body hangs under.
    inner.set_editor_property("retarget_from",
                              unreal.RetargetSourceMode.PARENT_SKELETAL_MESH_COMPONENT)
    node.set_editor_property("node", inner)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{pkg} failed to compile")
    EAL.save_asset(pkg)
    got = _retarget_node(_load(pkg)).get_editor_property("node")
    if got.get_editor_property("ik_retargeter_asset") != rtg:
        raise RuntimeError("the retargeter did not stick on the anim BP's node")
    _log(f"{pkg}: retargets from the parent component through "
         f"{rtg.get_name()}")
    return bp
