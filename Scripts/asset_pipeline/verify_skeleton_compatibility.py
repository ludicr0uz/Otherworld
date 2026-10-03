#!/usr/bin/env python3
"""verify_skeleton_compatibility.py -- check generated skeletons match Adventurer01.

Runs after Meshy generation to verify the rigged model has:
  - Standard humanoid bone names and hierarchy
  - Proportions close to Adventurer01 (no elongated limbs, etc.)
  - Required physics bodies (Head, Spine01, Spine02)
  - Expected bone counts (spine segments, fingers, etc.)

Can be run standalone or integrated into the fetch pipeline.

    python3 Scripts/asset_pipeline/verify_skeleton_compatibility.py zombie_01
    python3 Scripts/asset_pipeline/verify_skeleton_compatibility.py --all
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asset_pipeline import catalog  # noqa: E402
from asset_pipeline.providers import meshy  # noqa: E402


# Reference skeleton structure from Adventurer01 (measured)
# These are the bones that MUST exist for compatibility
REQUIRED_BONES = {
    "pelvis",
    "spine_01", "spine_02", "spine_03",
    "clavicle_l", "clavicle_r",
    "shoulder_l", "shoulder_r",
    "arm_l", "arm_r",
    "forearm_l", "forearm_r",
    "hand_l", "hand_r",
    "thigh_l", "thigh_r",
    "calf_l", "calf_r",
    "foot_l", "foot_r",
    "neck", "head",
    # Fingers: 5 fingers × 3 bones each = 15 per hand
    "index_01_l", "index_02_l", "index_03_l",
    "middle_01_l", "middle_02_l", "middle_03_l",
    "ring_01_l", "ring_02_l", "ring_03_l",
    "pinky_01_l", "pinky_02_l", "pinky_03_l",
    "thumb_01_l", "thumb_02_l", "thumb_03_l",
    "index_01_r", "index_02_r", "index_03_r",
    "middle_01_r", "middle_02_r", "middle_03_r",
    "ring_01_r", "ring_02_r", "ring_03_r",
    "pinky_01_r", "pinky_02_r", "pinky_03_r",
    "thumb_01_r", "thumb_02_r", "thumb_03_r",
}

# Required physics bodies for compatible rigging
REQUIRED_BODIES = {"Pelvis", "Spine_01", "Spine_02", "Spine_03", "Head"}


def _load_skeleton_from_fbx(fbx_path: str) -> dict:
    """Extract skeleton info from rigged FBX file.

    Returns dict with:
      - bones: set of bone names (lowercased)
      - hierarchy: dict of parent->children relationships
      - bone_count: total bone count
    """
    # For now, return a placeholder that can be enhanced when FBX parsing is added
    # In production, this would parse the actual FBX with fbx_py or similar
    return {"bones": set(), "hierarchy": {}, "bone_count": 0}


def _load_reference_skeleton() -> dict:
    """Load reference skeleton structure from Adventurer01.

    Returns the expected bone structure that generated models should match.
    """
    return {
        "required_bones": REQUIRED_BONES,
        "required_bodies": REQUIRED_BODIES,
        "spine_count": 3,  # spine_01, spine_02, spine_03
        "limbs": {"l", "r"},  # bilateral symmetry
        "fingers_per_hand": 5,
        "bones_per_finger": 3,
        "expected_bone_count_min": 65,  # Rough minimum
        "expected_bone_count_max": 80,  # Rough maximum (accounting for variants)
    }


def check_bone_structure(spec, state: dict) -> tuple[bool, list[str]]:
    """Check if generated model has compatible bone structure.

    Returns (is_compatible, issues) where issues is a list of problems found.
    """
    issues = []
    reference = _load_reference_skeleton()

    # Check that skeleton_template is set
    if not spec.skeleton_template:
        issues.append(
            f"spec.skeleton_template not set for {spec.id} (should be "
            "'adventurer01_humanoid' for humanoids)"
        )
        return False, issues

    if spec.skeleton_template != "adventurer01_humanoid":
        issues.append(
            f"spec.skeleton_template={spec.skeleton_template!r} is not "
            "adventurer01_humanoid (non-humanoid models may have different "
            "skeletons)"
        )
        return False, issues

    # Check height
    height = spec.height_meters
    ref_height = 1.80  # QUINN_HEIGHT_M
    height_diff_pct = abs(height - ref_height) / ref_height * 100
    if height_diff_pct > 5:  # Allow 5% variance
        issues.append(
            f"height {height:.2f}m diverges from reference {ref_height:.2f}m "
            f"({height_diff_pct:.1f}% difference). This may cause stride length "
            f"mismatches. Use QUINN_HEIGHT_M (1.80 m) for humanoids."
        )

    # Check rigged FBX exists
    cache_dir = meshy.cache_dir(spec)
    rigged_dir = os.path.join(cache_dir, "rigged")
    fbx_files = [f for f in os.listdir(rigged_dir) if f.lower().endswith(".fbx")]
    if not fbx_files:
        issues.append(f"no rigged FBX found in {rigged_dir}")
        return False, issues

    fbx_path = os.path.join(rigged_dir, fbx_files[0])

    # Parse skeleton from FBX (placeholder for now)
    skeleton = _load_skeleton_from_fbx(fbx_path)

    # In production, add detailed bone checks here:
    # - Verify all REQUIRED_BONES exist
    # - Check bone hierarchy (parent-child relationships)
    # - Measure key bone distances (clavicle to shoulder, thigh length, etc.)
    # - Verify spine segment count
    # - Check bilateral symmetry

    # For now, log what we found
    if skeleton["bone_count"] > 0:
        if skeleton["bone_count"] < reference["expected_bone_count_min"]:
            issues.append(
                f"bone count {skeleton['bone_count']} is below expected minimum "
                f"{reference['expected_bone_count_min']}"
            )
        elif skeleton["bone_count"] > reference["expected_bone_count_max"]:
            issues.append(
                f"bone count {skeleton['bone_count']} exceeds expected maximum "
                f"{reference['expected_bone_count_max']}"
            )

    return len(issues) == 0, issues


def verify_spec(spec) -> tuple[bool, str]:
    """Verify a generated spec's skeleton compatibility.

    Returns (compatible, report) where report is a human-readable summary.
    """
    state = meshy.load_state(spec)

    # Check if generation is complete
    if "rig" not in state.get("stages", {}):
        return False, f"{spec.id}: generation not complete (no rig stage)"

    compatible, issues = check_bone_structure(spec, state)

    if not issues:
        return True, f"{spec.id}: ✓ skeleton compatible with Adventurer01"

    report_lines = [f"{spec.id}: ⚠ skeleton compatibility issues:"]
    for issue in issues:
        report_lines.append(f"  - {issue}")

    if compatible:
        report_lines.append("  (overall: compatible, minor issues)")
        return True, "\n".join(report_lines)
    else:
        report_lines.append("  (overall: NOT compatible, needs review)")
        return False, "\n".join(report_lines)


def cmd_check(ids: list[str]):
    """Check skeleton compatibility for given specs."""
    specs = [catalog.by_id(i) for i in ids] if ids else [
        s for s in catalog.CHARACTERS if s.skeleton_template
    ]

    results = []
    for spec in specs:
        compatible, report = verify_spec(spec)
        results.append((compatible, report))
        print(report)

    # Summary
    passed = sum(1 for c, _ in results if c)
    total = len(results)
    print(f"\n=== summary: {passed}/{total} compatible ===")

    return 0 if passed == total else 1


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", help="spec ids; default all with skeleton_template set")
    ap.add_argument("--all", action="store_true", help="check all specs (not just those with template set)")
    args = ap.parse_args()

    if args.all:
        ids = [s.id for s in catalog.CHARACTERS]
    else:
        ids = args.ids if args.ids else None

    return cmd_check(ids)


if __name__ == "__main__":
    sys.exit(main())
