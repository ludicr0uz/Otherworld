"""The knife's slash: A_KnifeSlash, an AnimSequence keyed here, bone by bone,
for whatever body the player wears.

WHY IT IS KEYED AND NOT RETARGETED
----------------------------------
No clip of a knife attack exists on this machine: the FPS Weapon Bundle ships
the knife's mesh and no animation, and the mannequin's Unarmed set is fists.
So the slash is authored the way body_pose.py authors the crouch -- as turns
stated by what they do ("swing the arm up and out to the right by 25 deg") in
the body's component frame (forward +Y, left +X, up +Z; see body_pose.py) --
except that here they are written into a clip's bone tracks with the
AnimationDataController, so the result plays into a slot like any clip.

THE SLASH
---------
It starts from A_HoldKnife (hold_pose.py), the pose the knife is held in, so the
first and last frames are exactly what the slot shows before and after:

    0.00 s  the ready pose
    0.16 s  wound up: chest turned right, arm raised and out, elbow cocked
    0.26 s  the cut: chest turned left, arm swept down across the body
    0.60 s  back in the ready pose

The blow (COMBAT.knife_impact_s) lands on the way into the cut. Every track
the source clip has is rewritten -- constant at the source's first frame,
except the three turned bones -- and no track is added, so a bone the source
leaves to the mesh's reference pose still does.

A turn D (component space, in the ready pose's frame) on a bone whose parent
turns too becomes the local rotation parent^-1 * D * bone: the parent's own
turn cancels, so each bone is written against the source pose alone.
"""

import math

import unreal

from combat.body_pose import _mul, _conj
from combat.hold_pose import in_place
from combat.log import _log
from uebp.graph import _assets
from combat.paths import HOLD_KNIFE_ANIM_PATH, KNIFE_ANIM_PATH
from combat.tuning import COMBAT

FPS = 30
FRAMES = 18                                   # 0.6 s, the knife's interval

# (time s, chest yaw, arm yaw, arm raise, elbow cock), degrees. Yaw is about
# up, positive to the right; raise and cock are about the body's left-right
# axis, positive up. Eased between keys (smoothstep).
SLASH_KEYS = (
    (0.00, 0.0, 0.0, 0.0, 0.0),
    (0.16, 30.0, 25.0, 30.0, 35.0),
    (0.26, -30.0, -35.0, -15.0, 0.0),
    (FRAMES / FPS, 0.0, 0.0, 0.0, 0.0),
)

UP, LEFT = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)


def _about(axis, deg):
    h = math.radians(deg) / 2.0
    s = math.sin(h)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(h))


def _angles(t):
    """The four angles at time t, eased between SLASH_KEYS."""
    for a, b in zip(SLASH_KEYS, SLASH_KEYS[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / (b[0] - a[0])
            u = u * u * (3.0 - 2.0 * u)
            return tuple(x + (y - x) * u for x, y in zip(a[1:], b[1:]))
    return SLASH_KEYS[-1][1:]


def _turns(t):
    """{role: component-space turn} at time t."""
    chest, arm_yaw, raise_, cock = _angles(t)
    return {
        "chest": _about(UP, chest),
        "upperarm_r": _mul(_about(UP, arm_yaw), _about(LEFT, raise_)),
        "forearm_r": _about(LEFT, cock),
    }


def _q(rot):
    return (rot.x, rot.y, rot.z, rot.w)


def _component_rotation(clip, bone):
    q = (0.0, 0.0, 0.0, 1.0)
    for b in reversed(unreal.AnimationLibrary.find_bone_path_to_root(clip, bone)):
        q = _mul(q, _q(unreal.AnimationLibrary.get_bone_pose_for_time(
            clip, b, 0.0, False).rotation))
    return q


def _parent(clip, bone):
    path = unreal.AnimationLibrary.find_bone_path_to_root(clip, bone)
    return str(path[1]) if len(path) > 1 else None


def _slash_clip(skin):
    """The clip asset, a copy of the knife's hold pose on first build.
    Reused afterwards (a just-written asset cannot be deleted in the same
    editor session), unless the worn skeleton changed under it."""
    eal = unreal.EditorAssetLibrary
    src = _assets().load_asset(HOLD_KNIFE_ANIM_PATH)
    if eal.does_asset_exist(KNIFE_ANIM_PATH):
        clip = _assets().load_asset(KNIFE_ANIM_PATH)
        if clip.get_editor_property("skeleton") == src.get_editor_property("skeleton"):
            return in_place(clip), src
        if not eal.delete_asset(KNIFE_ANIM_PATH):
            raise RuntimeError(f"{KNIFE_ANIM_PATH} is on another skeleton and "
                               "could not be deleted; restart the editor")
    clip = eal.duplicate_asset(HOLD_KNIFE_ANIM_PATH, KNIFE_ANIM_PATH)
    if clip is None:
        raise RuntimeError(f"could not copy {HOLD_KNIFE_ANIM_PATH} to {KNIFE_ANIM_PATH}")
    return in_place(clip), src


def build_knife_slash(skin):
    """Key A_KnifeSlash for ``skin``'s body; returns the clip."""
    clip, src = _slash_clip(skin)
    bones = {"chest": skin.aim_bones[-1],
             "upperarm_r": skin.pose_bones["upperarm_r"],
             "forearm_r": skin.pose_bones["forearm_r"]}
    tracks = [str(n) for n in src.data_model_interface.get_bone_track_names()]
    lower = {t.lower() for t in tracks}
    missing = [b for b in bones.values() if b.lower() not in lower]
    if missing:
        raise RuntimeError(f"{HOLD_KNIFE_ANIM_PATH} has no track for {missing}")

    rest = {t: unreal.AnimationLibrary.get_bone_pose_for_time(src, t, 0.0, False)
            for t in tracks}
    comp = {role: _component_rotation(src, b) for role, b in bones.items()}
    parent = {role: _component_rotation(src, _parent(src, b))
              for role, b in bones.items()}
    by_track = {t.lower(): t for t in tracks}
    moved = {by_track[b.lower()]: role for role, b in bones.items()}

    times = [f / FPS for f in range(FRAMES + 1)]
    turns = [_turns(t) for t in times]
    ctrl = clip.controller
    ctrl.open_bracket(unreal.Text("Key the knife slash"), False)
    ctrl.remove_all_bone_tracks(False)
    ctrl.set_frame_rate(unreal.FrameRate(FPS, 1), False)
    ctrl.set_number_of_frames(unreal.FrameNumber(FRAMES), False)
    for track in tracks:
        xf = rest[track]
        if track in moved:
            role = moved[track]
            rots = [unreal.Quat(*_mul(_conj(parent[role]),
                                      _mul(turn[role], comp[role])))
                    for turn in turns]
        else:
            rots = [xf.rotation] * len(times)
        if not ctrl.add_bone_curve(track, False):
            raise RuntimeError(f"could not add a track for {track}")
        if not ctrl.set_bone_track_keys(track, [xf.translation] * len(times), rots,
                                        [xf.scale3d] * len(times), False):
            raise RuntimeError(f"could not key {track}")
    ctrl.close_bracket(False)
    _assets().save_loaded_asset(clip, False)
    _log(f"built {KNIFE_ANIM_PATH} ({len(tracks)} tracks, {FRAMES} frames at "
         f"{FPS} fps, from {HOLD_KNIFE_ANIM_PATH.rsplit('/', 1)[-1]}; the cut at "
         f"{SLASH_KEYS[2][0]:.2f} s, the blow at {COMBAT.knife_impact_s:.2f} s)")
    return clip
