#!/usr/bin/env python3
"""Build the IK Rigs and retargeter that make Meshy monsters animate.

Run inside the editor:

    Scripts/dev/uepy.py Scripts/asset_pipeline/build_retarget.py

Meshy rigs every creature on the same 24-bone Mixamo-named skeleton -- same bone
names, same parents, for a 1.8 m zombie and a 2.4 m wendigo alike.  That made it
look as though the work here could be done once for all monsters, and for a
while it was.  It cannot: what an animation stores is a per-bone local rotation,
and what that rotation MEANS depends on the bind pose, which Meshy does not
share between creatures.  Retargeted once against the wendigo, the clips put the
wendigo's 59-degree forward neck pitch on the zombie and its head hung in front
of its chest.  import_characters.py carries the measurements.

So the source side is built once and the target side once per creature:

    IK_Mannequin              chains over SK_Mannequin   (source of the motion)
    IK_<Monster>              chains over SK_<Monster>   (where it is going)
    RTG_<Monster>_from_Mannequin                         (the mapping)

and the Unarmed locomotion set is batch-retargeted per monster into
Anims/<Monster>/ with an A_<Monster>_ prefix.  Nothing hand-authored is
duplicated -- the chain tables below are keyed by bone name, and those really
are shared, so a new creature still needs no new authoring.  What multiplies is
generated assets: about 22 clips, an IK Rig and a retargeter each.

Why the chains are written out by hand instead of calling
``apply_auto_generated_retarget_definition``: Meshy numbers its spine
**backwards**.  The chain from the hips runs ``Hips -> Spine02 -> Spine01 ->
Spine``, so the bone named ``Spine02`` is the LOWEST one, where UE's ``spine_01``
is the lowest.  Auto-characterisation keys off names and gets this inside out,
which folds the creature over at the waist.  Explicit start/end bones are also
reproducible: the same source tree builds the same rig on any machine.

Chain names are deliberately identical on both sides so the mapping is an exact
string match rather than a fuzzy guess.
"""

import os
import unreal

MANNEQUIN_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"

CHARACTER_ROOT = "/Game/Sourced/Characters"
RIG_DIR = "/Game/Sourced/Characters/Rigs"
ANIM_ROOT = "/Game/Sourced/Characters/Anims"

IK_MANNEQUIN = f"{RIG_DIR}/IK_Mannequin"


# ─── One animation set per monster ──────────────────────────────────────────
#
# These used to be single constants, because every monster was bound to one
# SK_MeshyHumanoid.  They are functions now for the reason spelled out at
# length in import_characters.py: Meshy shares bone NAMES between creatures but
# not bind poses, so a clip retargeted against the wendigo puts the wendigo's
# 59-degree forward neck pitch on a zombie and its head hangs off the front of
# its body.  Each monster animates against its own bind pose or it animates
# wrong.
#
# Nothing hand-authored is duplicated by this -- the chain tables below are
# keyed by bone name and those genuinely are shared.  What multiplies is
# generated assets: roughly 22 clips, an IK Rig and a retargeter per creature.

def ik_rig_path(name):
    return f"{RIG_DIR}/IK_{name}"


def retargeter_path(name):
    return f"{RIG_DIR}/RTG_{name}_from_Mannequin"


def anim_dir(name):
    return f"{ANIM_ROOT}/{name}"


def anim_prefix(name):
    return f"A_{name}_"


def abp_path(name):
    return f"{anim_dir(name)}/{anim_prefix(name)}ABP_Unarmed"


def melee_path(name):
    return f"{anim_dir(name)}/{anim_prefix(name)}MM_Attack_01"

# name -> (start bone, end bone).  Identical keys on both sides: auto_map_chains
# then pairs them by exact string match and never has to guess.
CHAINS_MANNEQUIN = {
    "Spine":         ("spine_01", "spine_05"),
    "Neck":          ("neck_01", "neck_02"),
    "Head":          ("head", "head"),
    "LeftClavicle":  ("clavicle_l", "clavicle_l"),
    "LeftArm":       ("upperarm_l", "hand_l"),
    "RightClavicle": ("clavicle_r", "clavicle_r"),
    "RightArm":      ("upperarm_r", "hand_r"),
    "LeftLeg":       ("thigh_l", "ball_l"),
    "RightLeg":      ("thigh_r", "ball_r"),
}

