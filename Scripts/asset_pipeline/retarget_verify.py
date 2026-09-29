"""retarget_verify -- verify(): does each retargeted clip leave the creature
standing, in place and stepping, and did every asset the builders address by
path get produced?
"""

import unreal

from asset_pipeline.retarget_paths import (
    abp_path, aim_paths, hit_paths, melee_path,
)
from asset_pipeline.rig_util import _bone_world, _log


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
    # A HIT REACTION (MM_HitReact_*, see HIT_SOURCES) has no gait -- the
    # feet stay planted while the chest takes the hit -- so "the feet
    # alternate" is an assertion that it is NOT a reaction. In place, upright
    # and the hip band all still apply: a flinch that travels, or folds a
    # creature onto the floor, is the MM_Death_* mistake over again.
    name = anim.get_name()
    grounded = not any(k in name for k in ("Jump", "Fall", "Land"))
    reaction = "HitReact" in name
    has_gait = grounded and not reaction and "Idle" not in name
    in_place = True

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
