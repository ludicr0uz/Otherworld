"""build_gas_bridge.py -- the skeleton bridge between the Game Animation
Sample and the player's MetaHuman, as far as one idle.  Editor-side.

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/build_gas_bridge.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_gas_idle.py

The sample's clips are on SK_UEFN_Mannequin.  The bridge chosen (Scripts/
asset_pipeline/CLAUDE.md, "The skeleton bridge") is that the player's hidden
mesh becomes that mannequin, so the clips, the PoseSearch databases and the
sample's anim blueprint play as they shipped, and the MetaHuman body follows
it through a retargeter whose source is rebuilt on the UEFN skeleton.
Writes, under /Game/Sourced/MetaHuman, beside the mannequin's bridge and
touching none of it:

    IK_UEFN_Mannequin_Source       the mannequin's chain table (rig_chains.
                                   CHAINS_MANNEQUIN) on SKM_UEFN_Mannequin,
                                   which names every one of those bones as
                                   SK_Mannequin does: the chain map onto
                                   IK_MetaHuman is exact.  Not the sample's
                                   own IK_UEFN_Mannequin, whose chains are
                                   named for the sample's retargeters.
    RTG_MetaHuman_from_UEFN        that rig -> IK_MetaHuman (build_metahuman_
                                   retarget.py's, which must have run).
    ABP_MetaHuman_Retarget_UEFN    the retargeting anim blueprint, pointed at
                                   it: what the Body component wears while
                                   its parent is the UEFN mannequin.
    ABP_GasIdle                    one sequence player on SK_UEFN_Mannequin
                                   (gas_idle_abp.py): the proof's idle.

Nothing in the game wears any of these yet: probe_gas_idle.py puts them on
the live player for one run.  Idempotent: assets are reused and rebuilt in
place.
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith(("asset_pipeline", "uebp"))]:
    del sys.modules[_name]          # a warm editor keeps yesterday's modules

from asset_pipeline.gas_bridge_paths import (                      # noqa: E402
    ABP_RETARGET_UEFN, HIDDEN_MESH_GAS, IK_UEFN, RTG_FROM_UEFN,
)
from asset_pipeline.gas_idle_abp import build_idle_blueprint       # noqa: E402
from asset_pipeline.metahuman_paths import BODY_MESH, IK_METAHUMAN  # noqa: E402
from asset_pipeline.metahuman_retarget import (                    # noqa: E402
    build_anim_blueprint, build_retargeter,
)
from asset_pipeline.retarget_rig import build_ik_rig              # noqa: E402
from asset_pipeline.rig_chains import (                            # noqa: E402
    CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN, ROOT_MOTION_BONE_MANNEQUIN,
)
from asset_pipeline.rig_util import _load, _log                    # noqa: E402

EAL = unreal.EditorAssetLibrary


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    for need, by in ((HIDDEN_MESH_GAS, "import_gas.py"),
                     (IK_METAHUMAN, "build_metahuman_retarget.py")):
        if not EAL.does_asset_exist(need):
            raise RuntimeError(f"{need} is not here: run Scripts/asset_pipeline/{by} first")
    src = build_ik_rig(IK_UEFN, HIDDEN_MESH_GAS, CHAINS_MANNEQUIN,
                       RETARGET_ROOT_MANNEQUIN,
                       root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    rtg = build_retargeter(src, _load(IK_METAHUMAN), RTG_FROM_UEFN, _load(BODY_MESH),
                           align=True)
    build_anim_blueprint(rtg, ABP_RETARGET_UEFN)
    build_idle_blueprint()
    _log("done")


if __name__ == "__main__":
    main()