# Note the Spine entry: start Spine02 (the child of Hips), end Spine (the top).
# That is not a typo, it is Meshy's inverted numbering.
CHAINS_MESHY = {
    "Spine":         ("Spine02", "Spine"),
    "Neck":          ("neck", "neck"),
    "Head":          ("Head", "Head"),
    "LeftClavicle":  ("LeftShoulder", "LeftShoulder"),
    "LeftArm":       ("LeftArm", "LeftHand"),
    "RightClavicle": ("RightShoulder", "RightShoulder"),
    "RightArm":      ("RightArm", "RightHand"),
    "LeftLeg":       ("LeftUpLeg", "LeftToeBase"),
    "RightLeg":      ("RightUpLeg", "RightToeBase"),
}

RETARGET_ROOT_MANNEQUIN = "pelvis"
RETARGET_ROOT_MESHY = "Hips"

# The mannequin separates travel into a dedicated ``root`` bone and leaves the
# pelvis bobbing in place.  Meshy has no such bone -- its hierarchy starts at
# ``Hips`` -- so there is nowhere for root motion to land.  Left unset, the
# Root Motion op falls back to bone 0, which on the Meshy rig IS the pelvis: it
# overwrote the pelvis track, pinning the hips to z=0 and sliding the whole
# creature forward 4.3 m over a walk cycle.  So the mannequin gets its root
# bone named explicitly, and root motion is switched off for the target.
ROOT_MOTION_BONE_MANNEQUIN = "root"

# The locomotion an enemy actually needs.  Not the pistol/rifle sets: the Meshy
# rig has no fingers, so anything that grips a weapon is meaningless on it.
# Two roots, not a list of clips.  Retargeting the ANIM BLUEPRINT with
# include_referenced_assets pulls in everything it plays -- BS_Idle_Walk_Run and
# the sixteen directional clips behind it, MM_Idle, and the jump set -- and,
# more importantly, produces a target-skeleton copy of the state machine that
# drives them.  A folder of loose AnimSequences is not something a Character can
# be pointed at; an anim BP is.  Listing the clips by hand, as this did at
# first, retargeted the animation and left the animation LOGIC behind on
# SK_Mannequin, which is why the monsters existed as assets but nothing in the
# game could use them.
#
# MM_Attack_01 is named separately because nothing references it: the AI
# controller plays it into a slot by path at runtime, so the dependency walk
# cannot see it.
ABP_SOURCE = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"
MELEE_SOURCE = "/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"
RETARGET_SOURCES = (ABP_SOURCE, MELEE_SOURCE)

# What the NPC builder points a monster's SkeletalMeshComponent at.  Derived
# from the source name and the prefix below, and asserted in verify() rather
# than left as a comment, because a rename here silently breaks the NPCs.


# print() goes nowhere in a cold -ExecutePythonScript run; the log does.
def _log(msg):
    unreal.log_warning(f"[RETARGET] {msg}")


def _monsters():
    """Every imported creature, as (short name, mesh, skeleton).

    Discovered rather than listed: each monster imports into a folder of its
    own and which ones are present depends on what the catalog fetched.  The
    short name drops the SKM_ prefix, so SKM_Zombie01 animates out of
    Anims/Zombie01 with an A_Zombie01_ prefix.
    """
    out = []
    for path in sorted(unreal.EditorAssetLibrary.list_assets(
            CHARACTER_ROOT, recursive=True)):
        asset = unreal.EditorAssetLibrary.load_asset(path.split(".")[0])
        if not isinstance(asset, unreal.SkeletalMesh):
            continue
        skel = asset.get_editor_property("skeleton")
        if not skel:
            continue
        out.append((asset.get_name().replace("SKM_", ""), asset, skel))
    if not out:
        raise RuntimeError(f"no skeletal mesh under {CHARACTER_ROOT}")
    return out


def _reuse_or_create(pkg, cls, factory):
    """Load the asset at pkg, or create it there. Never deletes."""
    existing = unreal.EditorAssetLibrary.load_asset(pkg)
    if isinstance(existing, cls):
        return existing
    folder, name = pkg.rsplit("/", 1)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, cls, factory)
    if asset is None:
        raise RuntimeError(f"could not create {pkg}")
    return asset


def _load(pkg):
    a = unreal.EditorAssetLibrary.load_asset(pkg)
    if a is None:
        raise RuntimeError(f"missing asset {pkg}")
    return a


