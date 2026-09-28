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

import math
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


def aim_paths(name):
    """Where this creature's retargeted ready poses land.

    The batch operation neither searches nor replaces anything in these names,
    so the output is the source's own name behind the creature prefix.
    """
    return tuple(f"{anim_dir(name)}/{anim_prefix(name)}{src.rsplit('/', 1)[1]}"
                 for src in AIM_SOURCES)


def hit_paths(name):
    """Where this creature's six retargeted hit reactions land.

    Same shape as aim_paths, and named here for the same reason: nothing
    references them either -- the health component plays them into HitSlot by
    object reference written onto a class default, so the dependency walk that
    drives the batch cannot find them from the anim Blueprint.
    """
    return tuple(f"{anim_dir(name)}/{anim_prefix(name)}{src.rsplit('/', 1)[1]}"
                 for src in HIT_SOURCES)

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
MANNEQUIN_ANIM_DIR = "/Game/Characters/Mannequins/Anims/Unarmed"
ABP_SOURCE = f"{MANNEQUIN_ANIM_DIR}/ABP_Unarmed"
MELEE_SOURCE = "/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"

# The two ready poses the player holds a weapon in.  Named here for the same
# reason MM_Attack_01 is: nothing references them, because
# build_weapons_and_combat.py plays them into DefaultSlot by path at runtime,
# so the dependency walk cannot find them.
#
# They are retargeted for every creature rather than only for the one the
# player wears.  A creature that never holds a gun pays two clips for it, and
# the alternative -- a per-creature source list -- would make the set a
# creature is built with depend on a decision taken in a different file.
AIM_SOURCES = ("/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS",
               "/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS")

# The hit reactions -- and the reason they are spelled MM_Death_*.
#
# Epic's "death" set is not deaths.  Measured off the source assets: every one
# of the six is about a second long and ends with the pelvis at 83-88 cm and
# both feet on the floor, having staggered 1.5-2 m backwards.  They are
# FLINCHES authored to be blended into a ragdoll, which is why the project's
# own death is a ragdoll and nothing plays these at 0 HP (see the dying block
# in build_weapons_and_combat.py).  What they are is exactly what a survivor
# reacting to a bullet needs, so this is where they earn their place.
#
# The names carry a DIRECTION and that direction is load-bearing:
# build_weapons_and_combat.hit_reactions() sorts the retargeted copies into
# HIT_REACTION_CLIPS order and the health component picks by which side the
# round came from.  Three Fronts and one each of the others is what Epic
# shipped, and the three Fronts are why being shot from in front -- the common
# case -- does not look like a loop.
#
# Retargeted for every creature, for the same reason the aim poses are: which
# body the player wears is a decision taken in another file.
HIT_DIR = "/Game/Characters/Mannequins/Anims/Death"
HIT_SOURCES = (f"{HIT_DIR}/MM_Death_Front_01",
               f"{HIT_DIR}/MM_Death_Front_02",
               f"{HIT_DIR}/MM_Death_Front_03",
               f"{HIT_DIR}/MM_Death_Back_01",
               f"{HIT_DIR}/MM_Death_Left_01",
               f"{HIT_DIR}/MM_Death_Right_01")

RETARGET_SOURCES = (ABP_SOURCE, MELEE_SOURCE) + AIM_SOURCES + HIT_SOURCES

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


def build_retargeter(source_rig, target_rig, pkg, palm_angles=None):
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

    # Chain alignment fixes DIRECTION and leaves ROLL, which is why the monsters
    # ran with their palms up -- measured at 80-95 degrees off the mannequin in
    # the retargeted clips. The hands get a second pass with MESH_TO_MESH, which
    # derives orientation from the skinned geometry rather than from bone axes.
    # It has to be geometry: Epic runs X down the bone and Mixamo runs Y, so the
    # rotation-axis methods would be measuring the convention, not the pose.
    _apply_palm_twist(ctl, name, palm_angles or {})

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


# The local axis the roll is applied about.
PALM_TWIST_AXIS_LOCAL = (0.0, 1.0, 0.0)   # Mixamo runs Y down the bone


def _quat_axis_angle(axis, degrees):
    half = math.radians(degrees) * 0.5
    sn = math.sin(half)
    a = _unit(*axis)
    return unreal.Quat(a.x * sn, a.y * sn, a.z * sn, math.cos(half))


