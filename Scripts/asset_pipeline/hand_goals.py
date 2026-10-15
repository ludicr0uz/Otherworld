"""hand_goals -- the drawn MetaHuman's wrists pinned to the hidden mannequin's.

The retargeter copies rotations, so the drawn hands sit where the
MetaHuman's own arm lengths put them: 2.5 to 6.6 cm off the mannequin's
wrists, which hold the gun (probe_drawn_grip.py, 15 Oct 2026).  This module
gives the bridge the game wears (RTG_MetaHuman_from_UEFN) a target rig with
an IK goal on each hand, one limb solver per arm (upperarm -> hand), and a
Blend to Source op under Run IK Rig that puts each goal on the source's hand,
its place and its turn: the gun hangs off the mannequin's palm, so a drawn
hand on the right spot but turned as the rotation-only retarget turns it
held the 1911 a hand's width above the grip.  The elbow bends in the plane
it already has.

Blend to Source turns a goal by the source hand's turn since its retarget
pose, laid on the target hand's retarget pose, so a hand rolled differently
in the two poses stays rolled by as much (30.2 degrees on both hands, run 2
of the probe).  turn_hands_as_source writes the target hands' retarget-pose
offset that gives them the source's turn in that pose.

The mannequin stays the gameplay truth: the gun socket, the hit bodies and
the server read the hidden mesh, and nothing here touches it.  IK_MetaHuman,
the mannequin bridge's target, is left as it is.
"""

import unreal

from asset_pipeline.quat_math import conj, mul
from asset_pipeline.rig_util import _log, mesh_ref_pose

EAL = unreal.EditorAssetLibrary
RTS = unreal.RetargetSourceOrTarget

LIMB_SOLVER = "/Script/IKRig.IKRigLimbSolver"
BLEND_OP = "/Script/IKRig.IKRetargetBlendToSourceOp"
RUN_IK_OP = "Run IK Rig"
# (retarget chain, goal, its bone, the limb's root bone)
ARMS = (("LeftArm", "LeftHandGoal", "hand_l", "upperarm_l"),
        ("RightArm", "RightHandGoal", "hand_r", "upperarm_r"))


def add_hand_goals(rig, pkg):
    """One goal per hand and one limb solver per arm on ``rig`` (built by
    retarget_rig.build_ik_rig, which leaves solvers and goals alone), its
    arm chains ending on them.  Rebuilt from nothing each run."""
    ctl = unreal.IKRigController.get_controller(rig)
    for i in reversed(range(ctl.get_num_solvers())):
        ctl.remove_solver(i)
    for goal in [g.get_editor_property("goal_name") for g in ctl.get_all_goals()]:
        ctl.remove_goal(goal)
    for chain, goal, bone, root in ARMS:
        made = ctl.add_new_goal(goal, bone)
        if str(made) != goal:
            raise RuntimeError(f"{pkg}: goal {goal} came back {made}")
        g = ctl.get_goal(goal)
        # Held at 1, the solver leaves the hand turned as the goal is (the
        # source's hand, by the op below) and turns only the arm.
        g.set_editor_property("rotation_alpha", 1.0)
        i = ctl.add_solver(LIMB_SOLVER)
        if i < 0:
            raise RuntimeError(f"{pkg}: no solver of type {LIMB_SOLVER}")
        if not (ctl.set_start_bone(root, i) and ctl.connect_goal_to_solver(goal, i)):
            raise RuntimeError(f"{pkg}: limb solver {root} -> {goal} refused")
        if not ctl.set_retarget_chain_goal(chain, goal):
            raise RuntimeError(f"{pkg}: chain {chain} refused goal {goal}")
        end = ctl.get_solver_controller(i).get_solver_settings().get_editor_property("end_bone")
        if str(end) != bone:
            raise RuntimeError(f"{pkg}: limb solver from {root} ends on {end}, not {bone}")
        _log(f"{pkg}: {chain} ends on {goal}, a limb solver from {root} to {end}")
    EAL.save_asset(pkg)
    return rig


