"""plain_retarget -- the retargeter between two rigs named and oriented the
mannequin's way: the Quaternius library's, the mannequin's, the UEFN
mannequin's.  retarget_rig.build_retargeter is written for a Meshy target
(its finger offsets, its palm calibration and its mapping check all name
Meshy's bones) and none of that is needed between these: the chains map by
name and the palms need no turn.  What is kept from it is what the game needs
of any clip: in place (the character's movement moves the body, not the
clip) and the target's pose aligned chain to chain.
"""

import unreal

from asset_pipeline.rig_util import _reuse_or_create

EAL = unreal.EditorAssetLibrary


def build_plain_retargeter(source_rig, target_rig, pkg, chains):
    """``pkg``: source -> target, every one of ``chains`` mapped by name."""
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
    unmapped = [c for c in chains if str(ctl.get_source_chain(c)) in ("", "None")]
    if unmapped:
        raise RuntimeError(f"{pkg}: target chains with no source: {unmapped}")
    EAL.save_asset(pkg)
    return rtg
