"""The drawn MetaHuman's fitted hands, keyed: drawn_grip_consts.CLIP, three
frames a gun (hold, sights, carry), each frame every finger bone of both
hands, the fingers bent onto the gun's real mesh (drawn_grip.py fits,
drawn_grip_mesh.py measures).

Where the hands are comes from drawn_grip_capture.json (probe_drawn_grip's
capture, trimmed: `cd Scripts && python3 -m combat.drawn_grip`), so the
bake needs no running game; a change to where the wrists are (a ready pose,
the grip, the retarget's hand goals) wants the probe run again and the
capture taken again. The right hand is fitted once a gun (the gun is rigid
in it), the index drawn to the trigger (drawn_grip_consts.TRIGGER); the
left once a frame, against every placement its states have it in. A
handgun's left fingers lie on the mesh and on the right hand's fitted
fingers, which they close over.

A clip is not played on the drawn body as keyed: the game retargets it
from its skeleton's reference pose (metahuman_base_skel's, the female body's)
to the mesh's (Taro's), and each finger bone's local comes out turned and
moved by the difference (a metacarpal 29 degrees, a knuckle 1.2 cm). So the
keys are settled (settle()): played on the body as the game plays it
(AnimPoseExtensions, retargeting on: it gives the game's locals to 0.01
degree), each key is corrected by what playing did to it, until the pose
played is the fit. A change of body wants the bake run again.
(AnimationLibrary.get_bone_pose_for_time does not read the keys back: it
reads them retargeted another way.)

drawn_grip_graph.py lays the clip over the retarget's fingers.
"""

import json
import math
import os

import unreal

from asset_pipeline.metahuman_paths import BODY_MESH
from combat import drawn_grip as D
from combat import drawn_thumb, finger_fit
from combat.drawn_grip_consts import (
    CLIP, CLIP_FPS, FRAMES, GUNS, HANDGUNS, THUMB_CEILING_CM, THUMB_REST, TRIGGER,
)
from combat.drawn_grip_mesh import gun_solid
from combat.log import _log
from uebp.graph import _assets

CAPTURE_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "drawn_grip_capture.json")
# The skeleton the clip is keyed on: the drawn body's.
SKELETON = "/Game/MetaHumans/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel"
# settle(): at most this many rounds, and how far the pose played may still
# be off the fit, any bone of any frame (degrees, cm). One round settles it
# to 0.13 degrees, which no further round improves (the clip's compression).
SETTLE_ROUNDS = 3
SETTLED_DEG = 0.25
SETTLED_CM = 0.01


def capture():
    with open(CAPTURE_JSON) as f:
        return json.load(f)


def trigger(solid, segment):
    """The trigger's segment laid a skin off its face: each end moved onto
    the nearest point of the mesh and back out a SKIN_CM."""
    out = []
    for p in segment:
        q = solid.toward(p)
        way = tuple(a - b for a, b in zip(p, q))
        if solid.distance(p) < 0.0:
            way = tuple(-w for w in way)
        n = max(sum(w * w for w in way) ** 0.5, 1e-9)
        out.append(tuple(b + finger_fit.SKIN_CM * w / n for b, w in zip(q, way)))
    return tuple(out)


def _said(label, before, after):
    return f"{label} " + ", ".join(
        f"{f} {before[f][0]:+.2f}/{before[f][1]:+.2f} -> {after[f][0]:+.2f}/{after[f][1]:+.2f}"
        for f in before)


