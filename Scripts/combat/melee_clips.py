"""The melee clips: the knife's and the axe's ready pose and swing, baked from
Mixamo's clips for the body the player wears.

    A_HoldKnife   the knife ready           Mixamo's "Knife Idle"
    A_KnifeSlash  the knife's swing: a stab Mixamo's "Stabbing"
    A_HoldAxe     the axe ready             Pro Melee Axe Pack, "standing idle"
    A_AxeSwing    the axe's swing: a chop   ..."standing melee attack downward"

Nothing here is keyed by hand: until C2 the ready pose was arm directions
written onto the idle and the slash three turns keyed onto that (hold_pose.py
still keys the poses no clip exists for: the carry and the torch's two).
asset_pipeline/import_mixamo.py imports the four and retargets them onto the
player's skeleton (mixamo_paths.PLAYER_CLIPS, mixamo_player.py); this copies
each into the game's own asset, frame for frame, with two changes:

    the fist   the right hand's fingers are the pistol pose's on every frame,
               closed round a grip. Mixamo's hand is posed for a prop the game
               does not have, and the items are seated in the pistol's fist
               (grip.py): the hand keeps the clip's place and turn, and the
               handle stays in it through the swing.
    the cut    a swing starts ``COMBAT.knife_impact_s`` before the moment its
               clip lands (MeleeClip.hit_s, read off the hand's path), so the
               blow, which is timed and not notified (weapon_component/
               punch.py), falls where the clip strikes. The wind-up before
               that is not played; the recovery after it is, to the clip's
               end, unless the next swing cuts it short.

A ready pose is the whole idle, looping (the equip plays it into the slot as
it played the constant poses). Every bake is in place (hold_pose.in_place).
The clips are on the Game Animation Sample's skeleton, so a body on another
one cannot be built a knife: the build says so.
"""

import dataclasses

import unreal

from asset_pipeline.mixamo_paths import player_clip
from asset_pipeline.rig_util import mesh_ref_pose
from combat.hold_pose import _below, _copy_of, _shown
from combat.log import _log
from combat.paths import (
    AXE_ANIM_PATH, HOLD_AXE_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, KNIFE_ANIM_PATH,
)
from combat.tuning import COMBAT
from uebp.graph import _assets

FPS = 30


@dataclasses.dataclass(frozen=True)
class MeleeClip:
    """One baked clip: where it lands, which of mixamo_paths.PLAYER_CLIPS it
    is, and for a swing the time in Mixamo's clip at which it strikes (None:
    a ready pose)."""
    path: str
    role: str
    hit_s: float = None

    @property
    def start_s(self):
        """Where in Mixamo's clip the bake starts."""
        return 0.0 if self.hit_s is None else self.hit_s - COMBAT.knife_impact_s


# hit_s: the knife's hand is at the end of its thrust 0.97 s in (it leaves
# the hip at 0.7 and is 73 cm out by 1.0); the axe's is coming down past the
# chest 0.85 s in (overhead at 0.7, at the waist by 0.9).
KNIFE_READY = MeleeClip(HOLD_KNIFE_ANIM_PATH, "knife_ready")
KNIFE_SWING = MeleeClip(KNIFE_ANIM_PATH, "knife_swing", 0.97)
AXE_READY = MeleeClip(HOLD_AXE_ANIM_PATH, "axe_ready")
AXE_SWING = MeleeClip(AXE_ANIM_PATH, "axe_swing", 0.85)
MELEE_CLIPS = (KNIFE_READY, KNIFE_SWING, AXE_READY, AXE_SWING)


def _source(skin, row):
    path = player_clip(row.role)
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError(f"{path} is not here: run Scripts/asset_pipeline/"
                           "import_mixamo_player.py (the Mixamo downloads go in "
                           "assets/cache/mixamo)")
    src = _assets().load_asset(path)
    worn = _assets().load_asset(skin.mesh).get_editor_property("skeleton")
    if src.get_editor_property("skeleton") != worn:
        raise RuntimeError(f"{path} is on another skeleton than {skin.mesh}: the "
                           "melee clips are retargeted onto the Game Animation "
                           "Sample's mannequin alone (asset_pipeline/mixamo_player.py)")
    return src


def frame_count(row, source_length):
    """How many frames the bake of ``row`` has, off a source that long."""
    return max(1, int(round((source_length - row.start_s) * FPS)))


def _bake(skin, row, fist, fingers):
    src = _source(skin, row)
    frames = frame_count(row, src.get_play_length())
    times = [min(row.start_s + f / FPS, src.get_play_length()) for f in range(frames + 1)]
    lower = {b.lower() for b in fingers}
    tracks = [str(n) for n in src.data_model_interface.get_bone_track_names()]
    moving = [t for t in tracks if t.lower() not in lower]
    # [frame][track]: the source's own keys, so a bone it leaves to the mesh's
    # reference pose is left to it here too.
    poses = [unreal.AnimationLibrary.get_bone_poses_for_time(src, moving, t, False)
             for t in times]

    clip = _copy_of(player_clip(row.role), row.path)
    ctrl = clip.controller
    ctrl.open_bracket(unreal.Text("Bake a melee clip"), False)
    ctrl.remove_all_bone_tracks(False)
    ctrl.set_frame_rate(unreal.FrameRate(FPS, 1), False)
    ctrl.set_number_of_frames(unreal.FrameNumber(frames), False)
    for i, track in enumerate(moving):
        xfs = [pose[i] for pose in poses]
        _key(ctrl, track, xfs)
    for bone in sorted(fingers):
        _key(ctrl, bone, [fist[bone][2]] * len(times))
    ctrl.close_bracket(False)
    _assets().save_loaded_asset(clip, False)
    _log(f"built {row.path} ({len(moving)} tracks and the fist's {len(fingers)}, "
         f"{frames} frames at {FPS} fps, off {src.get_name()} from {row.start_s:.2f} s"
         + (f"; it strikes {COMBAT.knife_impact_s:.2f} s in)" if row.hit_s else ", looping)"))
    return clip


def _key(ctrl, track, xfs):
    if not ctrl.add_bone_curve(track, False):
        raise RuntimeError(f"could not add a track for {track}")
    if not ctrl.set_bone_track_keys(track, [x.translation for x in xfs],
                                    [x.rotation for x in xfs],
                                    [x.scale3d for x in xfs], False):
        raise RuntimeError(f"could not key {track}")


def build_melee_clips(skin):
    """Bake every row of MELEE_CLIPS for ``skin``'s body; returns
    {path: clip}."""
    mesh = _assets().load_asset(skin.mesh)
    pistol = _assets().load_asset(skin.aim_pistol)
    if mesh is None or pistol is None:
        raise RuntimeError(f"could not load {skin.mesh} or {skin.aim_pistol}")
    ref = mesh_ref_pose(mesh)
    fist = _shown(pistol, mesh, ref)
    hand = skin.pose_bones["hand_r"]
    fingers = {b for b in ref if _below(ref, b, hand)}
    return {row.path: _bake(skin, row, fist, fingers) for row in MELEE_CLIPS}
