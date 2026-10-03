"""retarget_rig -- build one IK Rig from a chain table, and one retargeter
between two rigs.

Shared by both retarget entry points: build_retarget.py (mannequin -> each
Meshy creature) and import_mixamo.py (X Bot -> each creature that wears the
Mixamo packs).  The target side is always a Meshy creature, which is why the
retargeter's finger and mapping checks read CHAINS_MESHY.
"""

import unreal

from asset_pipeline.clavicle_align import align_clavicles
from asset_pipeline.palm_twist import _apply_palm_twist
from asset_pipeline.rig_chains import CHAINS_MESHY, meshy_finger_bones
from asset_pipeline.rig_util import _bone_names, _load, _log, _reuse_or_create


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
    # Then the clavicles, which that leaves as they are, and the arms again
    # from where they now hang (clavicle_align.py).
    align_clavicles(ctl, source_rig, target_rig, name)
    _log(f"{name}: target retarget pose auto-aligned to the source (chain to chain)")

    # Chain alignment fixes DIRECTION and leaves ROLL, which is why the monsters
    # ran with their palms up -- measured at 80-95 degrees off the mannequin in
    # the retargeted clips. The hands get a second pass with MESH_TO_MESH, which
    # derives orientation from the skinned geometry rather than from bone axes.
    # It has to be geometry: Epic runs X down the bone and Mixamo runs Y, so the
    # rotation-axis methods would be measuring the convention, not the pose.
    _apply_palm_twist(ctl, name, palm_angles or {})

    # The fingers keep their bind pose. finger_rig.py laid them out as the
    # mannequin's reference fingers carried into this hand, so relative to the
    # PALM they already sit where the source's sit -- and relative to the palm is
    # all that matters, because a finger's delta is the hand's delta plus its
    # own. Auto-align points them the source's way in WORLD space, which is
    # wrong twice over: the roll above then carried them 130 degrees round the
    # hand (thumbs curled backwards), and aligned after the roll they still
    # inherit the wrist bend chain alignment leaves between the two hands, which
    # over-curled every knuckle by ~45 degrees.
    # Spelled out: unreal.Quat() is (0, 0, 0, 0), not the identity, and as an
    # offset it collapsed every finger joint onto its knuckle.
    IDENTITY = unreal.Quat(0.0, 0.0, 0.0, 1.0)
    for bone in meshy_finger_bones():
        ctl.set_rotation_offset_for_retarget_pose_bone(
            unreal.Name(bone), IDENTITY, unreal.RetargetSourceOrTarget.TARGET)

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
