"""mannequin_bind -- bind a generated body to the mannequin's own skeleton.

THE TWO WAYS TO ANIMATE A GENERATED BODY
----------------------------------------
Per-body skeleton (import_characters.py, build_retarget.py; what the project
did first).  The body keeps the 24-bone rig Meshy returned.  Every clip is
retargeted onto it, so each body has its own skeleton, IK rig, retargeter,
anim blueprint and a copy of every clip -- and each difference between its
bind pose and the mannequin's needs a pass to absorb it (clavicle_align.py,
palm_twist.py, two_hands.py, finger_rig.py, physics_template.py).

Shared skeleton (this package; where the project is going).  The body is put
in the mannequin's pose and skinned to the mannequin's 89 bones, once, on the
way in.  After that it IS a mannequin mesh as far as animation goes:
ABP_Unarmed and every clip keyed for SK_Mannequin play on it as they are.  No
IK rig, no retargeter, no copies.  A clip from somewhere else (Mixamo,
Quaternius) is retargeted once, onto the mannequin, and serves every body.

It is also the only way to fix skinning.  A retarget changes what bones do;
it cannot add a twist bone or change which vertices follow a clavicle.

WHAT RUNS WHERE
---------------
Host-side (no ``unreal``; ../bind_to_mannequin.py is the entry point):
    paths.py          where it reads and writes; the worktree rule
    xform.py          vectors, quaternions, matrices as tuples
    space.py          glTF's space <-> Unreal's
    ref_skeleton.py   the mannequin's reference skeleton out of its .uasset
    glb.py            read a skinned GLB; write it on another skeleton
    body.py           a cached Meshy rig, in Unreal's space
    bone_map.py       constants: which Meshy bone is which mannequin bone
    lbs.py            linear blend skinning: where vertices go when bones move
    hand_frame.py     which way a hand points and which face is the palm
    repose.py         the limbs turned onto the mannequin's lines
    fit.py            the mannequin's skeleton sized to the body
    finger_fit.py     the digits found in the mesh, and curled
    fingers.py        the hand's weight shared over its finger bones
    weights.py        24 bones' weights re-addressed to 89; the clavicle trim
    bind.py           the steps above, in order
    check.py          what can be proved about the result without an editor

Editor-side:
    ../import_bound.py   the bound GLB onto SK_Mannequin, and its checks
    ../bound_look.py     photographs in clip poses, beside the per-body body
                         and Quinn

Tests: dev/tests/test_mannequin_bind.py.

WHAT IS NOT PROVED HERE
-----------------------
check.py proves the file is what the bind meant, and import_bound.py that the
editor read it that way.  Neither proves the bind meant the right thing where
the answer is a look -- the shoulder under a lifted arm, the forearm's twist,
the fingers -- which is what bound_look.py is for.  See the "bound bodies"
section of ../CLAUDE.md for where it stands.
"""