def fit_gun(gun, row, solid):
    """{frame: {bone: local}} of ``gun``'s three frames, both hands; logs
    each hand's riding points (nearest/furthest, cm off a skin off the gun)
    before and after."""
    hand_r = D.xf_of(row["hand_r"])
    right = D.locals_of(row["right"])
    seen_r = D.Seen(solid, [hand_r])
    into = D.inverse(hand_r)
    pull = tuple(D.apply(into, p) for p in trigger(solid, TRIGGER[gun]))
    moved, bends = D.fit_hand(right, "r", seen_r, trigger=pull)
    right_fit = {**right, **moved}
    if gun in THUMB_REST:
        right_fit, bends["thumb"] = _rest_thumb(gun, right_fit, hand_r, solid)
    pad = finger_fit.riding(D.finger_points(right_fit, "r")["index"])[D.PAD]
    near = finger_fit._len(finger_fit._sub(pad, finger_fit.aimed(pull, pad)))
    _log(_said(f"{gun} right", D.offsets(right, "r", seen_r),
               D.offsets(right_fit, "r", seen_r))
         + f"; index pad {near:.2f} cm off the trigger; bends "
         + ", ".join(f"{f} " + "/".join(f"{a:+.0f}" for a in
                                         (b if isinstance(b, tuple) else (b,)))
                     for f, b in bends.items()))
    fist = finger_fit.Union([solid, D.capsules(right_fit, "r", hand_r)])
    out = {}
    for frame in FRAMES:
        if gun in HANDGUNS and frame == "carry":
            out[frame] = out["hold"]
            continue
        spec = row["frames"][frame]
        left = D.locals_of(spec["left"])
        seen = D.Seen(fist if gun in HANDGUNS else solid, [D.xf_of(h) for h in spec["hands"]])
        moved, _bends = D.fit_hand(left, "l", seen)
        left_fit = {**left, **moved}
        each = [min(o[0] for o in D.offsets(left_fit, "l", D.Seen(seen.solid, [h])).values())
                for h in seen.hands]
        _log(_said(f"{gun} left {frame}", D.offsets(left, "l", seen),
                   D.offsets(left_fit, "l", seen))
             + "; deepest by state " + " ".join(f"{d:+.2f}" for d in each))
        out[frame] = {**right_fit, **left_fit}
    return out


def _rest_thumb(gun, right, hand_r, solid):
    """``right`` with its thumb laid on the gun's THUMB_REST (drawn_thumb.lay),
    clear of the gun and the fitted fingers, and the search's params."""
    into = D.inverse(hand_r)
    rest = tuple(D.apply(into, p) for p in trigger(solid, THUMB_REST[gun]))
    fist = finger_fit.Union([solid, D.capsules(right, "r", hand_r)])
    height = lambda p: D.apply(hand_r, p)[2]
    bones = D.chain("thumb", "r")
    moved, params = drawn_thumb.lay(right, bones, D.Seen(fist, [hand_r]), rest, height,
                                    THUMB_CEILING_CM)
    out = {**right, **moved}
    tip = D.finger_points(out, "r")["thumb"][-1]
    near = finger_fit._len(finger_fit._sub(tip, finger_fit.aimed(rest, tip)))
    _log(f"{gun} right thumb laid on its rest: tip {near:.2f} cm off it, top "
         f"{drawn_thumb.top(right, bones, height):+.2f} -> {drawn_thumb.top(out, bones, height):+.2f}"
         f" cm (its axis at most {THUMB_CEILING_CM - finger_fit.SKIN_CM:+.2f}); turns "
         + "/".join(f"{a:+.0f}" for a in params))
    return out, params


def _clip():
    eal = unreal.EditorAssetLibrary
    if eal.does_asset_exist(CLIP):
        return _assets().load_asset(CLIP)
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property("target_skeleton", _assets().load_asset(SKELETON))
    folder, name = CLIP.rsplit("/", 1)
    clip = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.AnimSequence, factory)
    if clip is None:
        raise RuntimeError(f"could not create {CLIP}")
    return clip


