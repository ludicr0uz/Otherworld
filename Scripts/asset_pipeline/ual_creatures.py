"""ual_creatures -- the few UAL clips a creature plays, retargeted onto it:
the zombie's swing, UAL2's Zombie_Scratch, into
/Game/Sourced/Quaternius/UAL/Zombie01/.

Not every clip, as the player gets: a creature plays one or two, and the
batch of 86 costs minutes.  ual_retarget.retarget_ual does the work, given
only the clips named in quaternius_paths.UAL_CREATURE_CLIPS and the idle the
palms are calibrated on.  Needs the creature's IK rig (build_retarget.py) and
the UAL packs already imported (import_quaternius.py step 1).
"""

import unreal

from asset_pipeline.quaternius_paths import (
    PALM_CALIBRATION, UAL_CREATURE_CLIPS, ZOMBIE_MELEE, ual_clip,
    ual_source_clip,
)
from asset_pipeline.rig_util import _bone_world, _load, _log
from asset_pipeline.ual_retarget import retarget_ual
from forest_generator.npc_placement import NPC_VARIANTS

# The scratch must reach: each hand sweeps at least this far over the clip
# (measured on Zombie01: the right 150 cm, the left 64), and the hips stay
# over the spot.
MIN_HAND_SWEEP_CM = {"RightHand": 100.0, "LeftHand": 40.0}
MAX_HIPS_DRIFT_CM = 30.0


def _packs(creature):
    """{short: {name: source clip}} for retarget_ual: the creature's clips and
    the palm calibration idle."""
    packs = {}
    for short, name in (PALM_CALIBRATION,) + tuple(UAL_CREATURE_CLIPS[creature]):
        packs.setdefault(short, {})[name] = _load(ual_source_clip(short, name))
    return packs


def retarget_creatures():
    """Retarget each creature's clips; returns {creature: worst palm roll}.
    A creature with no IK rig yet is skipped with a note."""
    done = {}
    for creature in UAL_CREATURE_CLIPS:
        if not unreal.EditorAssetLibrary.does_asset_exist(
                f"/Game/Sourced/Characters/Rigs/IK_{creature}"):
            unreal.log_warning(f"[RETARGET] note: no IK_{creature} yet, so no UAL "
                               "clips on it: run build_retarget.py, then this again")
            continue
        done[creature] = retarget_ual(creature, _packs(creature))
    return done


def _sweep(clip, bone):
    length = clip.get_editor_property("sequence_length")
    pts = [_bone_world(clip, bone, length * i / 24.0) for i in range(25)]
    return max((a - b).length() for a in pts for b in pts)


def check_creature_clips(check):
    creature = "Zombie01"
    path = ual_clip(creature, *ZOMBIE_MELEE)
    clip = unreal.EditorAssetLibrary.load_asset(path)
    mesh = unreal.EditorAssetLibrary.load_asset(
        f"/Game/Sourced/Characters/SKM_{creature}/SKM_{creature}")
    skel = mesh.get_editor_property("skeleton") if mesh else None
    check(f"{creature} UAL Scratch On Its Skeleton",
          clip is not None and clip.get_editor_property("skeleton") == skel,
          f"({path})")
    worn = [v for v in NPC_VARIANTS if v.mesh.endswith(f"SKM_{creature}")]
    check(f"{creature} Wanderer Swings The UAL Scratch",
          bool(worn) and all(v.melee == path for v in worn),
          f"(NPC_VARIANTS melee: {[v.melee for v in worn]})")
    if clip is None:
        return
    hands = {b: _sweep(clip, b) for b in MIN_HAND_SWEEP_CM}
    check(f"{creature} Scratch Sweeps The Hands (right >= 100 cm, left >= 40)",
          all(hands[b] >= least for b, least in MIN_HAND_SWEEP_CM.items()),
          "(" + ", ".join(f"{b} {d:.0f}" for b, d in hands.items()) + ")")
    length = clip.get_editor_property("sequence_length")
    hips = [_bone_world(clip, "Hips", length * i / 24.0) for i in range(25)]
    drift = max(((a - hips[0]) * unreal.Vector(1, 1, 0)).length() for a in hips)
    check(f"{creature} Scratch Stays In Place (hips within {MAX_HIPS_DRIFT_CM:.0f} cm)",
          drift <= MAX_HIPS_DRIFT_CM, f"({drift:.1f} cm)")
    _log(f"{creature} scratch: {length:.2f} s, hips drift {drift:.1f} cm")