def _apply_palm_twist(ctl, name, angles):
    """Roll each hand in the target retarget pose so the palms face right.

    Chain alignment fixes the direction a chain points and says nothing about
    the spin around it, so the hands arrive rolled -- the monsters ran with
    their palms up, measured at 75-95 degrees off the mannequin.

    The offsets are LOCAL-space deltas and which way round they compose is not
    something to guess at, so the angle is not derived analytically, it is
    CALIBRATED: retarget once, measure the roll in the resulting clip, apply
    the negative of it, retarget again.  A trial of +45 degrees moved the
    measured roll by +43 to +48 on every hand of both creatures, so the
    response is essentially one-for-one -- but nothing here depends on that
    being exactly true, only on it being monotonic, and the second measurement
    checks the result rather than assuming it.

    Being a measurement rather than a constant is what makes it work for the
    next creature without anyone opening the retargeter.
    """
    pose = ctl.get_current_retarget_pose(unreal.RetargetSourceOrTarget.TARGET)
    existing = dict(pose.get_editor_property("bone_rotation_offsets"))
    for _src, bone in HAND_PAIRS:
        deg = angles.get(bone, 0.0)
        if not deg:
            continue
        q = _quat_axis_angle(PALM_TWIST_AXIS_LOCAL, deg)
        prior = existing.get(unreal.Name(bone))
        combined = prior.multiply(q) if prior else q
        ctl.set_rotation_offset_for_retarget_pose_bone(
            unreal.Name(bone), combined, unreal.RetargetSourceOrTarget.TARGET)
        _log(f"  {bone} palm roll {deg:+.1f} deg")


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


# ─── Palms ──────────────────────────────────────────────────────────────────
#
# CHAIN_TO_CHAIN alignment matches each chain's DIRECTION and says nothing
# about roll around it, so the arms came out pointing correctly with the hands
# rolled -- the monsters ran with their palms up.
#
# The roll cannot be read off the skeletons.  Epic runs X down the bone and
# Mixamo runs Y, so the bone axes sit ~90 degrees apart everywhere and comparing
# them measures the convention, not the pose; and Meshy's LeftHand is a LEAF
# with no finger children, so there is no second bone to define a hand plane
# from.  Palm orientation exists only in the skinned geometry.
#
# So it is measured there: take the vertices whose dominant weight is the hand
# (plus its descendants, because the mannequin has 15 finger bones under hand_l
# while Meshy's hand is one bone), and fit a frame to the cloud.
#
#   finger direction  wrist -> cloud centroid.  Unambiguous.
#   palm normal       the least-variance PCA axis.  A hand is a flat slab, so
#                     this is well conditioned (mannequin eigenvalues
#                     26.6/10.7/3.2, zombie 25.0/17.9/2.9).
#
# PCA gives no sign, and the sign is the whole answer, so it comes from the
# cloud's SKEW along that axis: a hand is not symmetric about its own plane --
# the fingers curl toward the palm -- so the third moment has a consistent sign.
# It measures +0.084/-0.084 on the mannequin's two hands (exactly antisymmetric,
# which is the check that it is real and not noise) and +0.418/-0.564 on the
# zombie's.  Signing both rigs by the same geometric rule is what makes their
# palm normals comparable at all.
#
# Measured residual twist after chain alignment, about the finger axis:
#
#     Zombie01   L -70.9   R +62.0
#     Wendigo01  L -87.8   R +90.7
#
# Mirror-consistent on both creatures, and ~90 degrees, which is the known
# difference between a Mixamo A-pose and Epic's.

HAND_PAIRS = (("hand_l", "LeftHand"), ("hand_r", "RightHand"))

# The clip the palm roll is calibrated against, and how close is close enough.
# An idle is the right choice: the hands are at rest, so what is measured is the
# retarget pose's own error and not a pose the animator put there.
PALM_CALIBRATION_CLIP = "MM_Idle"
PALM_TOLERANCE_DEG = 15.0


