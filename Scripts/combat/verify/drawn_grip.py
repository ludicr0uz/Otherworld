"""verify.drawn_grip -- the drawn MetaHuman's fingers on the gun
(drawn_grip_graph.py, weapon_component/drawn_grip.py, drawn_grip_bake.py):
A_DrawnGrip is three frames a gun at one a second, keying both hands'
fingers and no root motion; the drawn body's anim Blueprint lays it over the
retarget's fingers, the right hand's then the left's, each by its weight;
its update copies the weights off the weapon component, which finds the
gun's frames by the ready pose in hand. The fit itself (no finger in the
gun, the pads on it, the index at the trigger) is measured in the running
game: probes/probe_drawn_grip.py.
"""

import unreal

from asset_pipeline.gas_bridge_paths import ABP_RETARGET_UEFN
from combat.drawn_grip import roots
from combat.drawn_grip_consts import (
    CLIP, CLIP_FPS, FRAMES_PER_GUN, GRIP_LEFT_VAR, GRIP_RIGHT_VAR, GUNS,
)
from combat.drawn_grip_graph import COPIED, LAYERED_CLASS, RETARGET_CLASS, ROOT_CLASS
from combat.drawn_grip_vars import GripCarry, GripGun, GripLeft, GripPoses, GripRight
from combat.finger_pose import clip_for
from combat.paths import WEAPON_COMP_BP_PATH
from combat.skin import player_skin
from combat.verify.anchor import feeders, the, title
from combat.verify.common import cdo, check, graph, load, num_pin
from combat.verify.fixtures import wg

ANIM = unreal.AnimationLibrary


def _cls(node):
    return node.get_class().get_name()


def _filters(blend):
    layer = blend.get_editor_property("node").get_editor_property("layer_setup")
    return [str(f.get_editor_property("bone_name"))
            for f in layer[0].get_editor_property("branch_filters")] if layer else []


def _path(asset):
    return asset.get_path_name().split(".")[0] if asset else None


def check_clip():
    clip = load(CLIP)
    # Counted off its length: get_num_frames answers at the sampling rate
    # the engine resamples it to (30 a second), not the clip's own.
    frames = round(ANIM.get_sequence_length(clip) * CLIP_FPS) + 1 if clip else 0
    tracks = [str(b) for b in ANIM.get_animation_track_names(clip)] if clip else []
    want = [b for side in "rl" for b in roots(side)]
    check(f"{CLIP.rsplit('/', 1)[1]} holds {FRAMES_PER_GUN} frames for each of the "
          f"{len(GUNS)} guns at {CLIP_FPS} a second, keying every finger root of both "
          "hands, with no root motion",
          clip is not None and frames == FRAMES_PER_GUN * len(GUNS)
          and all(b in tracks for b in want)
          and not clip.get_editor_property("enable_root_motion"),
          f"{frames} frames, {len(tracks)} tracks, missing "
          f"{[b for b in want if b not in tracks]}")


def check_anim_graph():
    abp = load(ABP_RETARGET_UEFN)
    nodes = graph(abp, "AnimGraph").list_all_nodes() if abp else []
    root = the(n for n in nodes if _cls(n) == ROOT_CLASS)
    left = the(feeders(root, "Result")) if root else None
    right = the(feeders(left, "BasePose")) if left else None
    base = the(feeders(right, "BasePose")) if right else None
    chain = [left, right]
    ok = (all(n is not None and _cls(n) == LAYERED_CLASS for n in chain)
          and base is not None and _cls(base) == RETARGET_CLASS
          and _filters(left) == roots("l") and _filters(right) == roots("r"))
    check(f"{ABP_RETARGET_UEFN.rsplit('/', 1)[1]}: the retarget, then the right "
          "fingers from their roots, then the left's, laid over by layered blends",
          ok, f"root <- {[title(n) if n else None for n in chain + [base]]}")
    weights = {GRIP_RIGHT_VAR: right, GRIP_LEFT_VAR: left}
    fed = {v: [title(f) for f in feeders(n, "BlendWeights_0")] if n else []
           for v, n in weights.items()}
    check("...each hand by its own weight", all(fed[v] == [f"Get {v}"] for v in fed), str(fed))
    events = graph(abp).list_all_nodes() if abp else []
    sets = {v: the(n for n in events if title(n) == f"Set {v}") for v, _c in COPIED}
    copied = {v: [title(f) for f in feeders(n, v)] if n else None for v, n in sets.items()}
    check("...and its update copies the five off the pawn's weapon component",
          all(copied[v] == [f"Get {theirs}"] for v, theirs in COPIED), str(copied))


def check_component():
    poses = [_path(c) for c in (cdo(load(WEAPON_COMP_BP_PATH)).get_editor_property(str(GripPoses))
                                or [])]
    want = [clip_for(g) for g in GUNS]
    check(f"the weapon component's {GripPoses} is each gun's ready clip, in "
          "drawn_grip_consts.GUNS' order", poses == want, f"{poses} vs {want}")
    sets = {v: the(n for n in wg if title(n) == f"Set {v}")
            for v in (GripGun, GripRight, GripLeft, GripCarry)}
    gun = sets[GripGun]
    to_float = the(feeders(gun, str(GripGun))) if gun else None
    times = the(feeders(to_float, "InInt")) if to_float else None
    check(f"...which writes the four, {GripGun} the found pose's place x {FRAMES_PER_GUN}",
          all(sets.values()) and times is not None
          and num_pin(times, "B") == FRAMES_PER_GUN,
          f"{ {str(v): bool(n) for v, n in sets.items()} }, "
          f"{title(times) if times else None}")


def run():
    if player_skin().retarget != ABP_RETARGET_UEFN:
        unreal.log_warning("[VERIFY] drawn_grip: the player is not the MetaHuman over the "
                           "UEFN rig; nothing to check")
        return
    check_clip()
    check_anim_graph()
    check_component()
