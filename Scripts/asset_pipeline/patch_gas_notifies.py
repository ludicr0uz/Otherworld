"""patch_gas_notifies.py -- make the two notifies of the Game Animation Sample
that only its Mover character answers compile without it.  Editor side.

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/patch_gas_notifies.py

BP_AnimNotify_TriggerRagdoll casts its owner to SandboxCharacter_Mover_Ragdoll
and BP_NotifyState_OverrideMovementMode to SandboxCharacter_Mover, and neither
does anything for any other character.  The Mover variant is not copied
(gas_paths.EXCLUDED), so as copied both fail to compile, on every load of a
clip that carries one.  Their clips still name them, so they cannot be left
behind: this removes each one's function graphs, which leaves a notify of the
same class and variables that does nothing, and saves it.  import_gas.py
keeps a package listed in gas_paths.PATCHED once it is here, so the copy does
not undo this; delete the file to take the sample's again.
"""
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
for _m in [m for m in sys.modules if m.split(".")[0] == "asset_pipeline"]:
    del sys.modules[_m]

from asset_pipeline.gas_paths import PATCHED, gas  # noqa: E402

BEL = unreal.BlueprintEditorLibrary


def _patch(path):
    bp = unreal.EditorAssetLibrary.load_asset(path)
    if bp is None:
        raise RuntimeError(f"{path} is not here: run import_gas.py first")
    removed = []
    for graph in list(BEL.list_graphs(bp) or []):
        name = graph.get_name()
        if name.startswith("Received_"):
            BEL.remove_function_graph(bp, name)
            removed.append(name)
    left = [g.get_name() for g in BEL.list_graphs(bp) or []
            if g.get_name().startswith("Received_")]
    if left:
        raise RuntimeError(f"{path}: could not remove {left}")
    BEL.compile_blueprint(bp)
    status = bp.get_editor_property("status")
    if status == unreal.BlueprintStatus.BS_ERROR:
        raise RuntimeError(f"{path} still does not compile")
    if removed:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError(f"{path} was not saved")
    unreal.log_warning(f"[GEN] {path}: removed {removed or 'nothing (already patched)'}, {status}")


def main():
    for pkg in PATCHED:
        _patch(gas(pkg))


main()
