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

Meshy ships no finger bones, so before each creature's rig is built
finger_rig.py gives it 15 per hand, and finger_verify.py checks afterwards that
the retargeted clips curl them the way the mannequin's curl.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# A live editor keeps imported modules between runs: drop the package so an
# edit to any of its modules is what actually runs.
for _name in [m for m in sys.modules
              if m == "asset_pipeline" or m.startswith("asset_pipeline.")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from asset_pipeline.finger_rig import ensure_fingers              # noqa: E402
from asset_pipeline.finger_verify import verify_fingers           # noqa: E402
from asset_pipeline.mixamo_locomotion import (                    # noqa: E402
    apply_locomotion, mixamo_ready,
)
from asset_pipeline.mixamo_paths import MIXAMO_CREATURES          # noqa: E402
from asset_pipeline.palm_twist import (                           # noqa: E402
    PALM_CALIBRATION_CLIP, PALM_TOLERANCE_DEG,
    measure_clip_hand_turn, measure_clip_palm_twist,
)
from asset_pipeline.retarget_abp import fix_retargeted_abp        # noqa: E402
from asset_pipeline.retarget_paths import (                       # noqa: E402
    ANIM_ROOT, CHARACTER_ROOT, IK_MANNEQUIN, MANNEQUIN_ANIM_DIR,
    MANNEQUIN_MESH, RETARGET_SOURCES, RIG_DIR, abp_path, anim_dir,
    anim_prefix, ik_rig_path, retargeter_path,
)
from asset_pipeline.retarget_rig import (                         # noqa: E402
    build_ik_rig, build_retargeter,
)
from asset_pipeline.retarget_verify import verify                 # noqa: E402
from asset_pipeline.rig_chains import (                           # noqa: E402
    CHAINS_MANNEQUIN, CHAINS_MESHY, RETARGET_ROOT_MANNEQUIN,
    RETARGET_ROOT_MESHY, ROOT_MOTION_BONE_MANNEQUIN,
)
from asset_pipeline.rig_util import (                             # noqa: E402
    _load, _log,
)


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
        # Before the rig: its finger chains name bones Meshy does not ship.
        ensure_fingers(mesh)
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
        # The whole turn, not just the roll: see measure_clip_hand_turn -- the
        # fingers curl about the wrong axis on a hand that only agrees in roll.
        turn = measure_clip_hand_turn(
            src_clip, _load(f"{anim_dir(name)}/{anim_prefix(name)}"
                            f"{PALM_CALIBRATION_CLIP}"), mesh)

        rtg = build_retargeter(src, tgt, retargeter_path(name), palm_angles=turn)
        created = retarget_animations(rtg, mesh, anim_dir(name),
                                      anim_prefix(name))
        calibrated = _load(f"{anim_dir(name)}/{anim_prefix(name)}"
                           f"{PALM_CALIBRATION_CLIP}")
        after = measure_clip_palm_twist(src_clip, calibrated, mesh)
        _log("  palm roll after:  "
             + ", ".join(f"{k} {v:+.1f}" for k, v in after.items()))
        left = measure_clip_hand_turn(src_clip, calibrated, mesh)
        _log("  hand turn after:  "
             + ", ".join(f"{k} {d:+.1f}" for k, (_a, d) in left.items()))
        worst = max(abs(v) for v in after.values())
        if worst > PALM_TOLERANCE_DEG:
            raise RuntimeError(
                f"{name}: palms still {worst:.1f} deg off the mannequin after "
                f"correction (tolerance {PALM_TOLERANCE_DEG}); the creature "
                "would run with its palms turned")

        # After the copy, before the checks: verify() asserts the graph is clean.
        fix_retargeted_abp(abp_path(name), skeleton)
        totals.append((name, *verify(created, name, skeleton), worst))
        verify_fingers(name, mesh)

    # The loop above regenerated each blend space from the mannequin's; a
    # creature that wears the Mixamo packs gets its idle/walk/run back.
    for name, _mesh, _skel in monsters:
        if name in MIXAMO_CREATURES and mixamo_ready(name):
            apply_locomotion(name)
        elif name in MIXAMO_CREATURES:
            _log(f"{name}: no Mixamo clips yet -- run import_mixamo.py")

    unreal.EditorAssetLibrary.save_directory(RIG_DIR, only_if_is_dirty=False)
    unreal.EditorAssetLibrary.save_directory(ANIM_ROOT, only_if_is_dirty=False)

    _log("=" * 52)
    for name, ok, clips, palm in totals:
        _log(f"  {name:12s} {ok}/{clips} clips, palms within {palm:.1f} deg, "
             f"anim BP {abp_path(name).rsplit('/', 1)[1]}")
    _log(f"{len(totals)} monster(s) animate against their own bind pose")


if __name__ == "__main__":
    main()
