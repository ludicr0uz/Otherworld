"""import_lyra.py -- Lyra's clips the game plays, onto the player's skeleton.
Editor-side:

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/import_lyra.py

The pack itself is the user's to add (a Fab asset: the Lyra Starter Game's
Content/Characters under Content/Sourced/Lyra, lyra_paths.py); this is what a
script can do with it.  Lyra's clips are on its own SK_Mannequin and the
player's hidden mesh is the Game Animation Sample's UEFN mannequin
(Scripts/asset_pipeline/CLAUDE.md, "The skeleton bridge"), so each row of
lyra_paths.CLIPS is retargeted onto that one, as retarget_to_uefn.py does the
game's older clips: read off Lyra's Manny through a rig of the mannequin's
chain table (the bones are named alike), by the plain retargeter, in place.

Writes, under /Game/Sourced/Lyra (not committed, as the pack is not):
    Rig/IK_Lyra_Mannequin_Source, Rig/RTG_UEFN_from_Lyra
    UEFN_Player/A_UEFN_Player_<clip>      wiped and written whole

A new clip from Lyra is a row of lyra_paths.CLIPS and a re-run.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline.gas_bridge_paths import IK_UEFN, PLAYER_MESH_GAS   # noqa: E402
from asset_pipeline.lyra_paths import (                                # noqa: E402
    CLIPS, CONTENT_DIR, IK_LYRA, RIG_DIR, RTG_UEFN_FROM_LYRA, SKELETON, SOURCE_MESH,
    UEFN_DIR, UEFN_PREFIX, uefn_clip,
)
from asset_pipeline.plain_retarget import build_plain_retargeter       # noqa: E402
from asset_pipeline.retarget_rig import build_ik_rig                   # noqa: E402
from asset_pipeline.rig_chains import (                                # noqa: E402
    CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN, ROOT_MOTION_BONE_MANNEQUIN,
)
from asset_pipeline.rig_util import _load                              # noqa: E402
from asset_pipeline.ual_retarget import _asset_data, _fresh            # noqa: E402

EAL = unreal.EditorAssetLibrary


def _log(msg):
    unreal.log_warning(f"[LYRA] {msg}")


def _batch(rtg, target_mesh, clips):
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget", [_asset_data(c) for c in clips])
    inputs.set_editor_property("source_mesh", _load(SOURCE_MESH))
    inputs.set_editor_property("target_mesh", target_mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    inputs.set_editor_property("include_referenced_assets", False)
    inputs.set_editor_property("prefix", UEFN_PREFIX)
    inputs.set_editor_property("target_path", UEFN_DIR)
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)
    created = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    if len(created) != len(clips):
        raise RuntimeError(f"retargeted {len(created)} of {len(clips)} Lyra clips")
    return created


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    for need, by in ((SOURCE_MESH, f"the user: Lyra's Content/Characters under {CONTENT_DIR}"),
                     (IK_UEFN, "Scripts/asset_pipeline/build_gas_bridge.py"),
                     (PLAYER_MESH_GAS, "Scripts/asset_pipeline/build_gas_bridge.py")):
        if not EAL.does_asset_exist(need):
            raise RuntimeError(f"{need} is not here: it comes from {by}")
    # A pack that loads with no skeleton has lost its redirect: the files
    # name Lyra's /Game/Characters/Heroes, not this folder.
    if EAL.load_asset(SKELETON) is None or _load(CLIPS[0]).get_editor_property("skeleton") is None:
        raise RuntimeError("Lyra's clips load without their skeleton: is lyra_paths."
                           "REDIRECTED in Config/DefaultEngine.ini, and the editor "
                           "started since?")
    mesh = _load(PLAYER_MESH_GAS)
    if not EAL.does_directory_exist(RIG_DIR):
        EAL.make_directory(RIG_DIR)
    source = build_ik_rig(IK_LYRA, SOURCE_MESH, CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN,
                          root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    rtg = build_plain_retargeter(source, _load(IK_UEFN), RTG_UEFN_FROM_LYRA,
                                 sorted(CHAINS_MANNEQUIN))
    _fresh(UEFN_DIR)
    _batch(rtg, mesh, [_load(p) for p in CLIPS])
    EAL.save_directory(RIG_DIR, only_if_is_dirty=False)

    skeleton = mesh.get_editor_property("skeleton")
    ok = True
    for source_clip in CLIPS:
        path = uefn_clip(source_clip)
        asset = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
        if isinstance(asset, unreal.AnimSequence):
            # No clip played into a slot may have root motion (Scripts/combat/
            # CLAUDE.md, "The weapon layers"): the player would stand rooted.
            asset.set_editor_property("enable_root_motion", False)
            EAL.save_loaded_asset(asset)
        good = (isinstance(asset, unreal.AnimSequence)
                and asset.get_editor_property("skeleton") == skeleton
                and not asset.get_editor_property("enable_root_motion")
                and abs(asset.get_play_length() - _load(source_clip).get_play_length()) < 0.05)
        ok = ok and good
        unreal.log_warning(f"[VERIFY] {'PASS' if good else 'FAIL'} {path.rsplit('/', 1)[1]} "
                           f"is a clip on {skeleton.get_name()}, in place, as long as Lyra's")
    _log(f"{len(CLIPS)} clip(s) onto {skeleton.get_name()}")
    return ok


if __name__ == "__main__":
    main()
