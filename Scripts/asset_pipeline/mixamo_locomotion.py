"""mixamo_locomotion -- put a creature's retargeted Mixamo idle, walk and run
into its locomotion blend space, and check the result.

The creature's anim Blueprint is a retargeted copy of ABP_Unarmed, and what it
plays on the ground is its own copy of BS_Idle_Walk_Run
(A_<Creature>_BS_Idle_Walk_Run).  Re-pointing that blend space's samples,
and moving each row to its clip's ground speed, is the whole integration: the
state machine, the sync group and the speed and direction the ABP feeds it
are untouched, and so is every other creature.

build_retarget.py regenerates the blend space from the mannequin's on every
run, so it calls apply_locomotion() again at its end; import_mixamo.py calls
it too.  Either order leaves the zombie shambling.
"""

import unreal

from asset_pipeline.mixamo_paths import (
    LOCOMOTION, MELEE, RATE_SCALE_RANGE, mixamo_clip, source_clip,
)
from asset_pipeline.retarget_paths import anim_dir, anim_prefix
from asset_pipeline.retarget_verify import _check_pose, _ref_hips_z
from asset_pipeline.rig_util import _bone_world, _load, _log


def blend_space_path(creature):
    return f"{anim_dir(creature)}/{anim_prefix(creature)}BS_Idle_Walk_Run"


def clip_ground_speed(clip):
    """cm/s the hips cover over the SOURCE clip (on X Bot, before the
    retargeter zeroes the travel), or None for a clip exported in place."""
    length = clip.get_editor_property("sequence_length")
    a, b = _bone_world(clip, "Hips", 0.0), _bone_world(clip, "Hips", length)
    travel = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
    return travel / length if travel > 20.0 and length > 0 else None


def _row_placement(meant, source):
    """(rate, sample speed) for a clip meant for ``meant`` cm/s.

    rate = meant / clip speed, clamped (RATE_SCALE_RANGE); the sample then
    sits at the speed the clip covers at that rate.  An in-place clip (the
    idle) stays where it was meant, at rate 1.
    """
    speed = clip_ground_speed(source)
    if not meant or not speed:
        return 1.0, meant
    lo, hi = RATE_SCALE_RANGE
    rate = max(lo, min(hi, meant / speed))
    return rate, speed * rate


def mixamo_ready(creature):
    return all(unreal.EditorAssetLibrary.does_asset_exist(mixamo_clip(creature, *c))
               for c in list(LOCOMOTION.values()) + [MELEE])


def _rows(samples):
    """The distinct Speed values of the samples, slowest first.

    Taken by order, not by value: once applied, the rows no longer sit at the
    0/300/600 the mannequin copy was built with, and a re-run must still find
    them.
    """
    return sorted({round(s.get_editor_property("sample_value").y, 3)
                   for s in samples})


def apply_locomotion(creature):
    """Rewrite each sample of the creature's blend space to its row's clip."""
    bs = _load(blend_space_path(creature))
    samples = list(bs.get_editor_property("sample_data"))
    rows = _rows(samples)
    if len(rows) != len(LOCOMOTION):
        raise RuntimeError(f"{bs.get_name()}: {len(rows)} speed rows {rows}, "
                           f"expected {len(LOCOMOTION)}")

    placed = {}
    for row, (meant, (short, stem)) in zip(rows, sorted(LOCOMOTION.items())):
        rate, speed = _row_placement(meant, _load(source_clip(short, stem)))
        placed[row] = (_load(mixamo_clip(creature, short, stem)), rate, speed)
        _log(f"  {creature} {stem}: meant for {meant:.0f} cm/s, rate "
             f"{rate:.2f}, sample at {speed:.0f} cm/s")

    for s in samples:
        value = s.get_editor_property("sample_value")
        clip, rate, speed = placed[round(value.y, 3)]
        s.set_editor_property("animation", clip)
        s.set_editor_property("rate_scale", rate)
        s.set_editor_property("sample_value",
                              unreal.Vector(value.x, speed, value.z))
    # A sample off the grid is snapped back onto it when the axis snaps.
    params = list(bs.get_editor_property("blend_parameters"))
    for p in params:
        p.set_editor_property("snap_to_grid", False)
    bs.set_editor_property("blend_parameters", params)
    # The default notify is wanted here: PostEditChange is what makes the
    # blend space re-validate and re-triangulate its samples.
    bs.set_editor_property("sample_data", samples)
    unreal.EditorAssetLibrary.save_asset(blend_space_path(creature),
                                         only_if_is_dirty=False)
    _log(f"{creature}: {len(samples)} blend space samples now play Mixamo "
         f"({bs.get_name()})")


def check_mixamo_set(creature, check):
    """The creature's Mixamo set, as ``check(label, ok, detail)`` calls."""
    mesh = _load(f"/Game/Sourced/Characters/SKM_{creature}/SKM_{creature}")
    skel = mesh.get_editor_property("skeleton")
    ref_hips = _ref_hips_z(skel)

    bs = _load(blend_space_path(creature))
    samples = list(bs.get_editor_property("sample_data"))
    rows = _rows(samples)
    for i, (meant, (short, stem)) in enumerate(sorted(LOCOMOTION.items())):
        want = mixamo_clip(creature, short, stem).rsplit("/", 1)[1]
        row = rows[i] if i < len(rows) else None
        got = {s.get_editor_property("animation").get_name()
               for s in samples
               if round(s.get_editor_property("sample_value").y, 3) == row}
        check(f"{creature} Blend Space Row {i} Plays {stem}",
              len(rows) == len(LOCOMOTION) and got == {want},
              f"(speed {row}, got {sorted(got)})")
        # Where the row sits is the promise that its feet stay planted.
        _rate, speed = _row_placement(meant, _load(source_clip(short, stem)))
        check(f"{creature} {stem} Sits At Its Ground Speed",
              row is not None and abs(row - speed) < 1.0,
              f"(row {row}, clip covers {speed:.0f} cm/s)")
        clip = _load(mixamo_clip(creature, short, stem))
        problems = _check_pose(clip, ref_hips)
        check(f"{creature} {stem} Upright, In Place, Stepping",
              not problems, "; ".join(problems[:3]))

    melee = unreal.EditorAssetLibrary.load_asset(mixamo_clip(creature, *MELEE))
    check(f"{creature} Mixamo Melee Clip On Its Skeleton",
          melee is not None and melee.get_editor_property("skeleton") == skel,
          f"({mixamo_clip(creature, *MELEE)})")
