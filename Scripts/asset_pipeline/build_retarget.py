#!/usr/bin/env python3
"""Build the IK Rigs and retargeter that make Meshy monsters animate.

Run inside the editor:

    Scripts/dev/uepy.py Scripts/asset_pipeline/build_retarget.py

Meshy rigs every creature on the same 24-bone Mixamo-named skeleton -- proved by
skeleton_probe.py, which found byte-identical hierarchies for a 1.8 m zombie and
a 2.4 m wendigo.  So the work here is done **once**, not once per monster: two IK
Rigs and one retargeter, after which every new creature is a mesh binding to
SK_MeshyHumanoid and inheriting this animation set for free.

Three assets get built:

    IK_Mannequin        chains over SK_Mannequin      (source of the animation)
    IK_MeshyHumanoid    chains over SK_MeshyHumanoid  (where it is going)
    RTG_Meshy_to_Mannequin                            (the mapping between them)

Then the Unarmed locomotion set is batch-retargeted onto SK_MeshyHumanoid.

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
MESHY_SKELETON = "/Game/Sourced/Characters/SK_MeshyHumanoid"

CHARACTER_ROOT = "/Game/Sourced/Characters"
RIG_DIR = "/Game/Sourced/Characters/Rigs"
ANIM_DIR = "/Game/Sourced/Characters/Anims"

IK_MANNEQUIN = f"{RIG_DIR}/IK_Mannequin"
IK_MESHY = f"{RIG_DIR}/IK_MeshyHumanoid"
RETARGETER = f"{RIG_DIR}/RTG_Meshy_to_Mannequin"

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
ABP_MESHY = f"{ANIM_DIR}/A_Meshy_ABP_Unarmed"
MELEE_MESHY = f"{ANIM_DIR}/A_Meshy_MM_Attack_01"


# print() goes nowhere in a cold -ExecutePythonScript run; the log does.
def _log(msg):
    unreal.log_warning(f"[RETARGET] {msg}")


def _meshy_mesh():
    """Any monster bound to SK_MeshyHumanoid will do -- they share the rig.

    Found rather than hardcoded: each monster imports into a folder of its own,
    and which one happens to be there is not this script's business.
    """
    skel = _load(MESHY_SKELETON)
    for path in sorted(unreal.EditorAssetLibrary.list_assets(CHARACTER_ROOT, recursive=True)):
        asset = unreal.EditorAssetLibrary.load_asset(path.split(".")[0])
        if isinstance(asset, unreal.SkeletalMesh) and \
                asset.get_editor_property("skeleton") == skel:
            return asset
    raise RuntimeError(f"no skeletal mesh under {CHARACTER_ROOT} uses {MESHY_SKELETON}")


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


def build_retargeter(source_rig, target_rig):
    name = RETARGETER.rsplit("/", 1)[1]
    rtg = _reuse_or_create(RETARGETER, unreal.IKRetargeter,
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

    unreal.EditorAssetLibrary.save_asset(RETARGETER)
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


def retarget_animations(rtg):
    assets = _source_assets()
    _log(f"retargeting {len(assets)} roots (+ their dependencies) -> {ANIM_DIR}")

    # Wipe first.  The batch operation does not reliably overwrite in place: a
    # run whose output collided with an existing A_Meshy_MM_Idle produced
    # A_Meshy_MM_Idle1 beside it despite overwrite_existing_files, and a stray
    # numbered duplicate is the kind of thing that gets referenced by accident
    # and then never updates.  The directory is generated in full every run and
    # is git-ignored, so there is nothing here worth preserving.
    if unreal.EditorAssetLibrary.does_directory_exist(ANIM_DIR):
        unreal.EditorAssetLibrary.delete_directory(ANIM_DIR)
    unreal.EditorAssetLibrary.make_directory(ANIM_DIR)
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()

    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget", assets)
    inputs.set_editor_property("source_mesh", _load(MANNEQUIN_MESH))
    inputs.set_editor_property("target_mesh", _meshy_mesh())
    inputs.set_editor_property("ik_retarget_asset", rtg)
    # Follow the graph: this is what turns two roots into the whole locomotion
    # set, blend space and state machine included.
    inputs.set_editor_property("include_referenced_assets", True)
    # Strip the mannequin's naming convention and stamp the creature family on,
    # so /Game/Sourced/Characters/Anims never collides with the source set.
    inputs.set_editor_property("search", "MF_Unarmed_")
    inputs.set_editor_property("replace", "")
    inputs.set_editor_property("prefix", "A_Meshy_")
    inputs.set_editor_property("target_path", ANIM_DIR)
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


def _check_pose(anim):
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
        # Ref-pose hips sit at 101 uu. A pelvis on the floor means the Root
        # Motion op stole the track; one at head height means a broken chain.
        if grounded and not 60.0 < hips < 140.0:
            problems.append(f"t={t:.2f} hips at z={hips:.0f}, expected ~101")
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


def verify(created):
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
    meshy_skel = _load(MESHY_SKELETON)
    clips, ok, bad = 0, 0, []

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
                problems = _check_pose(asset)
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
    for expected in (ABP_MESHY, MELEE_MESHY):
        if not unreal.EditorAssetLibrary.does_asset_exist(expected):
            bad.append((expected.rsplit("/", 1)[1], "expected by the NPC builder, not produced"))

    _log("=" * 52)
    _log(f"{ok}/{clips} clips upright, in place, with a real gait "
         f"({len(created)} assets total)")
    for name, why in bad:
        _log(f"  FAIL {name}: {why}")
    if bad:
        raise RuntimeError(f"{len(bad)} problems across the retargeted set")
    _log(f"monsters walk -- every mesh on {MESHY_SKELETON.rsplit('/', 1)[1]} "
         f"shares {ABP_MESHY.rsplit('/', 1)[1]}")


def main():
    # Chained straight after import_characters.py in one cold editor, the
    # registry is still scanning the meshes that were just written and
    # create_asset quietly returns None. Wait for it rather than race it.
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()

    for d in (RIG_DIR, ANIM_DIR):
        if not unreal.EditorAssetLibrary.does_directory_exist(d):
            unreal.EditorAssetLibrary.make_directory(d)

    src = build_ik_rig(IK_MANNEQUIN, MANNEQUIN_MESH,
                       CHAINS_MANNEQUIN, RETARGET_ROOT_MANNEQUIN,
                       root_motion_bone=ROOT_MOTION_BONE_MANNEQUIN)
    tgt = build_ik_rig(IK_MESHY, _meshy_mesh().get_path_name().split(".")[0],
                       CHAINS_MESHY, RETARGET_ROOT_MESHY)
    rtg = build_retargeter(src, tgt)
    verify(retarget_animations(rtg))
    unreal.EditorAssetLibrary.save_directory(RIG_DIR, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_directory(ANIM_DIR, only_if_is_dirty=False)


main()