def pin_hands_to_source(rtg, pkg):
    """A Blend to Source op under Run IK Rig: each arm's goal on the
    source's hand bone, its place and its turn."""
    ctl = unreal.IKRetargeterController.get_controller(rtg)
    i = ctl.add_retarget_op(BLEND_OP)
    if i < 0:
        raise RuntimeError(f"{pkg}: could not add {BLEND_OP}")
    name = ctl.get_op_name(i)
    if not ctl.set_parent_op_by_name(name, RUN_IK_OP):
        raise RuntimeError(f"{pkg}: {name} would not go under {RUN_IK_OP}")
    i = ctl.get_index_of_op_by_name(name)
    oc = ctl.get_op_controller(i)
    st = oc.get_settings()
    chains = []
    for chain, _goal, _bone, _root in ARMS:
        c = unreal.IKRetargetBlendToSourceChainSettings()
        c.set_editor_property("target_chain_name", chain)
        c.set_editor_property("blend_to_source", 1.0)
        c.set_editor_property("translation_alpha", 1.0)
        c.set_editor_property("rotation_alpha", 1.0)
        chains.append(c)
    st.set_editor_property("chains", chains)
    st.set_editor_property("alpha", 1.0)
    oc.set_settings(st)
    got = {str(c.get_editor_property("target_chain_name")): c.get_editor_property("blend_to_source")
           for c in ctl.get_op_controller(ctl.get_index_of_op_by_name(name))
           .get_settings().get_editor_property("chains")}
    want = {chain: 1.0 for chain, *_ in ARMS}
    if {k: got.get(k) for k in want} != want:
        raise RuntimeError(f"{pkg}: blend to source did not stick: {got}")
    _log(f"{pkg}: {name} under {ctl.get_parent_op_by_name(name)}, chains {got}")
    EAL.save_asset(pkg)
    return rtg


def _q(t):
    r = t.rotation
    return (r.x, r.y, r.z, r.w)


def _pose_turns(ctl, ref, side, bone):
    """(``bone``'s parent's, ``bone``'s own reference local) turns in the
    retarget pose of ``side``: each local is the mesh's reference local
    times the pose's stored offset (IKRetargetProcessor.cpp), so a parent's
    turn is the product down from the root."""
    line = [bone]
    while ref[line[-1]][1]:
        line.append(ref[line[-1]][1])
    world = (0.0, 0.0, 0.0, 1.0)
    for b in reversed(line[1:]):
        local = _local(ref, b)
        o = ctl.get_rotation_offset_for_retarget_pose_bone(unreal.Name(b), side)
        world = mul(world, mul(local, (o.x, o.y, o.z, o.w)))
    return world, _local(ref, bone)


def _local(ref, bone):
    parent = ref[bone][1]
    comp = _q(ref[bone][0])
    return comp if not parent else mul(conj(_q(ref[parent][0])), comp)


def turn_hands_as_source(rtg, source_rig, target_rig, pkg):
    """A TARGET retarget-pose offset on each hand that turns it, in that
    pose, as the source's hand is turned in its own; after the auto-align,
    which sets the arms above it."""
    ctl = unreal.IKRetargeterController.get_controller(rtg)
    src_ref = mesh_ref_pose(unreal.IKRigController.get_controller(source_rig).get_skeletal_mesh())
    tgt_ref = mesh_ref_pose(unreal.IKRigController.get_controller(target_rig).get_skeletal_mesh())
    for _chain, _goal, bone, _root in ARMS:
        s_parent, s_local = _pose_turns(ctl, src_ref, RTS.SOURCE, bone)
        so = ctl.get_rotation_offset_for_retarget_pose_bone(unreal.Name(bone), RTS.SOURCE)
        want = mul(s_parent, mul(s_local, (so.x, so.y, so.z, so.w)))
        t_parent, t_local = _pose_turns(ctl, tgt_ref, RTS.TARGET, bone)
        offset = mul(conj(t_local), mul(conj(t_parent), want))
        ctl.set_rotation_offset_for_retarget_pose_bone(
            unreal.Name(bone), unreal.Quat(*offset), RTS.TARGET)
        _log(f"{pkg}: {bone} turned in the target's retarget pose as the source's, offset {offset}")
    EAL.save_asset(pkg)
    return rtg
