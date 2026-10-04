"""retarget_ual_to_mannequin.py -- the Quaternius library, once, onto the
mannequin's skeleton.

Editor-side:

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/retarget_ual_to_mannequin.py

A body bound to SK_Mannequin (mannequin_bind/) plays the mannequin's clips as
they are, and a clip from anywhere else is retargeted ONCE, onto the
mannequin, and then serves every bound body.  This is that once for the two
Universal Animation Library packs: every clip lands in
/Game/Sourced/Quaternius/UAL/Mannequin as A_Mannequin_<Pack>_<Clip>, which is
where combat/skin.SKIN_BOUND looks for the crouch, the crawl, the kneel and
the throw.  (The per-body flow does the same retarget per body:
ual_retarget.py, retarget_player_clips.py.)

The retargeter is the plain one.  retarget_rig.build_retargeter is written for
a Meshy target -- its finger offsets, its palm calibration and its mapping
check all name Meshy's bones -- and none of that is needed here: the UAL rig is
named and oriented the mannequin's way, so the chains map by name and the
palms need no turn.  What is kept from it is what the game needs of any clip:
in place (the character's movement moves the body, not the clip) and the
target's pose aligned chain to chain.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline.quaternius_paths import (                       # noqa: E402
    CROUCH_IDLE, CROUCH_WALK, PRONE_CRAWL, SEARCH_KNEEL, THROW, UAL_PACKS,
    pack_dir, ual_anim_dir, ual_clip, ual_retargeter_path)
from asset_pipeline.retarget_paths import IK_MANNEQUIN, MANNEQUIN_MESH   # noqa: E402
from asset_pipeline.retarget_rig import build_ik_rig                # noqa: E402
from asset_pipeline.rig_chains import (                             # noqa: E402
    CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN, ROOT_MOTION_BONE_MANNEQUIN)
from asset_pipeline.rig_util import _load, _reuse_or_create         # noqa: E402
from asset_pipeline.ual_retarget import _batch, _fresh, build_ual_rig   # noqa: E402

EAL = unreal.EditorAssetLibrary
MANNEQUIN = "Mannequin"
USED = (CROUCH_IDLE, CROUCH_WALK, PRONE_CRAWL, SEARCH_KNEEL, THROW)


def _log(msg):
    unreal.log_warning(f"[UAL>MANNEQUIN] {msg}")


def build_retargeter(source_rig, target_rig, pkg):
    rtg = _reuse_or_create(pkg, unreal.IKRetargeter, unreal.IKRetargetFactory())
    ctl = unreal.IKRetargeterController.get_controller(rtg)
    ctl.remove_all_ops()
    ctl.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_rig)
    ctl.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_rig)
    ctl.add_default_ops()
    ctl.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
    # In place, for retarget_rig.py's reasons: root motion off, and the
    # pelvis's travel across the ground zeroed (its bob is kept).
    for i in range(ctl.get_num_retarget_ops()):
        op = str(ctl.get_op_name(i))
        if op == "Root Motion":
            ctl.set_retarget_op_enabled(i, False)
        elif op == "Pelvis Motion":
            oc = ctl.get_op_controller(i)
            st = oc.get_settings()
            st.set_editor_property("scale_horizontal", 0.0)
            oc.set_settings(st)
    ctl.auto_align_all_bones(unreal.RetargetSourceOrTarget.TARGET,
                             unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
    unmapped = [c for c in sorted(CHAINS_MANNEQUIN)
                if str(ctl.get_source_chain(c)) in ("", "None")]
    if unmapped:
        raise RuntimeError(f"{pkg}: target chains with no source: {unmapped}")
    EAL.save_asset(pkg)
    return rtg


def imported_packs():
    """{short: {clip name: AnimSequence}} for the packs as imported."""
    packs = {}
    for _stem, short, _glb in UAL_PACKS:
        prefix = f"A_{short}_"
        clips = {}
        for path in EAL.list_assets(pack_dir(short), recursive=False):
            name = path.split(".")[0].rsplit("/", 1)[1]
            asset = EAL.load_asset(path.split(".")[0]) if name.startswith(prefix) else None
            if isinstance(asset, unreal.AnimSequence):
                clips[name[len(prefix):]] = asset
        if not clips:
            raise RuntimeError(f"{pack_dir(short)} has no clips: run "
                               "asset_pipeline/import_quaternius.py first")
        packs[short] = clips
    return packs


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    packs = imported_packs()
    mesh = _load(MANNEQUIN_MESH)
    target = build_ik_rig(IK_MANNEQUIN, MANNEQUIN_MESH, CHAINS_MANNEQUIN,
                          RETARGET_ROOT_MANNEQUIN,
                          root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    _fresh(ual_anim_dir(MANNEQUIN))
    total = 0
    for short, clips in packs.items():
        rtg = build_retargeter(build_ual_rig(short), target,
                               ual_retargeter_path(MANNEQUIN, short))
        total += len(_batch(rtg, short, MANNEQUIN, mesh, list(clips.values())))
    EAL.save_directory(ual_anim_dir(MANNEQUIN), only_if_is_dirty=False)

    skeleton = mesh.get_editor_property("skeleton")
    ok = True
    for short, clip in USED:
        path = ual_clip(MANNEQUIN, short, clip)
        asset = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
        good = (isinstance(asset, unreal.AnimSequence)
                and asset.get_editor_property("skeleton") == skeleton)
        ok = ok and good
        unreal.log_warning(f"[VERIFY] {'PASS' if good else 'FAIL'} {path.rsplit('/', 1)[1]} "
                           "is a clip on SK_Mannequin")
    _log(f"{total} clips -> {ual_anim_dir(MANNEQUIN)}")
    return ok


if __name__ == "__main__":
    main()
