"""verify.shotgun_pose -- the shotgun's ready pose (combat/shotgun_pose.py):
A_AimShotgun is on the worn skeleton and is the rifle pose but for the two
thumbs, which point where the table says: the right one over the stock's
wrist, the left along the pump under the barrel's top. The grip solved in it
is the rifle pose's, and only the shotgun is held in it.
"""

import unreal

from asset_pipeline.rig_util import mesh_ref_pose
from combat.body_pose import _conj, _norm, _turn
from combat.grip import _grip_rotation, _grip_socket, fist_in_socket, part_placement
from combat.hold_pose import _shown
from combat.paths import SHOTGUN_AIM_ANIM_PATH, SHOTGUN_BP_PATH
from combat.shotgun_pose import SHOTGUN_THUMBS, THUMB_TIP_CM, thumb_lines, weapon_rotation
from combat.skin import player_skin
from combat.verify.common import cdo, check, load
from combat.weapon_models import SHOTGUN_WRIST, shotgun_outline
from combat.weapon_specs import _weapon_specs

THUMB_DIR_DOT = 0.999       # a thumb joint within ~2.5 deg of its table direction
SAME_RAD = 2e-3             # a track that is the rifle pose's, per key sampled
SAME_CM = 0.01
# A joint axis may sit this far inside the wood: a thumb pressed on it (cm).
SINK_CM = 1.0


def _sampled(clip, bone, frame):
    return unreal.AnimationLibrary.get_bone_pose_for_frame(clip, bone, frame, False)


def _fmt(v):
    return "(" + ", ".join(f"{c:.2f}" for c in v) + ")"


