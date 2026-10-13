"""import_fal.py -- the Free Animation Library's clips the game plays, onto
the player's skeleton.  Editor-side:

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/import_fal.py

The pack itself is the user's to add (a Fab asset, fal_paths.py); this is what
a script can do with it.  Its clips are on its own copy of the UE5 mannequin
and the player's hidden mesh is the Game Animation Sample's UEFN mannequin
(Scripts/asset_pipeline/CLAUDE.md, "The skeleton bridge"), so each row of
fal_paths.CLIPS is retargeted onto that one as import_lyra.py does Lyra's (the
same rig, the same chain table, the plain retargeter).

The travel is out of the copy.  The pack's moving loops carry their travel on
the root bone with root motion off (the forward crawl's root ends 63 cm on):
played as they are, the body would slide forward through the loop and snap
back at its end.  The plain retargeter leaves the root where the reference
pose has it and holds the pelvis's travel across the ground (its Root Motion
op off, its Pelvis Motion op's horizontal scale 0), so a copy is in place as
it lands; each one is checked for it here (the root and the pelvis over the
whole clip), since the character's movement moves the body, never the clip.

Writes, under /Game/FreeAnimationLibrary (not committed, as the pack is not):
    Rig/IK_FAL_Mannequin_Source, Rig/RTG_UEFN_from_FAL
    UEFN_Player/A_UEFN_Player_<clip>      wiped and written whole

A new clip from the pack is a row of fal_paths.CLIPS and a re-run.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline.fal_paths import (                                 # noqa: E402
    CLIPS, CONTENT_DIR, IK_FAL, RIG_DIR, RTG_UEFN_FROM_FAL, SOURCE_MESH, UEFN_DIR,
    UEFN_PREFIX, uefn_clip,
)
from asset_pipeline.gas_bridge_paths import IK_UEFN, PLAYER_MESH_GAS   # noqa: E402
from asset_pipeline.plain_retarget import build_plain_retargeter       # noqa: E402
from asset_pipeline.ik_follow import follow_feet, off_cm               # noqa: E402
from asset_pipeline.retarget_rig import build_ik_rig                   # noqa: E402
from asset_pipeline.rig_chains import (                                # noqa: E402
    CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN, ROOT_MOTION_BONE_MANNEQUIN,
)
from asset_pipeline.rig_util import _bone_world, _load                 # noqa: E402
from asset_pipeline.ual_retarget import _asset_data, _fresh            # noqa: E402

EAL = unreal.EditorAssetLibrary
ROOT = ROOT_MOTION_BONE_MANNEQUIN
# How far a copy may still carry the body across the ground (cm).
IN_PLACE_CM = 0.5


def _log(msg):
    unreal.log_warning(f"[FAL] {msg}")


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
        raise RuntimeError(f"retargeted {len(created)} of {len(clips)} clips")
    return created


def _travel(clip, n=16):
    """How far ``clip`` carries the body across the ground (cm): the root's
    furthest from the origin, and the pelvis's spread, whichever is more."""
    length = clip.get_play_length()
    times = [length * i / n for i in range(n + 1)]
    root = max(_bone_world(clip, ROOT, t).length() for t in times)
    hips = [_bone_world(clip, RETARGET_ROOT_MANNEQUIN, t) for t in times]
    spread = max(max(getattr(p, a) for p in hips) - min(getattr(p, a) for p in hips)
                 for a in "xy")
    return max(root, spread)


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    for need, by in ((SOURCE_MESH, f"the user: the Free Animation Library under {CONTENT_DIR}"),
                     (IK_UEFN, "Scripts/asset_pipeline/build_gas_bridge.py"),
                     (PLAYER_MESH_GAS, "Scripts/asset_pipeline/build_gas_bridge.py")):
        if not EAL.does_asset_exist(need):
            raise RuntimeError(f"{need} is not here: it comes from {by}")
    mesh = _load(PLAYER_MESH_GAS)
    if not EAL.does_directory_exist(RIG_DIR):
        EAL.make_directory(RIG_DIR)
    source = build_ik_rig(IK_FAL, SOURCE_MESH, CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN,
                          root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    rtg = build_plain_retargeter(source, _load(IK_UEFN), RTG_UEFN_FROM_FAL,
                                 sorted(CHAINS_MANNEQUIN))
    _fresh(UEFN_DIR)
    _batch(rtg, mesh, [_load(p) for p in CLIPS])
    EAL.save_directory(RIG_DIR, only_if_is_dirty=False)

    skeleton = mesh.get_editor_property("skeleton")
    ok = True
    for source_clip in CLIPS:
        path = uefn_clip(source_clip)
        asset = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
        name = path.rsplit("/", 1)[1]
        if not isinstance(asset, unreal.AnimSequence):
            ok = False
            unreal.log_warning(f"[VERIFY] FAIL {name} was not written")
            continue
        # No clip of the stance line may have root motion (Scripts/combat/
        # CLAUDE.md, "The weapon layers"): the player would lie rooted.
        asset.set_editor_property("enable_root_motion", False)
        # The legs are the clip's: its IK feet onto its feet (ik_follow.py).
        follow_feet(asset)
        travel, ik_off = _travel(asset), off_cm(asset)
        good = (asset.get_editor_property("skeleton") == skeleton
                and not asset.get_editor_property("enable_root_motion")
                and travel < IN_PLACE_CM and ik_off < IN_PLACE_CM
                and abs(asset.get_play_length() - _load(source_clip).get_play_length()) < 0.05)
        ok = ok and good
        unreal.log_warning(f"[VERIFY] {'PASS' if good else 'FAIL'} {name} is a clip on "
                           f"{skeleton.get_name()}, as long as the pack's and in place "
                           f"(root and pelvis travel {travel:.2f} cm), its IK feet on its feet "
                           f"({ik_off:.2f} cm off)")
    _log(f"{len(CLIPS)} clip(s) onto {skeleton.get_name()}")
    return ok


if __name__ == "__main__":
    main()
