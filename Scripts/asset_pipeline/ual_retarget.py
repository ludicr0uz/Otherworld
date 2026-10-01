"""ual_retarget -- carry every Quaternius UAL clip onto a character: IK_UAL1
and IK_UAL2 (once each), RTG_<Character>_from_<Pack>, and a batch retarget
into /Game/Sourced/Quaternius/UAL/<Character>/.

The retargeter is retarget_rig.build_retargeter, like the mannequin's and
X Bot's, so it inherits their corrections: root motion off, the pelvis's
horizontal travel zeroed, the target pose aligned chain to chain and the
fingers kept in their bind pose.

The palms are calibrated the way build_retarget.py calibrates them against
the mannequin: retarget once, measure the whole turn from the character's
hand onto the UAL hand in an idle, and retarget again with that turn in the
retarget pose.  The UAL rig is named the mannequin's way but is not the
mannequin, so the measurement has to be made against its own skin.
"""

import unreal

from asset_pipeline.palm_twist import (
    PALM_TOLERANCE_DEG, measure_clip_hand_turn, measure_clip_palm_twist,
)
from asset_pipeline.quaternius_paths import (
    PALM_CALIBRATION, ual_anim_dir, ual_clip, ual_ik_rig, ual_mesh, ual_prefix,
    ual_retargeter_path,
)
from asset_pipeline.retarget_rig import build_ik_rig, build_retargeter
from asset_pipeline.rig_chains import (
    CHAINS_UAL, RETARGET_ROOT_UAL, ROOT_MOTION_BONE_UAL,
)
from asset_pipeline.rig_util import _load, _log


def build_ual_rig(short):
    return build_ik_rig(ual_ik_rig(short), ual_mesh(short), CHAINS_UAL,
                        RETARGET_ROOT_UAL, root_motion_bone=ROOT_MOTION_BONE_UAL)


def _asset_data(clip):
    """The batch operation takes FAssetData, not loaded objects."""
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    data = reg.get_asset_by_object_path(clip.get_path_name())
    if not data or not data.is_valid():
        raise RuntimeError(f"not in the asset registry: {clip.get_path_name()}")
    return data


def _batch(rtg, short, character, mesh, clips):
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget", [_asset_data(c) for c in clips])
    inputs.set_editor_property("source_mesh", _load(ual_mesh(short)))
    inputs.set_editor_property("target_mesh", mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    inputs.set_editor_property("include_referenced_assets", False)
    # A_UAL1_Crouch_Idle_Loop -> A_Adventurer01_UAL1_Crouch_Idle_Loop
    # Not a bare "A_": clip names hold it too (A_TPose, Sword_Regular_A_Rec).
    inputs.set_editor_property("search", f"A_{short}_")
    inputs.set_editor_property("replace", f"{short}_")
    inputs.set_editor_property("prefix", ual_prefix(character))
    inputs.set_editor_property("target_path", ual_anim_dir(character))
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)
    created = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    if len(created) != len(clips):
        raise RuntimeError(f"{character}: retargeted {len(created)} of "
                           f"{len(clips)} {short} clips")
    return created


def _fresh(folder):
    # Wiped and regenerated in full, for build_retarget.py's reason: the batch
    # does not reliably overwrite in place.
    if unreal.EditorAssetLibrary.does_directory_exist(folder):
        unreal.EditorAssetLibrary.delete_directory(folder)
    unreal.EditorAssetLibrary.make_directory(folder)
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()


def retarget_ual(character, packs):
    """Every clip of every pack in ``packs`` ({short: {name: clip}}) onto
    ``character``, whose IK rig build_retarget.py built.  Returns the worst
    palm roll left, in degrees."""
    mesh = _load(f"/Game/Sourced/Characters/SKM_{character}/SKM_{character}")
    target_rig = _load(f"/Game/Sourced/Characters/Rigs/IK_{character}")
    cal_short, cal_name = PALM_CALIBRATION
    src_mesh = _load(ual_mesh(cal_short))
    src_clip = packs[cal_short][cal_name]

    # The calibration pack first: its idle is what the hands are measured on,
    # and the turn it gives is the same for the other pack (the same rig).
    order = [cal_short] + [s for s in packs if s != cal_short]
    rigs = {short: build_ual_rig(short) for short in order}
    rtg = build_retargeter(rigs[cal_short], target_rig,
                           ual_retargeter_path(character, cal_short))
    _fresh(ual_anim_dir(character))
    _batch(rtg, cal_short, character, mesh, [src_clip])
    turn = measure_clip_hand_turn(
        src_clip, _load(ual_clip(character, cal_short, cal_name)), mesh,
        src_mesh=src_mesh)
    _log(f"{character}: UAL hand turn before: "
         + ", ".join(f"{k} {d:+.1f}" for k, (_a, d) in turn.items()))

    _fresh(ual_anim_dir(character))
    total = 0
    for short in order:
        rtg = build_retargeter(rigs[short], target_rig,
                               ual_retargeter_path(character, short),
                               palm_angles=turn)
        total += len(_batch(rtg, short, character, mesh,
                            list(packs[short].values())))
    unreal.EditorAssetLibrary.save_directory(ual_anim_dir(character),
                                             only_if_is_dirty=False)

    after = measure_clip_palm_twist(
        src_clip, _load(ual_clip(character, cal_short, cal_name)), mesh,
        src_mesh=src_mesh)
    worst = max(abs(v) for v in after.values())
    _log(f"{character}: {total} UAL clips -> {ual_anim_dir(character)}, palm "
         "roll after: " + ", ".join(f"{k} {v:+.1f}" for k, v in after.items()))
    if worst > PALM_TOLERANCE_DEG:
        raise RuntimeError(f"{character}: palms {worst:.1f} deg off the UAL "
                           f"hands after correction (tolerance {PALM_TOLERANCE_DEG})")
    return worst