def check_shotgun_clip():
    skin = player_skin()
    worn, rifle, clip = load(skin.mesh), load(skin.aim_rifle), load(SHOTGUN_AIM_ANIM_PATH)
    check("A_AimShotgun exists on the worn skeleton",
          clip is not None and worn is not None
          and clip.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
          str(clip))
    if clip is None or rifle is None:
        return
    mine, theirs = clip.data_model_interface, rifle.data_model_interface
    n = theirs.get_number_of_keys()
    check("...as long as the rifle pose it is keyed off, key for key",
          mine.get_number_of_keys() == n
          and abs(clip.get_play_length() - rifle.get_play_length()) < 1e-3,
          f"{mine.get_number_of_keys()} keys, {clip.get_play_length():.3f} s against "
          f"{n}, {rifle.get_play_length():.3f} s")
    thumbs = {b.lower() for thumb in SHOTGUN_THUMBS for b in getattr(skin, thumb)}
    frames = sorted({0, n // 2, n - 1})
    off = []
    for track in sorted(str(t) for t in theirs.get_bone_track_names()):
        if track.lower() in thumbs:
            continue
        for f in frames:
            a, b = _sampled(clip, track, f), _sampled(rifle, track, f)
            if (a.rotation.angular_distance(b.rotation) > SAME_RAD
                    or (a.translation - b.translation).length() > SAME_CM):
                off.append(f"{track}@{f}")
    check("...and every track but the thumbs' is the rifle pose's "
          f"(frames {frames})", not off, str(off[:6]))
    moved = [b for b in sorted(thumbs)
             if _sampled(clip, b, 0).rotation.angular_distance(
                 _sampled(clip, b, n - 1).rotation) > SAME_RAD]
    check("...the thumbs held still through it", not moved, str(moved))


def check_shotgun_thumbs():
    skin = player_skin()
    worn, rifle, clip = load(skin.mesh), load(skin.aim_rifle), load(SHOTGUN_AIM_ANIM_PATH)
    bp = load(SHOTGUN_BP_PATH)
    if None in (worn, rifle, clip, bp):
        check("the shotgun, its pose and the worn body exist", False)
        return
    ref = mesh_ref_pose(worn)
    comp = _shown(clip, worn, ref)
    weapon = weapon_rotation(skin, comp)
    into = _conj(weapon)
    # The weapon's origin in the component: the grip socket, then GripLocation.
    _mesh_yaw, socket = _grip_socket()
    bone = str(socket.get_editor_property("bone_name"))
    in_bone = unreal.Transform(location=socket.get_editor_property("relative_location"),
                               rotation=socket.get_editor_property("relative_rotation"),
                               scale=unreal.Vector(1.0, 1.0, 1.0))
    held = unreal.MathLibrary.compose_transforms(
        unreal.MathLibrary.compose_transforms(
            unreal.Transform(location=cdo(bp).get_editor_property("GripLocation"),
                             rotation=cdo(bp).get_editor_property("GripRotation"),
                             scale=unreal.Vector(1.0, 1.0, 1.0)), in_bone),
        _component(comp, bone))
    origin = held.translation.to_tuple()

    def placed(point):
        return _turn(into, tuple(p - o for p, o in zip(point, origin)))

    at, lines = {}, {}
    for thumb, dirs in SHOTGUN_THUMBS.items():
        bones = getattr(skin, thumb)
        lines[thumb] = [_turn(into, line) for line in thumb_lines(bones, comp)]
        joints = [placed(comp[b][0]) for b in bones]
        tip = tuple(j + THUMB_TIP_CM * d for j, d in zip(joints[-1], lines[thumb][-1]))
        at[thumb] = joints + [tip]
        for b, got, want in zip(bones, lines[thumb], dirs):
            dot = sum(g * w for g, w in zip(got, _norm(want)))
            check(f"A_AimShotgun: {b} points along {want} in the weapon's frame",
                  dot > THUMB_DIR_DOT, f"{_fmt(got)}, dot {dot:.4f}")

    (lo_x, lo_y, _lo_z), (hi_x, hi_y, top) = SHOTGUN_WRIST
    _base, mid, end, tip = at["grip_thumb"]
    check("the grip thumb's middle joint is over the top of the stock's wrist",
          lo_x <= mid[0] <= hi_x and lo_y <= mid[1] <= hi_y and mid[2] > top - SINK_CM,
          f"{_fmt(mid)}; the wrist's top is z {top:g}")
    check("...its last joint down the wrist's left side, and the tip below it",
          end[1] < lo_y and end[2] < top and tip[2] < end[2],
          f"last {_fmt(end)}, tip {_fmt(tip)}")
    centre, _rot, half = part_placement(shotgun_outline(), "Barrel")
    barrel_top = centre.z + half.z
    line_z = min(cdo(bp).get_editor_property("SightAim").z,
                 cdo(bp).get_editor_property("SightOffset").z)
    high = max(p[2] for p in at["support_thumb"][1:])
    check(f"the support thumb is under the barrel's top (z {barrel_top:g}), so "
          f"under the sight line (z {line_z:.2f})",
          high < barrel_top < line_z,
          ", ".join(_fmt(p) for p in at["support_thumb"][1:]))


def _component(comp, bone):
    loc, quat = comp[bone][0], comp[bone][1]
    return unreal.Transform(location=unreal.Vector(*loc),
                            rotation=unreal.Quat(*quat).rotator(),
                            scale=unreal.Vector(1.0, 1.0, 1.0))


def check_grip_unchanged():
    skin = player_skin()
    if load(SHOTGUN_AIM_ANIM_PATH) is None:
        return
    a, b = _grip_rotation(SHOTGUN_AIM_ANIM_PATH), _grip_rotation(skin.aim_rifle)
    check("the grip solved in A_AimShotgun is the rifle pose's: the hand is "
          "the same hand",
          a.quaternion().angular_distance(b.quaternion()) < SAME_RAD, f"{a} against {b}")
    fa, fb = fist_in_socket(SHOTGUN_AIM_ANIM_PATH)[0], fist_in_socket(skin.aim_rifle)[0]
    check("...and so is the fist the stock is seated in",
          (fa - fb).length() < 0.05, f"{(fa - fb).length():.3f} cm apart")
    held = [s["display"] for s in _weapon_specs() if s["aim"] == SHOTGUN_AIM_ANIM_PATH]
    check("only the shotgun is held in it: the rifle and the sniper keep the "
          "rifle pose's thumbs", held == ["Shotgun"], str(held))


def run():
    check_shotgun_clip()
    check_shotgun_thumbs()
    check_grip_unchanged()