def _bone_names(mesh):
    """Bone list for a skeletal mesh, via a throwaway component far off-level."""
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, -1000000))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skeletal_mesh_asset(mesh)
        return [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def build_ik_rig(pkg, mesh_pkg, chains, retarget_root, root_motion_bone=None):
    """Create (or rebuild) one IK Rig with an explicit chain definition."""
    mesh = _load(mesh_pkg)
    present = set(_bone_names(mesh))

    # Fail loudly here rather than producing a rig with silently empty chains.
    # A chain whose bones do not exist is accepted by the controller and then
    # retargets nothing, which looks like a bad animation rather than a bad rig.
    missing = sorted({b for s, e in chains.values() for b in (s, e)
                      if b not in present} | ({retarget_root} - present))
    if missing:
        raise RuntimeError(f"{mesh_pkg} has no bones named: {missing}")

    # Rebuild in place rather than delete-and-recreate. Chained after a wipe
    # in one cold editor, the registry still lists the deleted assets: the
    # delete is a no-op on a file that is already gone, and create_asset then
    # refuses the name it believes is taken and returns None.  Reusing the
    # asset is also simply idempotent, which is what a build script wants.
    name = pkg.rsplit("/", 1)[1]
    rig = _reuse_or_create(pkg, unreal.IKRigDefinition,
                           unreal.IKRigDefinitionFactory())
    ctl = unreal.IKRigController.get_controller(rig)
    for existing in list(ctl.get_retarget_chains()):
        ctl.remove_retarget_chain(existing.chain_name)
    ctl.set_skeletal_mesh(mesh)
    ctl.set_retarget_root(retarget_root)
    if root_motion_bone:
        ctl.set_root_motion_bone(root_motion_bone)
    for chain, (start, end) in sorted(chains.items()):
        ctl.add_retarget_chain(chain, start, end, "None")

    built = sorted(str(c.chain_name) for c in ctl.get_retarget_chains())
    _log(f"{name}: root={retarget_root} "
         f"rootmotion={root_motion_bone or '-'} chains={len(built)} {built}")
    if len(built) != len(chains):
        raise RuntimeError(f"{name}: expected {len(chains)} chains, got {len(built)}")

    unreal.EditorAssetLibrary.save_asset(pkg)
    return rig


def build_retargeter(source_rig, target_rig, pkg):
    name = pkg.rsplit("/", 1)[1]
    rtg = _reuse_or_create(pkg, unreal.IKRetargeter,
                           unreal.IKRetargetFactory())
    ctl = unreal.IKRetargeterController.get_controller(rtg)
    ctl.remove_all_ops()

    ctl.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, source_rig)
    ctl.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, target_rig)

    # Pelvis Motion, FK Chains, IK Chains, IK Solve, Root Motion.  Must exist
    # before auto_map_chains: the mapping lives on the ops, so mapping an empty
    # op stack maps nothing.
    ctl.add_default_ops()
    ctl.auto_map_chains(unreal.AutoMapChainType.EXACT, True)

    # See ROOT_MOTION_BONE_MANNEQUIN.  Enemies are driven by CharacterMovement,
    # so in-place locomotion is what we want anyway; this is not a compromise.
    for i in range(ctl.get_num_retarget_ops()):
        op = str(ctl.get_op_name(i))
        if op == "Root Motion":
            ctl.set_retarget_op_enabled(i, False)
            _log(f"{name}: disabled the Root Motion op (Meshy rig has no root bone)")
        elif op == "Pelvis Motion":
            # Disabling Root Motion is not enough on its own. The retargeter
            # evaluates the SOURCE globally, so the mannequin's root travel is
            # already baked into the pelvis position this op reads -- the clip
            # still slid 7 m across a jog. Zeroing the horizontal scale keeps
            # the vertical bob (which sells the gait) and drops the travel.
            oc = ctl.get_op_controller(i)
            st = oc.get_settings()
            st.set_editor_property("scale_horizontal", 0.0)
            oc.set_settings(st)
            _log(f"{name}: pelvis horizontal scale 0 -- clips are in place")

    # ── Retarget pose ────────────────────────────────────────────────────────
    # The retargeter does not copy poses, it copies the *difference* between a
    # bone's animated orientation and its orientation in the retarget pose. If
    # the two skeletons' retarget poses disagree, that disagreement is baked
    # into every frame of every clip, permanently.
    #
    # Left alone, each side's retarget pose is its own reference pose. Meshy's
    # A-pose and Epic's A-pose are not the same A-pose, and the residual showed
    # up on screen exactly where the arm and leg chains differ most: arms held
    # wide, hands up at the sides, feet toed out, through the whole run cycle.
    #
    # auto_align_all_bones rotates each TARGET bone so its chain points the way
    # the source chain points, which is the correction, and is the same button
    # the IK Retargeter editor offers under "Auto-Align". CHAIN_TO_CHAIN rather
    # than the rotation-axis methods because those assume both rigs share axis
    # conventions -- Mixamo and Epic do not.
    ctl.auto_align_all_bones(unreal.RetargetSourceOrTarget.TARGET,
                             unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
    _log(f"{name}: target retarget pose auto-aligned to the source (chain to chain)")

    # Ask per target chain rather than reading the op stack: an unmapped chain
    # comes back "None" here, so a silent hole in the mapping is visible.
    unmapped = []
    _log(f"{name}: {ctl.get_num_retarget_ops()} ops")
    for chain in sorted(CHAINS_MESHY):
        src = str(ctl.get_source_chain(chain))
        _log(f"    {src} -> {chain}")
        if src in ("", "None"):
            unmapped.append(chain)
    if unmapped:
        raise RuntimeError(f"{name}: target chains with no source: {unmapped}")

    unreal.EditorAssetLibrary.save_asset(pkg)
    return rtg


def _source_assets():
    """AssetData for the retarget roots.

    The batch operation takes FAssetData, not loaded objects -- passing the
    UObject fails with "Cannot nativize 'AnimBlueprint' as 'AssetData'".
    """
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    out = []
    for pkg in RETARGET_SOURCES:
        data = reg.get_asset_by_object_path(f"{pkg}.{pkg.rsplit('/', 1)[1]}")
        if not data or not data.is_valid():
            raise RuntimeError(f"retarget source not found: {pkg}")
        out.append(data)
    return out


def retarget_animations(rtg, mesh, out_dir, prefix):
    assets = _source_assets()
    _log(f"retargeting {len(assets)} roots (+ their dependencies) -> {out_dir}")

    # Wipe first.  The batch operation does not reliably overwrite in place: a
    # run whose output collided with an existing A_Meshy_MM_Idle produced
    # A_Meshy_MM_Idle1 beside it despite overwrite_existing_files, and a stray
    # numbered duplicate is the kind of thing that gets referenced by accident
    # and then never updates.  The directory is generated in full every run and
    # is git-ignored, so there is nothing here worth preserving.
    if unreal.EditorAssetLibrary.does_directory_exist(out_dir):
        unreal.EditorAssetLibrary.delete_directory(out_dir)
    unreal.EditorAssetLibrary.make_directory(out_dir)
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()

    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget", assets)
    inputs.set_editor_property("source_mesh", _load(MANNEQUIN_MESH))
    inputs.set_editor_property("target_mesh", mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    # Follow the graph: this is what turns two roots into the whole locomotion
    # set, blend space and state machine included.
    inputs.set_editor_property("include_referenced_assets", True)
    # Strip the mannequin's naming convention and stamp the creature family on,
    # so /Game/Sourced/Characters/Anims never collides with the source set.
    inputs.set_editor_property("search", "MF_Unarmed_")
    inputs.set_editor_property("replace", "")
    inputs.set_editor_property("prefix", prefix)
    inputs.set_editor_property("target_path", out_dir)
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)

    created = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    _log(f"created {len(created)} assets")
    return created


def _bone_world(anim, bone, time):
    """Component-space position of a bone at a time, composed up the hierarchy.

    get_bone_pose_for_time returns a LOCAL transform, so a bone's actual
    position is its own transform multiplied by every parent's up to the root.
    """
    xf = unreal.Transform()
    for b in unreal.AnimationLibrary.find_bone_path_to_root(anim, bone):
        xf = xf.multiply(unreal.AnimationLibrary.get_bone_pose_for_time(
            anim, b, time, False))
    return xf.translation


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


def _skeleton_bone_names(skeleton):
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    return [str(b) for b in unreal.AnimPoseExtensions.get_bone_names(pose)]


def _ref_hips_z(skeleton):
    """Hip height in the skeleton's own reference pose, component space.

    The grounded band below used to be the literal 60..140, which happened to
    bracket both the 1.8 m zombie (hips 101) and the 2.4 m wendigo (hips 128).
    Now that each creature carries its own skeleton, a taller one would fail a
    check that is really asking "are the hips roughly where this creature's
    hips belong" -- so ask that.
    """
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    return unreal.AnimPoseExtensions.get_bone_pose(
        pose, "Hips", unreal.AnimPoseSpaces.WORLD).translation.z


def _check_pose(anim, ref_hips):
    """Is this a creature standing up and taking steps, or a folded heap?

    Existing-and-non-empty is not a useful test: an animation that folds the
    creature double at the waist, or pins its pelvis to the floor, passes it.
    Both are exactly what a wrongly-ordered spine chain and a stolen root
    produce, so the check has to look at where the bones actually are.
    """
    length = anim.get_editor_property("sequence_length")
    samples = [length * i / 8.0 for i in range(8)]
    problems = []
    foot_gaps, hips_xy = [], []

    # Two exemptions, both because the check below encodes what GROUNDED
    # locomotion looks like and these clips are not that.
    #
    # An idle has no gait: an idle whose feet alternate is the bug.
    #
    # An airborne clip has no fixed hip height and no step cycle -- rising is
    # the entire content of a jump.  MM_Jump legitimately reaches z=153 and
    # was the one clip to fail the grounded band.  Upright and in-place still
    # apply to it: a jump that folds double or drifts sideways is still wrong.
    name = anim.get_name()
    grounded = not any(k in name for k in ("Jump", "Fall", "Land"))
    has_gait = grounded and "Idle" not in name

    for t in samples:
        p = {b: _bone_world(anim, b, t)
             for b in ("Hips", "Head", "LeftFoot", "RightFoot")}
        hips, head = p["Hips"].z, p["Head"].z
        feet = max(p["LeftFoot"].z, p["RightFoot"].z)
        if not (head > hips > feet):
            problems.append(f"t={t:.2f} not upright "
                            f"(head {head:.0f} hips {hips:.0f} feet {feet:.0f})")
        # A pelvis on the floor means the Root Motion op stole the track; one
        # at head height means a broken chain. Banded against this creature's
        # own reference pose rather than a literal, so a taller monster is not
        # failed for being tall.
        if grounded and not 0.6 * ref_hips < hips < 1.4 * ref_hips:
            problems.append(f"t={t:.2f} hips at z={hips:.0f}, "
                            f"expected ~{ref_hips:.0f}")
        foot_gaps.append(p["LeftFoot"].z - p["RightFoot"].z)
        hips_xy.append((p["Hips"].x, p["Hips"].y))

    # A frozen pose satisfies every bound above, so locomotion has to show a
    # gait: one foot high while the other is planted, and the pair swapping.
    if has_gait:
        if max(foot_gaps) - min(foot_gaps) < 5.0:
            problems.append("feet never alternate "
                            f"(spread {max(foot_gaps) - min(foot_gaps):.1f} uu)")
        elif not (max(foot_gaps) > 0 > min(foot_gaps)):
            problems.append("the same foot leads throughout -- no step cycle")

    # In-place is the contract now that root motion is off: a clip that travels
    # metres in its pelvis track slides away from its own capsule.
    travel = max((abs(a - c) + abs(b - d))
                 for a, b in hips_xy for c, d in hips_xy)
    if travel > 50.0:
        problems.append(f"pelvis travels {travel:.0f} uu -- not in place")
    return problems


def verify(created, monster, meshy_skel):
    """The point of the whole exercise: does a monster actually animate?

    The batch now returns three kinds of asset, and each needs a different
    question asked of it.  A clip is checked geometrically -- upright, in
    place, with a real step cycle -- because the cheap check (right skeleton,
    non-zero length) passes for a creature folded double at the waist or
    pinned to the floor, which is exactly what two live bugs produced while
    this reported "ok".  A blend space and an anim blueprint have no pose to
    sample, so they are checked for the thing that breaks instead: the blend
    space for its skeleton, the blueprint for whether it compiles.
    """
    clips, ok, bad = 0, 0, []
    ref_hips = _ref_hips_z(meshy_skel)

    for data in created:
        pkg = str(data.package_name)
        asset = unreal.EditorAssetLibrary.load_asset(pkg)
        name = asset.get_name() if asset else pkg

        if isinstance(asset, unreal.AnimSequence):
            clips += 1
            # Nothing downstream can extract root motion from a skeleton with
            # no root bone; leaving the flag on invites a silent foot-slide.
            asset.set_editor_property("enable_root_motion", False)
            asset.set_editor_property("force_root_lock", False)

            skel = asset.get_editor_property("skeleton")
            frames = asset.get_editor_property("number_of_sampled_frames")
            if skel != meshy_skel:
                bad.append((name, f"skeleton {skel.get_name() if skel else None}"))
            elif frames < 2:
                bad.append((name, f"{frames} frames"))
            else:
                problems = _check_pose(asset, ref_hips)
                bad.extend((name, p) for p in problems)
                ok += not problems

        elif isinstance(asset, unreal.AnimBlueprint):
            # A retargeted anim BP keeps every node it had, including ones
            # bound to the source rig.  ABP_Unarmed drives CR_Mannequin_FootIK,
            # a Control Rig authored against SK_Mannequin's bone names; on the
            # Meshy hierarchy those elements do not resolve.  That is a no-op
            # rather than an error -- the foot IK simply stops contributing --
            # but it has to compile, because a blueprint that does not compile
            # has no generated class and cannot be assigned to a component.
            if not unreal.BlueprintEditorLibrary.compile_blueprint(asset):
                bad.append((name, "does not compile"))
            elif not unreal.BlueprintEditorLibrary.generated_class(asset):
                bad.append((name, "compiled but produced no class"))
            else:
                skel = asset.get_editor_property("target_skeleton")
                if skel != meshy_skel:
                    bad.append((name, f"targets {skel.get_name() if skel else None}"))

        elif isinstance(asset, unreal.BlendSpace) or isinstance(asset, unreal.AnimationAsset):
            skel = asset.get_editor_property("skeleton")
            if skel != meshy_skel:
                bad.append((name, f"skeleton {skel.get_name() if skel else None}"))

        else:
            bad.append((name, f"unexpected asset type {type(asset).__name__}"))

    # The NPC builder addresses these two by path. A rename upstream would
    # otherwise surface as a missing anim class at spawn time, in the game.
    for expected in (abp_path(monster), melee_path(monster)):
        if not unreal.EditorAssetLibrary.does_asset_exist(expected):
            bad.append((expected.rsplit("/", 1)[1], "expected by the NPC builder, not produced"))

    _log(f"  {ok}/{clips} clips upright, in place, with a real gait "
         f"({len(created)} assets total)")
    for bad_name, why in bad:
        _log(f"  FAIL {bad_name}: {why}")
    if bad:
        raise RuntimeError(
            f"{monster}: {len(bad)} problems across the retargeted set")
    return ok, clips


def main():
    # Chained straight after import_characters.py in one cold editor, the
    # registry is still scanning the meshes that were just written and
    # create_asset quietly returns None. Wait for it rather than race it.
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()

    for d in (RIG_DIR, ANIM_ROOT):
        if not unreal.EditorAssetLibrary.does_directory_exist(d):
            unreal.EditorAssetLibrary.make_directory(d)

    # The source side is built once: there is only one mannequin.
    src = build_ik_rig(IK_MANNEQUIN, MANNEQUIN_MESH,
                       CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN,
                       root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)

    monsters = _monsters()
    _log(f"{len(monsters)} monster(s): {', '.join(n for n, _, _ in monsters)}")
    totals = []
    for name, mesh, skeleton in monsters:
        _log(f"--- {name} ({skeleton.get_name()}) ---")
        tgt = build_ik_rig(ik_rig_path(name),
                           mesh.get_path_name().split(".")[0],
                           CHAINS_MESHY, RETARGET_ROOT_MESHY)
        rtg = build_retargeter(src, tgt, retargeter_path(name))
        created = retarget_animations(rtg, mesh, anim_dir(name),
                                      anim_prefix(name))
        # After the copy, before the checks: verify() asserts the graph is clean.
        fix_retargeted_abp(abp_path(name), skeleton)
        totals.append((name, *verify(created, name, skeleton)))

    unreal.EditorAssetLibrary.save_directory(RIG_DIR, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_directory(ANIM_ROOT, only_if_is_dirty=False)

    _log("=" * 52)
    for name, ok, clips in totals:
        _log(f"  {name:12s} {ok}/{clips} clips, anim BP {abp_path(name).rsplit('/', 1)[1]}")
    _log(f"{len(totals)} monster(s) animate against their own bind pose")


main()
