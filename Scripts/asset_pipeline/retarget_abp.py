"""retarget_abp -- fix_retargeted_abp(): make the batch-copied ABP_Unarmed
address the Meshy skeleton it now runs on.

The server branch (task A4, combat/server_anim.py) is not this file's: the
NPC build splices it into each creature's graph and the weapons build into
the player's, replacing whatever a copy carried over, so a re-retarget is
followed by those two builds.
"""

import unreal

from asset_pipeline.rig_util import _load, _log, _skeleton_bone_names


# ─── Fixing up the retargeted Anim Blueprint ────────────────────────────────
#
# The batch retarget copies an Anim Blueprint's graph verbatim. It rewrites the
# animation ASSETS the nodes point at, but it does not rewrite BONE NAMES typed
# into node settings -- there is no bone mapping it could apply, since a name
# is just a name. So two things arrive on the Meshy skeleton still addressing
# Epic's: the upper-body branch filter, and the Control Rig.
#
# Both fail silently, which is the dangerous part. Nothing errors at runtime;
# the animation just looks wrong.

# The lowest spine joint, the Meshy equivalent of Epic's spine_01.  Meshy
# numbers its spine backwards -- the chain runs Hips -> Spine02 -> Spine01 ->
# Spine -- so the *highest* number is the bone nearest the hips.
UPPER_BODY_ROOT_MESHY = "Spine02"


def fix_retargeted_abp(abp_pkg, skeleton):
    """Make the copied anim graph address the skeleton it now runs on.

    Two edits:

    1. The LayeredBoneBlend that makes DefaultSlot upper-body-only still filters
       on ``spine_01``, a bone SK_MeshyHumanoid does not have. An unresolvable
       branch filter contributes no bones, so the slot blends in at zero weight
       and **anything played into DefaultSlot is invisible** -- which is why the
       monsters never appeared to swing at anything.

    2. The Control Rig node runs CR_Mannequin_FootIK, authored against the
       mannequin hierarchy. On this skeleton it logs "Hierarchy discrepancy for
       bone 'Head'" at compile and then moves bones it has mismapped. It is
       removed rather than repaired: foot IK is a per-skeleton rig, this one
       cannot be retargeted, and the monsters do not need it.
    """
    bp = _load(abp_pkg)
    if not bp:
        raise RuntimeError(f"{abp_pkg} missing -- the retarget did not run")
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
    if not ed:
        raise RuntimeError(f"{abp_pkg} has no AnimGraph")

    def by_class(n):
        return [x for x in ed.list_all_nodes() if x.get_class().get_name() == n]

    bones = set(_skeleton_bone_names(skeleton))

    # ── 1. branch filters ────────────────────────────────────────────────────
    for blend in by_class("AnimGraphNode_LayeredBoneBlend"):
        inner = blend.get_editor_property("node")
        setup = inner.get_editor_property("layer_setup")
        changed = False
        # Structs read out of a UPROPERTY array come back as COPIES, so editing
        # one in place edits a temporary and the change evaporates.  Every level
        # here -- filter, layer, layer_setup, node -- has to be rebuilt and
        # written back whole.
        new_setup = []
        for layer in setup:
            rebuilt = []
            for f in layer.get_editor_property("branch_filters"):
                was = str(f.get_editor_property("bone_name"))
                bf = unreal.BranchFilter()
                bf.set_editor_property("blend_depth",
                                       f.get_editor_property("blend_depth"))
                if was in bones:
                    bf.set_editor_property("bone_name", was)
                else:
                    bf.set_editor_property("bone_name", UPPER_BODY_ROOT_MESHY)
                    changed = True
                    _log(f"  branch filter {was} -> {UPPER_BODY_ROOT_MESHY} (no "
                         f"{was} on this skeleton; the slot was blending at zero)")
                rebuilt.append(bf)
            new_layer = unreal.InputBlendPose()
            new_layer.set_editor_property("branch_filters", rebuilt)
            new_setup.append(new_layer)
        if changed:
            inner.set_editor_property("layer_setup", new_setup)
            blend.set_editor_property("node", inner)

    # ── 2. the mannequin Control Rig ─────────────────────────────────────────
    for rig in by_class("AnimGraphNode_ControlRig"):
        src = unreal.BlueprintEditorLibrary.find_input_pin(rig, "Source")
        out = unreal.BlueprintEditorLibrary.find_output_pin(rig, "Pose")
        upstream = unreal.BlueprintGraphPinLibrary.list_connected_pins(src) if src else []
        downstream = unreal.BlueprintGraphPinLibrary.list_connected_pins(out) if out else []
        if not upstream or not downstream:
            raise RuntimeError("Control Rig node is not wired in line; "
                               "refusing to guess how to bypass it")
        unreal.BlueprintGraphPinLibrary.break_pin_links(src)
        unreal.BlueprintGraphPinLibrary.break_pin_links(out)
        for d in downstream:
            if not upstream[0].try_create_connection(d):
                raise RuntimeError("could not bypass the Control Rig node")
        ed.remove_nodes([rig])
        _log("  removed the mannequin Control Rig (foot IK authored for "
             "SK_Mannequin; it mismapped 'Head' on this skeleton)")

    if not unreal.BlueprintEditorLibrary.compile_blueprint(bp):
        raise RuntimeError(f"{abp_pkg} failed to compile after the fix-up")
    unreal.EditorAssetLibrary.save_loaded_asset(bp)

    left = [x.get_class().get_name() for x in ed.list_all_nodes()
            if x.get_class().get_name() == "AnimGraphNode_ControlRig"]
    bad = []
    for blend in by_class("AnimGraphNode_LayeredBoneBlend"):
        for layer in blend.get_editor_property("node").get_editor_property("layer_setup"):
            for f in layer.get_editor_property("branch_filters"):
                if str(f.get_editor_property("bone_name")) not in bones:
                    bad.append(str(f.get_editor_property("bone_name")))
    if left or bad:
        raise RuntimeError(f"fix-up did not stick: control rigs={left} bad filters={bad}")
    _log(f"  {abp_pkg.rsplit('/', 1)[1]}: graph now addresses "
         f"{skeleton.get_name()} only")
