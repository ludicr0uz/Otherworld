"""mixamo_retarget -- carry the imported Mixamo clips onto a creature:
IK_XBot (once), RTG_<Creature>_from_XBot, and a batch retarget of every clip
into /Game/Sourced/Mixamo/<Creature>/.

The retargeter is built by the same retarget_rig.build_retargeter the
mannequin one is, so it inherits every correction that one earned: root
motion off and the pelvis's horizontal travel zeroed (a Mixamo walk exported
without "In Place" carries its hips metres forward, and a wanderer is moved by
CharacterMovement), the target pose auto-aligned chain to chain, and the
fingers kept in their bind pose.  The palm calibration is not repeated: it is
measured against the mannequin's reference clip, and both ends here use
Mixamo's bone axes, so there is no convention gap for it to close.
"""

import unreal

from asset_pipeline.mixamo_paths import (
    IK_XBOT, SOURCE_PREFIX, XBOT_MESH, mixamo_anim_dir, mixamo_prefix,
    mixamo_retargeter_path,
)
from asset_pipeline.retarget_rig import build_ik_rig, build_retargeter
from asset_pipeline.rig_chains import CHAINS_MIXAMO, RETARGET_ROOT_MIXAMO
from asset_pipeline.rig_util import _load, _log


def build_xbot_rig():
    return build_ik_rig(IK_XBOT, XBOT_MESH, CHAINS_MIXAMO, RETARGET_ROOT_MIXAMO)


def _asset_data(clip):
    """The batch operation takes FAssetData, not loaded objects."""
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    data = reg.get_asset_by_object_path(clip.get_path_name())
    if not data or not data.is_valid():
        raise RuntimeError(f"not in the asset registry: {clip.get_path_name()}")
    return data


def retarget_clips(source_rig, creature, clips):
    """Every clip in ``clips`` onto ``creature``; returns the created assets.

    ``creature`` is the short name build_retarget.py uses (Zombie01); its
    target IK rig is the one build_retarget.py built, so that has to have run.
    """
    mesh = _load(f"/Game/Sourced/Characters/SKM_{creature}/SKM_{creature}")
    target_rig = _load(f"/Game/Sourced/Characters/Rigs/IK_{creature}")
    rtg = build_retargeter(source_rig, target_rig,
                           mixamo_retargeter_path(creature))

    # Wiped and regenerated in full, for build_retarget.py's reason: the batch
    # does not reliably overwrite in place, and a numbered duplicate is the
    # kind of asset that gets referenced by accident and then never updates.
    out_dir = mixamo_anim_dir(creature)
    if unreal.EditorAssetLibrary.does_directory_exist(out_dir):
        unreal.EditorAssetLibrary.delete_directory(out_dir)
    unreal.EditorAssetLibrary.make_directory(out_dir)
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()

    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget",
                               [_asset_data(c) for c in clips])
    inputs.set_editor_property("source_mesh", _load(XBOT_MESH))
    inputs.set_editor_property("target_mesh", mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    inputs.set_editor_property("include_referenced_assets", False)
    # A_Mx_Scary_ZombieWalk -> A_Zombie01_Mx_Scary_ZombieWalk
    inputs.set_editor_property("search", SOURCE_PREFIX)
    inputs.set_editor_property("replace", "")
    inputs.set_editor_property("prefix", mixamo_prefix(creature))
    inputs.set_editor_property("target_path", out_dir)
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)
    created = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    _log(f"{creature}: {len(created)} Mixamo clips -> {out_dir}")
    if len(created) != len(clips):
        raise RuntimeError(f"{creature}: retargeted {len(created)} of "
                           f"{len(clips)} Mixamo clips")
    unreal.EditorAssetLibrary.save_directory(out_dir, only_if_is_dirty=False)
    return created
