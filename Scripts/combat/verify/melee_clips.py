"""verify.melee_clips -- the knife's and the axe's ready pose and swing
(combat/melee_clips.py): each is Mixamo's clip on the worn skeleton, frame for
frame from where the bake starts, in place, with the right hand closed as the
pistol pose closes it; a ready pose loops, and a swing has its hand out when
the timed blow lands and ends in its ready pose.
"""

import unreal

from asset_pipeline.mixamo_paths import player_clip
from combat.melee_clips import (
    AXE_READY, AXE_SWING, FPS, KNIFE_READY, KNIFE_SWING, MELEE_CLIPS, frame_count,
)
from combat.skin import player_skin
from combat.verify.grip_fit import fist_off
from combat.tuning import COMBAT
from combat.verify.common import check, load

ANIM = unreal.AnimationLibrary
SAME_RAD = 0.01             # a bone's turn, the bake against Mixamo's
FIST_SAME_CM = 0.5          # the fist, in the grip socket's frame
LOOP_CM = 3.0               # a ready pose's hand, last frame against first
# A swing's hand at its end, off the ready pose's. Mixamo's stab and its knife
# idle are two downloads: the stab ends with the hand 14 cm higher than the
# idle holds it, which the slot's blend out takes up.
RETURN_CM = 20.0
TRAVEL_CM = 30.0            # how far forward a swing carries the hand, at least
READY_OF = {KNIFE_SWING: KNIFE_READY, AXE_SWING: AXE_READY}


def _hand(clip, bone, t):
    """``bone``'s place in the body (cm: +Y forward, +Z up), ``t`` s in."""
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
        clip, min(t, clip.get_play_length()), unreal.AnimPoseEvaluationOptions())
    return unreal.AnimPoseExtensions.get_bone_pose(
        pose, bone, unreal.AnimPoseSpaces.WORLD).translation


def _turn(clip, bone, t):
    return ANIM.get_bone_pose_for_time(clip, bone, min(t, clip.get_play_length()),
                                       False).rotation


def check_melee_clip(row, skin):
    name = row.path.rsplit("/", 1)[-1]
    clip, src, worn = load(row.path), load(player_clip(row.role)), load(skin.mesh)
    check(f"{name} is a clip on the worn skeleton, off Mixamo's "
          f"{player_clip(row.role).rsplit('_', 1)[-1]}",
          clip is not None and src is not None
          and clip.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
          str(clip))
    if clip is None or src is None:
        return
    check("...in place: a clip with root motion played into the slot would root the player",
          not clip.get_editor_property("enable_root_motion"))
    want = frame_count(row, src.get_play_length()) / FPS
    check(f"...Mixamo's from {row.start_s:.2f} s to its end",
          abs(clip.get_play_length() - want) < 1e-3
          and abs(row.start_s + want - src.get_play_length()) < 1.0 / FPS,
          f"{clip.get_play_length():.3f} s of {src.get_play_length():.3f}")
    b = skin.pose_bones
    bones = [skin.aim_bones[-1]] + [b[k] for k in ("upperarm_r", "forearm_r", "hand_r",
                                                   "upperarm_l", "forearm_l")]
    # On the bake's own frames: between two of them the two clips' keys are
    # on different grids, and a fast swing differs by a couple of degrees.
    frames = frame_count(row, src.get_play_length())
    times = [round(i * frames / 8.0) / FPS for i in range(9)]
    worst = max(_turn(clip, bone, t).angular_distance(_turn(src, bone, row.start_s + t))
                for bone in bones for t in times)
    check("...frame for frame: the chest and both arms turn as Mixamo's do, nothing keyed",
          worst < SAME_RAD, f"worst {worst:.4f} rad")
    off = fist_off(skin, row.path)
    finger = skin.grip_fingers[1][1]
    still = max(_turn(clip, finger, t).angular_distance(_turn(clip, finger, 0.0))
                for t in times)
    check("...but for the right hand, closed as the pistol pose closes it on every "
          "frame (fist within 0.5 cm)",
          off < FIST_SAME_CM and still < 1e-3, f"{off:.2f} cm, moving {still:.4f} rad")
    hand = b["hand_r"]
    if row.hit_s is None:
        gap = (_hand(clip, hand, clip.get_play_length()) - _hand(clip, hand, 0.0)).length()
        check("...and it loops: the hand ends where it starts",
              gap < LOOP_CM and clip.get_play_length() > 1.0, f"{gap:.1f} cm")
        return
    steps = int(COMBAT.knife_interval_s / 0.05) + 1
    reach = [_hand(clip, hand, i * 0.05).y for i in range(steps)]
    back, out_ = min(reach), max(reach)
    at_blow = _hand(clip, hand, COMBAT.knife_impact_s).y
    check("...the hand is out when the blow lands: at least 80% of the way from "
          "where the swing draws it back to where it stops",
          out_ - back > TRAVEL_CM and at_blow >= back + 0.8 * (out_ - back),
          f"{at_blow:.0f} cm of {back:.0f}..{out_:.0f}")
    ready = load(READY_OF[row].path)
    gap = ((_hand(clip, hand, clip.get_play_length()) - _hand(ready, hand, 0.0)).length()
           if ready else 1e9)
    check("...and it ends in its ready pose",
          gap < RETURN_CM, f"hand {gap:.1f} cm off")


def check_axe_falls():
    """The axe's swing is a chop: the head comes down through the blow."""
    clip, hand = load(AXE_SWING.path), player_skin().pose_bones["hand_r"]
    if clip is None:
        return
    top, blow, after = (_hand(clip, hand, t).z
                        for t in (0.0, COMBAT.knife_impact_s, COMBAT.knife_impact_s + 0.1))
    check("the axe's swing is a chop: the hand is overhead as it starts and is "
          "falling through the blow",
          top > blow + 20.0 and blow > after + 10.0,
          f"{top:.0f} -> {blow:.0f} -> {after:.0f} cm up")


def run():
    skin = player_skin()
    for row in MELEE_CLIPS:
        check_melee_clip(row, skin)
    check_axe_falls()
