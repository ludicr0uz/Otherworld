"""build_metahuman_retarget.py -- what drives the MetaHuman body from the
mannequin.  Editor-side.

    python3 Scripts/asset_pipeline/import_metahuman.py                      # host-side, first
    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/build_metahuman_retarget.py

Writes, under /Game/Sourced/MetaHuman:

    IK_MetaHuman                   the mannequin's chain table (rig_chains.
                                   CHAINS_MANNEQUIN) on the MetaHuman body:
                                   metahuman_base_skel names its core bones
                                   exactly as SK_Mannequin does, so the same
                                   table fits both and the chain mapping is
                                   exact.
    RTG_MetaHuman_from_Mannequin   IK_Mannequin (build_retarget.py's; built
                                   here if it is not) -> IK_MetaHuman.  Both
                                   rigs rest in Epic's A-pose, so no retarget
                                   pose alignment: the Meshy corrections in
                                   retarget_rig.build_retargeter are not
                                   wanted and this does not use it.
    ABP_MetaHuman_Retarget         the sample's ABP_MetaHuman_m_med_nrw_
                                   Retargeting, duplicated (its whole graph is
                                   one Retarget Pose From Mesh node reading
                                   the PARENT skeletal mesh component) and
                                   pointed at the retargeter above.

A MetaHuman body component wearing ABP_MetaHuman_Retarget, attached under a
mesh component that runs the mannequin's anim blueprint, follows it: every
clip, slot, blend and Control Rig the mannequin plays reaches the MetaHuman
through the retargeter, frame by frame, with nothing retargeted on disk.
combat/skin.py wears it (SKIN_METAHUMAN) when player_body.PLAYER_RIG says
"metahuman".

Idempotent: assets are reused and rebuilt in place.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]          # a warm editor keeps yesterday's modules

from asset_pipeline.metahuman_paths import (                       # noqa: E402
    ABP_RETARGET, ABP_RETARGET_SAMPLE, BODY_MESH, IK_METAHUMAN, RTG_FROM_MANNEQUIN,
    SOURCED_DIR,
)
from asset_pipeline.retarget_paths import IK_MANNEQUIN, MANNEQUIN_MESH, RIG_DIR  # noqa: E402
from asset_pipeline.retarget_rig import build_ik_rig              # noqa: E402
from asset_pipeline.rig_chains import (                            # noqa: E402
    CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN, ROOT_MOTION_BONE_MANNEQUIN,
)
from asset_pipeline.rig_util import _load, _log, _reuse_or_create  # noqa: E402

EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary


def build_retargeter(source_rig, target_rig, pkg, target_mesh):
    """Source -> target with the default op stack and an exact chain map.
    Nothing is aligned: both rigs are Epic's A-pose."""
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


def build_anim_blueprint(rtg):
    """The sample's retargeting anim BP, duplicated and pointed at ``rtg``."""
    if not EAL.does_asset_exist(ABP_RETARGET):
        if not EAL.duplicate_asset(ABP_RETARGET_SAMPLE, ABP_RETARGET):
            raise RuntimeError(f"could not duplicate {ABP_RETARGET_SAMPLE}")
    bp = _load(ABP_RETARGET)
    node = _retarget_node(bp)
    inner = node.get_editor_property("node")
    inner.set_editor_property("ik_retargeter_asset", rtg)
    # Read the parent component's pose: the mannequin the body hangs under.
    inner.set_editor_property("retarget_from",
                              unreal.RetargetSourceMode.PARENT_SKELETAL_MESH_COMPONENT)
    node.set_editor_property("node", inner)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{ABP_RETARGET} failed to compile")
    EAL.save_asset(ABP_RETARGET)
    got = _retarget_node(_load(ABP_RETARGET)).get_editor_property("node")
    if got.get_editor_property("ik_retargeter_asset") != rtg:
        raise RuntimeError("the retargeter did not stick on the anim BP's node")
    _log(f"{ABP_RETARGET}: retargets from the parent component through "
         f"{rtg.get_name()}")
    return bp


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    if not EAL.does_asset_exist(BODY_MESH):
        raise RuntimeError(f"{BODY_MESH} is not imported: run "
                           "Scripts/asset_pipeline/import_metahuman.py first")
    for d in (RIG_DIR, SOURCED_DIR):
        if not EAL.does_directory_exist(d):
            EAL.make_directory(d)
    src = build_ik_rig(IK_MANNEQUIN, MANNEQUIN_MESH, CHAINS_MANNEQUIN,
                       RETARGET_ROOT_MANNEQUIN,
                       root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    tgt = build_ik_rig(IK_METAHUMAN, BODY_MESH, CHAINS_MANNEQUIN,
                       RETARGET_ROOT_MANNEQUIN,
                       root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    rtg = build_retargeter(src, tgt, RTG_FROM_MANNEQUIN, _load(BODY_MESH))
    build_anim_blueprint(rtg)
    _log("done")


if __name__ == "__main__":
    main()