def _key(clip, frames):
    bones = sorted(frames[0])
    ctrl = clip.controller
    ctrl.open_bracket(unreal.Text("The drawn hands on each gun"), False)
    ctrl.remove_all_bone_tracks(False)
    ctrl.set_frame_rate(unreal.FrameRate(CLIP_FPS, 1), False)
    ctrl.set_number_of_frames(unreal.FrameNumber(len(frames) - 1), False)
    for bone in bones:
        if not ctrl.add_bone_curve(bone, False):
            raise RuntimeError(f"could not add a track for {bone}")
        locs = [unreal.Vector(*f[bone][0]) for f in frames]
        rots = [unreal.Quat(*f[bone][1]) for f in frames]
        if not ctrl.set_bone_track_keys(bone, locs, rots,
                                        [unreal.Vector(1.0, 1.0, 1.0)] * len(frames), False):
            raise RuntimeError(f"could not key {bone}")
    ctrl.close_bracket(False)


def _played(clip, mesh, frames):
    """[{bone: Transform}] of each frame's bones as the game plays the clip
    on ``mesh`` (retargeted)."""
    opts = unreal.AnimPoseEvaluationOptions()
    opts.set_editor_property("optional_skeletal_mesh", mesh)
    opts.set_editor_property("should_retarget", True)
    pe, out = unreal.AnimPoseExtensions, []
    for i, frame in enumerate(frames):
        pose = pe.get_anim_pose_at_time(clip, float(i) / CLIP_FPS, opts)
        out.append({b: pe.get_bone_pose(pose, b, unreal.AnimPoseSpaces.LOCAL) for b in frame})
    return out


def _off(fit, got):
    """(degrees, cm) a played local is off its fit."""
    return (math.degrees(unreal.Quat(*fit[1]).angular_distance(got.rotation)),
            (unreal.Vector(*fit[0]) - got.translation).length())


def _corrected(key, fit, got):
    """``key`` moved by what playing did to it: turned after it (the
    retarget's turn is), shifted (its move is)."""
    turn = unreal.Quat(*fit[1]) * got.rotation.inversed() * unreal.Quat(*key[1])
    turn.normalize()
    at = unreal.Vector(*key[0]) + unreal.Vector(*fit[0]) - got.translation
    return ((at.x, at.y, at.z), (turn.x, turn.y, turn.z, turn.w))


def settle(clip, frames):
    """Key the clip so that played on the drawn body each frame is
    ``frames``' ({bone: local}). Returns the worst (degrees, cm) left;
    raises past SETTLED_DEG / SETTLED_CM."""
    mesh = _assets().load_asset(BODY_MESH)
    keys = [dict(f) for f in frames]
    for _round in range(SETTLE_ROUNDS):
        _key(clip, keys)
        worst = (0.0, 0.0)
        for fit, key, got in zip(frames, keys, _played(clip, mesh, keys)):
            for bone in fit:
                deg, cm = _off(fit[bone], got[bone])
                worst = (max(worst[0], deg), max(worst[1], cm))
                key[bone] = _corrected(key[bone], fit[bone], got[bone])
        _log(f"{clip.get_name()} as played on {mesh.get_name()}: {worst[0]:.3f} deg, "
             f"{worst[1]:.3f} cm off the fit at worst")
        if worst[0] <= SETTLED_DEG and worst[1] <= SETTLED_CM:
            return worst
    raise RuntimeError(f"{clip.get_name()} did not settle on {mesh.get_name()}: "
                       f"{worst[0]:.2f} deg, {worst[1]:.2f} cm off the fit")


def bake(frames):
    """Key ``frames`` ([{bone: local}], one a frame) into the clip, settled
    (settle()); saved."""
    clip = _clip()
    settle(clip, frames)
    clip.set_editor_property("enable_root_motion", False)
    _assets().save_loaded_asset(clip, False)
    return clip


def build_drawn_grip(guns=GUNS):
    """Fit every gun and key the clip (all of GUNS: a frame's time is its
    place in it)."""
    rows = capture()
    frames = []
    for gun in GUNS:
        if gun not in guns:
            raise RuntimeError("the clip keys every gun of GUNS at once")
        fitted = fit_gun(gun, rows[gun], gun_solid(gun))
        frames += [fitted[f] for f in FRAMES]
    clip = bake(frames)
    _log(f"built {CLIP}: {len(frames)} frames, {len(frames[0])} bones")
    return clip
