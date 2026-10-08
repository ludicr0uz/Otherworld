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
    BODY_MESH, IK_METAHUMAN, RTG_FROM_MANNEQUIN, SOURCED_DIR,
)
from asset_pipeline.metahuman_retarget import (                    # noqa: E402
    build_anim_blueprint, build_retargeter,
)
from asset_pipeline.retarget_paths import IK_MANNEQUIN, MANNEQUIN_MESH, RIG_DIR  # noqa: E402
from asset_pipeline.retarget_rig import build_ik_rig              # noqa: E402
from asset_pipeline.rig_chains import (                            # noqa: E402
    CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN, ROOT_MOTION_BONE_MANNEQUIN,
)
from asset_pipeline.rig_util import _load, _log                    # noqa: E402

EAL = unreal.EditorAssetLibrary


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
