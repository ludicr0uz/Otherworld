"""mixamo_player -- the player's melee set: the clips mixamo_paths.PLAYER_CLIPS
names, imported onto SK_XBot and retargeted onto the player's skeleton, the
Game Animation Sample's UEFN mannequin (Scripts/asset_pipeline/CLAUDE.md, "The
skeleton bridge"), into /Game/Sourced/Mixamo/UEFN_Player.

The retargeter is the plain one the game's other clips reached that skeleton
by (retarget_to_uefn.py, import_lyra.py): in place, the target's pose aligned
chain to chain, IK_XBot to build_gas_bridge.py's IK_UEFN_Mannequin_Source.
Every copy has its root motion off: no clip played into a slot may have it
(Scripts/combat/CLAUDE.md, "The weapon layers").

What the game plays is not these but combat/melee_clips.py's bakes of them
(the right hand's fingers closed on a handle), so this folder is wiped and
written whole like every retarget's.
"""

import os

import unreal

from asset_pipeline.gas_bridge_paths import IK_UEFN, PLAYER_FAMILY, PLAYER_MESH_GAS
from asset_pipeline.mixamo_import import _import, extract_packs
from asset_pipeline.mixamo_paths import (
    IK_XBOT, PLAYER_CLIPS, PLAYER_PACKS, SOURCE_PREFIX, XBOT_MESH, XBOT_SKELETON, clip_stem,
    mixamo_anim_dir,
    mixamo_prefix, mixamo_retargeter_path, pack_dir, player_clip, source_clip,
)
from asset_pipeline.mixamo_retarget import _asset_data
from asset_pipeline.plain_retarget import build_plain_retargeter
from asset_pipeline.rig_chains import CHAINS_MANNEQUIN, CHAINS_MIXAMO
from asset_pipeline.rig_util import _load, _log
from asset_pipeline.ual_retarget import _fresh

EAL = unreal.EditorAssetLibrary


def _fbx_of(folder, stem):
    found = [f for f in sorted(os.listdir(folder))
             if f.lower().endswith(".fbx") and clip_stem(f) == stem]
    if len(found) != 1:
        raise RuntimeError(f"{folder}: {len(found)} FBX files for the clip {stem!r} "
                           "(mixamo_paths.PLAYER_CLIPS names one)")
    return os.path.join(folder, found[0])


def import_player_clips(skeleton):
    """Each clip of PLAYER_CLIPS -> A_Mx_<Pack>_<Clip> on SK_XBot.  Returns
    {role: AnimSequence}."""
    folders = extract_packs(PLAYER_PACKS)
    out = {}
    for role, (short, stem) in PLAYER_CLIPS.items():
        path = source_clip(short, stem)
        imported = _import(_fbx_of(folders[short], stem), pack_dir(short),
                           path.rsplit("/", 1)[1], skeleton=skeleton)
        clip = next((a for a in imported if isinstance(a, unreal.AnimSequence)), None)
        if clip is None or clip.get_editor_property("skeleton") != skeleton:
            raise RuntimeError(f"{path}: not imported as a clip on {skeleton.get_name()}")
        out[role] = clip
    _log(f"the player's melee set: {len(out)} clips onto {skeleton.get_name()}")
    return out


def retarget_player_clips(source_rig, clips):
    """``clips`` ({role: clip on SK_XBot}) onto the player's skeleton, in
    place.  Returns the created assets."""
    for need in (IK_UEFN, PLAYER_MESH_GAS):
        if not EAL.does_asset_exist(need):
            raise RuntimeError(f"{need} is not here: run Scripts/asset_pipeline/"
                               "build_gas_bridge.py first")
    mesh = _load(PLAYER_MESH_GAS)
    # The fingers: Mixamo's table has the chains the rigs share.
    chains = sorted(set(CHAINS_MIXAMO) & set(CHAINS_MANNEQUIN))
    rtg = build_plain_retargeter(source_rig, _load(IK_UEFN),
                                 mixamo_retargeter_path(PLAYER_FAMILY), chains)
    out_dir = mixamo_anim_dir(PLAYER_FAMILY)
    _fresh(out_dir)
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget",
                               [_asset_data(c) for c in clips.values()])
    inputs.set_editor_property("source_mesh", _load(XBOT_MESH))
    inputs.set_editor_property("target_mesh", mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    inputs.set_editor_property("include_referenced_assets", False)
    inputs.set_editor_property("search", SOURCE_PREFIX)
    inputs.set_editor_property("replace", "")
    inputs.set_editor_property("prefix", mixamo_prefix(PLAYER_FAMILY))
    inputs.set_editor_property("target_path", out_dir)
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)
    created = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    if len(created) != len(clips):
        raise RuntimeError(f"retargeted {len(created)} of {len(clips)} of the "
                           "player's Mixamo clips")
    for role in clips:
        _load(player_clip(role)).set_editor_property("enable_root_motion", False)
    EAL.save_directory(out_dir, only_if_is_dirty=False)
    _log(f"the player's melee set: {len(created)} clips -> {out_dir}")
    return created


def check_player_clips(clips, check):
    """Each role's copy is a clip on the player's skeleton, in place, as long
    as Mixamo's."""
    skeleton = _load(PLAYER_MESH_GAS).get_editor_property("skeleton")
    for role, source in clips.items():
        path = player_clip(role)
        asset = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
        check(f"Player {role}: {path.rsplit('/', 1)[1]} On {skeleton.get_name()}, In Place",
              isinstance(asset, unreal.AnimSequence)
              and asset.get_editor_property("skeleton") == skeleton
              and not asset.get_editor_property("enable_root_motion")
              and abs(asset.get_play_length() - source.get_play_length()) < 0.05,
              f"({asset.get_play_length():.2f} s)" if asset else "(missing)")


def import_player_set(check):
    """The whole step: import, retarget, check.  X Bot and its rig are the
    creatures' packs' (import_mixamo.py's steps 2 and 3): every Mixamo
    download is on that skeleton."""
    clips = import_player_clips(_load(XBOT_SKELETON))
    retarget_player_clips(_load(IK_XBOT), clips)
    check_player_clips(clips, check)