def _descendants(mesh, root):
    """``root`` plus every bone beneath it, and the mesh's own bone order.

    The order matters and is not the order AnimPoseExtensions reports: skin
    weight bone indices are into the MESH's reference skeleton, and indexing one
    with the other silently attributes vertices to the wrong bone -- it put 974
    units of variance in the mannequin's "hand", which is an arm.
    """
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, -1000000))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skeletal_mesh_asset(mesh)
        order = [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
        family = set()
        for n in order:
            cur, depth = n, 0
            while cur and cur != "None" and depth < 64:
                if cur == root:
                    family.add(n)
                    break
                cur = str(comp.get_parent_bone(cur))
                depth += 1
        return family, order
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def _unit(x, y, z):
    m = math.sqrt(x * x + y * y + z * z) or 1.0
    return unreal.Vector(x / m, y / m, z / m)


def _eig3(m):
    """Eigenvectors of a symmetric 3x3 by Jacobi rotation, descending."""
    a = [row[:] for row in m]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(64):
        p, q, best = 0, 1, 0.0
        for i in range(3):
            for j in range(i + 1, 3):
                if abs(a[i][j]) > best:
                    best, p, q = abs(a[i][j]), i, j
        if best < 1e-12:
            break
        theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, sn = math.cos(theta), math.sin(theta)
        for k in range(3):
            a[k][p], a[k][q] = c * a[k][p] - sn * a[k][q], sn * a[k][p] + c * a[k][q]
        for k in range(3):
            a[p][k], a[q][k] = c * a[p][k] - sn * a[q][k], sn * a[p][k] + c * a[q][k]
        for k in range(3):
            v[k][p], v[k][q] = c * v[k][p] - sn * v[k][q], sn * v[k][p] + c * v[k][q]
    out = [(a[i][i], (v[0][i], v[1][i], v[2][i])) for i in range(3)]
    out.sort(key=lambda t: -t[0])
    return out


def hand_frame(mesh, bone):
    """(finger direction, palm normal) for one hand, in component space."""
    family, order = _descendants(mesh, bone)
    skel = mesh.get_editor_property("skeleton")
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
    wrist = unreal.AnimPoseExtensions.get_bone_pose(
        pose, bone, unreal.AnimPoseSpaces.WORLD).translation

    dm = unreal.DynamicMesh()
    dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
        mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    pts = []
    for i in range(dm.get_vertex_count()):
        _d, w, ok = dm.get_vertex_bone_weights(i)
        if not ok or not w:
            continue
        top = max(w, key=lambda x: x.get_editor_property("weight"))
        if order[top.get_editor_property("bone_index")] not in family:
            continue
        pt, _ = dm.get_vertex_position(i)
        pts.append((pt.x, pt.y, pt.z))
    if len(pts) < 32:
        raise RuntimeError(f"{mesh.get_name()}/{bone}: only {len(pts)} skinned "
                           "vertices -- cannot fit a palm frame")

    n = len(pts)
    c = [sum(p[i] for p in pts) / n for i in range(3)]
    cov = [[0.0] * 3 for _ in range(3)]
    for p in pts:
        d = [p[i] - c[i] for i in range(3)]
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    for i in range(3):
        for j in range(3):
            cov[i][j] /= n
    ev = _eig3(cov)
    normal = _unit(*ev[2][1])

    s1 = s3 = 0.0
    for p in pts:
        d = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
        proj = d[0] * normal.x + d[1] * normal.y + d[2] * normal.z
        s1 += proj * proj
        s3 += proj ** 3
    sigma = math.sqrt(s1 / n) or 1.0
    if (s3 / n) / (sigma ** 3) < 0:
        normal = unreal.Vector(-normal.x, -normal.y, -normal.z)

    finger = _unit(c[0] - wrist.x, c[1] - wrist.y, c[2] - wrist.z)
    return finger, normal


def _signed_twist(src_finger, src_normal, tgt_finger, tgt_normal):
    """Roll left over once the target's finger axis is turned onto the source's.

    This is the part chain alignment does not fix: turning the finger axis onto
    the source's still leaves the hand free to spin about that axis, and the
    spin is what points the palms at the sky.
    """
    axis = tgt_finger.cross(src_finger)
    d = max(-1.0, min(1.0, tgt_finger.dot(src_finger)))
    if axis.length() > 1e-6:
        turned = _rodrigues(_unit(axis.x, axis.y, axis.z), math.acos(d), tgt_normal)
    else:
        turned = tgt_normal
    a = _reject(turned, src_finger)
    b = _reject(src_normal, src_finger)
    return math.degrees(math.atan2(a.cross(b).dot(src_finger), a.dot(b)))


def _rodrigues(axis, angle, v):
    c, s = math.cos(angle), math.sin(angle)
    cr = axis.cross(v)
    return unreal.Vector(
        v.x * c + cr.x * s + axis.x * axis.dot(v) * (1 - c),
        v.y * c + cr.y * s + axis.y * axis.dot(v) * (1 - c),
        v.z * c + cr.z * s + axis.z * axis.dot(v) * (1 - c))


def _reject(v, axis):
    d = v.dot(axis)
    return _unit(v.x - d * axis.x, v.y - d * axis.y, v.z - d * axis.z)


def _bone_xf(anim, bone, time):
    """Component-space TRANSFORM of a bone at a time (not just its position)."""
    xf = unreal.Transform()
    for b in unreal.AnimationLibrary.find_bone_path_to_root(anim, bone):
        xf = xf.multiply(unreal.AnimationLibrary.get_bone_pose_for_time(
            anim, b, time, False))
    return xf


def measure_clip_palm_twist(src_anim, tgt_anim, tgt_mesh, time=0.0):
    """Residual palm roll in an actual retargeted clip, per side, in degrees.

    The reference-pose measurement cannot see the fix: auto-align writes into
    the retargeter's retarget pose, not into the meshes.  This samples what the
    player is shown -- the animated hand -- and is therefore the only honest
    check that the palms came out facing the same way as the mannequin's.

    The hand cloud is rigid to its bone, so the palm frame at time t is the
    reference-pose frame carried by the bone's animated rotation.
    """
    man = _load(MANNEQUIN_MESH)
    out = {}
    for src_bone, tgt_bone in HAND_PAIRS:
        sf0, sn0 = hand_frame(man, src_bone)
        tf0, tn0 = hand_frame(tgt_mesh, tgt_bone)

        sr = _bone_xf(src_anim, src_bone, time).rotation
        s_ref = unreal.AnimPoseExtensions.get_bone_pose(
            unreal.AnimPoseExtensions.get_reference_pose(
                man.get_editor_property("skeleton")),
            src_bone, unreal.AnimPoseSpaces.WORLD).rotation
        tr = _bone_xf(tgt_anim, tgt_bone, time).rotation
        t_ref = unreal.AnimPoseExtensions.get_bone_pose(
            unreal.AnimPoseExtensions.get_reference_pose(
                tgt_mesh.get_editor_property("skeleton")),
            tgt_bone, unreal.AnimPoseSpaces.WORLD).rotation

        def carry(cur, ref, v):
            return cur.rotate_vector(ref.inversed().rotate_vector(v))

        out[tgt_bone] = _signed_twist(
            carry(sr, s_ref, sf0), carry(sr, s_ref, sn0),
            carry(tr, t_ref, tf0), carry(tr, t_ref, tn0))
    return out


def measure_palm_twist(target_mesh):
    """Residual palm roll per side, target vs the mannequin, in degrees."""
    man = _load(MANNEQUIN_MESH)
    out = {}
    for src_bone, tgt_bone in HAND_PAIRS:
        sf, sn = hand_frame(man, src_bone)
        tf, tn = hand_frame(target_mesh, tgt_bone)
        out[tgt_bone] = _signed_twist(sf, sn, tf, tn)
    return out


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

    # Three exemptions, all because the checks below encode what GROUNDED
    # locomotion looks like and these clips are not that.
    #
    # An idle has no gait: an idle whose feet alternate is the bug.
    #
    # An airborne clip has no fixed hip height and no step cycle -- rising is
    # the entire content of a jump.  MM_Jump legitimately reaches z=153 and
    # was the one clip to fail the grounded band.  Upright and in-place still
    # apply to it: a jump that folds double or drifts sideways is still wrong.
    #
    # A HIT REACTION (MM_Death_*, see HIT_SOURCES -- they are flinches, not
    # deaths) is a stagger: the whole point of it is that the creature is
    # knocked off its feet' rhythm and shoved 1.5-2 m backwards, so both "the
    # feet alternate" and "the pelvis stays put" are assertions that it is NOT
    # a reaction.  Upright and the hip band still apply, and between them they
    # are the whole reason these clips were usable here at all: a reaction that
    # ended on the floor would be a death and this project does not have one.
    name = anim.get_name()
    grounded = not any(k in name for k in ("Jump", "Fall", "Land"))
    reaction = "Death" in name
    has_gait = grounded and not reaction and "Idle" not in name
    in_place = not reaction

    for t in samples:
        p = {b: _bone_world(anim, b, t)
             for b in ("Hips", "Head", "LeftFoot", "RightFoot")}
        hips, head = p["Hips"].z, p["Head"].z
        feet = max(p["LeftFoot"].z, p["RightFoot"].z)
        # A reaction is allowed to put its head UNDER its hips, and the hunched
        # creatures do: the wendigo's bind pose already pitches the neck 59 deg
        # forward, so a flinch that bows the head adds to an existing bow and
        # the head ends up around knee height for half a second. Measured, not
        # guessed -- head 73-105 against hips 108-124 on the wendigo, and the
        # zombie and the adventurer stay upright throughout. That is a monster
        # doubling over when it is shot, which is the point. What must still
        # hold is the pelvis (the band below, unrelaxed) and head-above-feet:
        # a reaction that folds a creature onto the floor is a death, and this
        # project's death is a ragdoll.
        upright = head > feet if reaction else head > hips > feet
        if not upright:
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
    if in_place and travel > 50.0:
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

    # And the two the weapon builder addresses by path when this creature is
    # the one the player wears. Same failure mode: a missing pose surfaces as a
    # weapon pointing at the floor, a long way from here.
    for expected in aim_paths(monster):
        if not unreal.EditorAssetLibrary.does_asset_exist(expected):
            bad.append((expected.rsplit("/", 1)[1],
                        "expected by the weapon builder, not produced"))

    # ...and the six hit reactions, which install_hit_reactions() writes onto
    # every character's health component.  All six, in full: the directional
    # pick indexes a six-entry array, so five of six is a silently wrong clip
    # rather than a missing one.
    for expected in hit_paths(monster):
        if not unreal.EditorAssetLibrary.does_asset_exist(expected):
            bad.append((expected.rsplit("/", 1)[1],
                        "hit reaction expected by the weapon builder, not produced"))

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
    src_clip = _load(f"{MANNEQUIN_ANIM_DIR}/{PALM_CALIBRATION_CLIP}")
    totals = []
    for name, mesh, skeleton in monsters:
        _log(f"--- {name} ({skeleton.get_name()}) ---")
        tgt = build_ik_rig(ik_rig_path(name),
                           mesh.get_path_name().split(".")[0],
                           CHAINS_MESHY, RETARGET_ROOT_MESHY)

        # Pass 1 establishes the palm error; pass 2 corrects it. The clips from
        # pass 1 are thrown away -- retarget_animations wipes the directory --
        # so nothing half-corrected can survive into the game.
        rtg = build_retargeter(src, tgt, retargeter_path(name))
        retarget_animations(rtg, mesh, anim_dir(name), anim_prefix(name))
        before = measure_clip_palm_twist(
            src_clip, _load(f"{anim_dir(name)}/{anim_prefix(name)}"
                            f"{PALM_CALIBRATION_CLIP}"), mesh)
        _log("  palm roll before: "
             + ", ".join(f"{k} {v:+.1f}" for k, v in before.items()))

        rtg = build_retargeter(src, tgt, retargeter_path(name),
                               palm_angles={k: -v for k, v in before.items()})
        created = retarget_animations(rtg, mesh, anim_dir(name),
                                      anim_prefix(name))
        after = measure_clip_palm_twist(
            src_clip, _load(f"{anim_dir(name)}/{anim_prefix(name)}"
                            f"{PALM_CALIBRATION_CLIP}"), mesh)
        _log("  palm roll after:  "
             + ", ".join(f"{k} {v:+.1f}" for k, v in after.items()))
        worst = max(abs(v) for v in after.values())
        if worst > PALM_TOLERANCE_DEG:
            raise RuntimeError(
                f"{name}: palms still {worst:.1f} deg off the mannequin after "
                f"correction (tolerance {PALM_TOLERANCE_DEG}); the creature "
                "would run with its palms turned")

        # After the copy, before the checks: verify() asserts the graph is clean.
        fix_retargeted_abp(abp_path(name), skeleton)
        totals.append((name, *verify(created, name, skeleton), worst))

    unreal.EditorAssetLibrary.save_directory(RIG_DIR, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_directory(ANIM_ROOT, only_if_is_dirty=False)

    _log("=" * 52)
    for name, ok, clips, palm in totals:
        _log(f"  {name:12s} {ok}/{clips} clips, palms within {palm:.1f} deg, "
             f"anim BP {abp_path(name).rsplit('/', 1)[1]}")
    _log(f"{len(totals)} monster(s) animate against their own bind pose")


# Guarded, so that a verifier can import this module for its tables -- the six
# HIT_SOURCES in particular, which verify_weapons_and_combat.py checks against
# its own clip order -- without retargeting three creatures as a side effect.
# Both ways this file is actually run (UnrealEditor-Cmd -ExecutePythonScript and
# uepy's runpy) give it __main__, so nothing about running it changes.
if __name__ == "__main__":
    main()
