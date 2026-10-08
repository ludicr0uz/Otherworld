"""retarget_to_uefn.py -- the game's own clips, once, onto the Game Animation
Sample's skeleton.  Editor-side:

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/retarget_to_uefn.py

The player's hidden mesh is the sample's UEFN mannequin (Scripts/
asset_pipeline/CLAUDE.md, "The skeleton bridge"), and a clip belongs to one
skeleton: what the weapon layers play over the motion matching (combat/
weapon_layers.py) has to be on SK_UEFN_Mannequin.  This puts it there:

    the mannequin's   the two ready poses (MF_Rifle_Idle_ADS, MF_Pistol_
                      Idle_ADS), the punch (MM_Attack_01) and the six hit
                      reactions, read off the mannequin the player wore
                      (gas_bridge_paths.CLIPS_FROM_MESH) into
                      /Game/Sourced/Characters/Anims/UEFN_Player as
                      A_UEFN_Player_<clip>
    Quaternius's      the crouch, the crawl, the kneel and the throw
                      (quaternius_paths), read off the packs' own rig, not
                      off their mannequin copies (one retarget, not two),
                      into /Game/Sourced/Quaternius/UAL/UEFN_Player as
                      A_UEFN_Player_<Pack>_<Clip>

which is where combat/skin.SKIN_GAS looks.  The target rig is build_gas_
bridge.py's IK_UEFN_Mannequin_Source (the mannequin's chain table on the UEFN
mesh: every chain maps by name).  The retargeter is retarget_ual_to_
mannequin's plain one: in place, the target's pose aligned chain to chain,
since the UEFN mannequin rests with its arms at another angle than either
source.  Both folders are wiped and written whole.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline.gas_bridge_paths import (                        # noqa: E402
    CLIPS_FROM_MESH, IK_UEFN, PLAYER_FAMILY, PLAYER_MESH_GAS, RTG_UEFN_FROM_MANNEQUIN,
)
from asset_pipeline.plain_retarget import build_plain_retargeter     # noqa: E402
from asset_pipeline.quaternius_paths import (                        # noqa: E402
    CROUCH_IDLE, CROUCH_WALK, PRONE_CRAWL, SEARCH_KNEEL, THROW, ual_anim_dir, ual_clip,
    ual_retargeter_path, ual_source_clip,
)
from asset_pipeline.retarget_paths import (                          # noqa: E402
    AIM_SOURCES, HIT_SOURCES, IK_MANNEQUIN, MELEE_SOURCE, anim_dir, anim_prefix,
)
from asset_pipeline.rig_chains import CHAINS_MANNEQUIN               # noqa: E402
from asset_pipeline.rig_util import _load                            # noqa: E402
from asset_pipeline.ual_retarget import _asset_data, _batch, _fresh, build_ual_rig  # noqa: E402

EAL = unreal.EditorAssetLibrary
MANNEQUIN_CLIPS = AIM_SOURCES + (MELEE_SOURCE,) + HIT_SOURCES
UAL_CLIPS = (CROUCH_IDLE, CROUCH_WALK, PRONE_CRAWL, SEARCH_KNEEL, THROW)


def _log(msg):
    unreal.log_warning(f"[>UEFN] {msg}")


def mannequin_clip(source):
    """Where a mannequin clip's copy on the UEFN skeleton lands."""
    return f"{anim_dir(PLAYER_FAMILY)}/{anim_prefix(PLAYER_FAMILY)}{source.rsplit('/', 1)[1]}"


def _batch_mannequin(rtg, target_mesh):
    clips = [_load(p) for p in MANNEQUIN_CLIPS]
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget", [_asset_data(c) for c in clips])
    inputs.set_editor_property("source_mesh", _load(CLIPS_FROM_MESH))
    inputs.set_editor_property("target_mesh", target_mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    inputs.set_editor_property("include_referenced_assets", False)
    inputs.set_editor_property("prefix", anim_prefix(PLAYER_FAMILY))
    inputs.set_editor_property("target_path", anim_dir(PLAYER_FAMILY))
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)
    created = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    if len(created) != len(clips):
        raise RuntimeError(f"retargeted {len(created)} of {len(clips)} mannequin clips")
    return created


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    for need, by in ((IK_UEFN, "build_gas_bridge.py"), (PLAYER_MESH_GAS, "build_gas_bridge.py"),
                     (IK_MANNEQUIN, "build_metahuman_retarget.py")):
        if not EAL.does_asset_exist(need):
            raise RuntimeError(f"{need} is not here: run Scripts/asset_pipeline/{by} first")
    mesh = _load(PLAYER_MESH_GAS)
    target = _load(IK_UEFN)
    chains = sorted(CHAINS_MANNEQUIN)

    _fresh(anim_dir(PLAYER_FAMILY))
    rtg = build_plain_retargeter(_load(IK_MANNEQUIN), target, RTG_UEFN_FROM_MANNEQUIN, chains)
    total = len(_batch_mannequin(rtg, mesh))
    EAL.save_directory(anim_dir(PLAYER_FAMILY), only_if_is_dirty=False)

    _fresh(ual_anim_dir(PLAYER_FAMILY))
    for short in sorted({s for s, _clip in UAL_CLIPS}):
        rtg = build_plain_retargeter(build_ual_rig(short), target,
                                     ual_retargeter_path(PLAYER_FAMILY, short), chains)
        clips = [_load(ual_source_clip(s, c)) for s, c in UAL_CLIPS if s == short]
        total += len(_batch(rtg, short, PLAYER_FAMILY, mesh, clips))
    EAL.save_directory(ual_anim_dir(PLAYER_FAMILY), only_if_is_dirty=False)

    skeleton = mesh.get_editor_property("skeleton")
    ok = True
    for path in ([mannequin_clip(p) for p in MANNEQUIN_CLIPS]
                 + [ual_clip(PLAYER_FAMILY, s, c) for s, c in UAL_CLIPS]):
        asset = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
        if isinstance(asset, unreal.AnimSequence):
            # In place means the flag too. The mannequin's punch has root
            # motion on (150 cm forward); its copy here has none to give, and
            # a montage of a clip with the flag on takes the character's
            # movement over: the player would stand rooted for the punch.
            asset.set_editor_property("enable_root_motion", False)
            EAL.save_loaded_asset(asset)
        good = (isinstance(asset, unreal.AnimSequence)
                and asset.get_editor_property("skeleton") == skeleton
                and not asset.get_editor_property("enable_root_motion"))
        ok = ok and good
        unreal.log_warning(f"[VERIFY] {'PASS' if good else 'FAIL'} {path.rsplit('/', 1)[1]} "
                           f"is a clip on {skeleton.get_name()}, in place")
    _log(f"{total} clips onto {skeleton.get_name()}")
    return ok


if __name__ == "__main__":
    main()
