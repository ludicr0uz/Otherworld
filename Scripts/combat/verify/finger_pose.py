"""verify.finger_pose -- a fitted gun's fingers are on its model in the clip
it is held in (combat/finger_pose.py): re-measured from the SAVED clip, the
solved grip and the model's outline, and held to the fit's own arithmetic.

Per name of weapon_models.GUN_FINGERS, so a gun added there is held to it
that day: its clip is its row's pose but for the fingers, its item is held in
it, every finger the fit bent lies on the model (points on it, none pressed
in, none left in the air) and nearer it than the pose had it, a finger the
fit left is the pose's, and the left thumb is laid on the part under its
ceiling. The live fingers: probes/probe_gun_hands.py.
"""

import unreal

from combat import finger_fit, finger_pose, gun_hold
from combat.skin import player_skin
from combat.verify.common import cdo, check, load
from combat.weapon_models import GUN_FINGERS
from combat.weapon_specs import _weapon_specs

# A riding point of a fitted finger is no nearer the model than this (cm;
# its axis rides SKIN_CM off: measured at least 0.43, the sniper's left ring)
# and none is further than FAR_CM (measured at most 1.44, its right ring).
NEAR_CM = 0.3
FAR_CM = 1.6
# The saved clip against the fit's arithmetic (cm).
KEYED_CM = 0.05
# The left thumb's nearest point to the part (cm; measured 0.81 and 0.82).
THUMB_CM = 1.0
# How many of a gun's seven bent fingers must be laid on it (measured 6 on
# the AK, whose left index is past the front of its handguard; 7 on the Val).
FITTED = 5
# Bones that are not fingers, read on both clips' first and last frame.
_BODY = ("hand_r", "hand_l", "lowerarm_r", "lowerarm_l", "upperarm_r", "spine_05", "head")


def _same(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w


def _worst(near, far):
    """How far a finger's worst riding point is from a skin off the model."""
    return max(abs(near - finger_fit.SKIN_CM), abs(far - finger_fit.SKIN_CM))


def check_rows():
    specs = {s["path"].rsplit("/", 1)[-1]: s for s in _weapon_specs()}
    check("every name of weapon_models.GUN_FINGERS is a gun's row, held in both hands",
          all(n in specs and specs[n]["two_handed"] for n in GUN_FINGERS),
          f"{GUN_FINGERS} against {sorted(specs)}")
    for name, spec in sorted(specs.items()):
        fitted = name in GUN_FINGERS
        check(f"{spec['display']}: held in " + ("a clip of its own, its pose with its "
              "fingers on this gun" if fitted else "its row's pose as shipped"),
              spec["aim"] == (finger_pose.clip_for(name) if fitted else spec["pose"]),
              f"{spec['aim']} off {spec['pose']}")


def _check_clip(skin, spec):
    name, clip, pose = spec["display"], load(spec["aim"]), load(spec["pose"])
    check(f"{name}: its clip {spec['aim'].rsplit('/', 1)[-1]} is saved", clip is not None)
    if clip is None or pose is None:
        return False
    check("...on the worn skeleton, as long as the pose it is, and in place",
          clip.get_skeleton() == load(skin.mesh).skeleton
          and abs(clip.get_play_length() - pose.get_play_length()) < 1e-4
          and clip.get_editor_property("number_of_sampled_keys")
          == pose.get_editor_property("number_of_sampled_keys")
          and not clip.get_editor_property("enable_root_motion"),
          f"{clip.get_play_length():.3f} s against {pose.get_play_length():.3f}")
    off = []
    for t in (0.0, pose.get_play_length()):
        a = unreal.AnimationLibrary.get_bone_poses_for_time(clip, list(_BODY), t, False)
        b = unreal.AnimationLibrary.get_bone_poses_for_time(pose, list(_BODY), t, False)
        off += [bone for bone, x, y in zip(_BODY, a, b)
                if not (_same(x.translation.to_tuple(), y.translation.to_tuple())
                        and abs(_dot(x.rotation, y.rotation)) > 1.0 - 1e-6)]
    check("...and it is that pose but for the fingers: the hands, the arms, the "
          "spine and the head as the pose keys them, first frame and last",
          not off, str(off))
    held = cdo(load(spec["path"])).get_editor_property("AimPose")
    check("...and the gun's item is held in it", held == clip, str(held))
    return True


def _check_fingers(skin, spec):
    name = spec["display"]
    _turns, bends = finger_pose.fit(skin, spec)
    was, now = finger_pose.measure(skin, spec), finger_pose.measure(skin, spec, spec["aim"])
    want = finger_pose.expected(skin, spec)
    bent = [label for label, bend in bends.items() if bend and label != "left thumb"]
    check(f"{name}: at least {FITTED} of its seven bent fingers are laid on the model",
          len(bent) >= FITTED, str(sorted(bent)))
    for label in sorted(bends):
        on, near, far = now[label]
        check(f"{name}: the saved clip's {label} is where the fit puts it",
              on == want[label][0] and _same(now[label][1:], want[label][1:], KEYED_CM),
              f"{now[label]} against {want[label]}")
        if label == "left thumb":
            continue
        if not bends[label]:
            check("...which leaves it the pose's (it cannot be laid on the model)",
                  _same(now[label], was[label], KEYED_CM), f"{now[label]} was {was[label]}")
            continue
        check(f"...on the model: at least {finger_fit.ON_POINTS} of its points a "
              f"skin off it, none nearer than {NEAR_CM:g} cm, none further than {FAR_CM:g}",
              on >= finger_fit.ON_POINTS and near >= NEAR_CM and far <= FAR_CM,
              f"{on} on, {near:.2f} to {far:.2f} cm")
        check("...and better laid than the pose had it: its worst point nearer a "
              "skin off the model than the pose's worst was (in it or in the air)",
              _worst(near, far) <= _worst(*was[label][1:]) + KEYED_CM,
              f"{near:.2f} to {far:.2f} cm, {was[label][1]:.2f} to {was[label][2]:.2f} before")
    _on, near, _far = now["left thumb"]
    comp, _weapon, placed = gun_hold.held(skin, spec, spec["aim"])
    _fingers, (_bones, thumb, _boxes) = finger_pose.hands(skin, spec, comp, placed)
    top, ceiling = max(p[2] for p in thumb[1:]), gun_hold.ceiling(spec)
    check(f"{name}: the left thumb is laid against the part, within {THUMB_CM:g} cm "
          "of it and not in it, under its ceiling",
          NEAR_CM <= near <= THUMB_CM and top < ceiling,
          f"{near:.2f} cm off (the pose's {was['left thumb'][1]:.2f}), its top at "
          f"z {top:.2f} under {ceiling:.2f}")


def check_clips():
    skin = player_skin()
    for spec in _weapon_specs():
        if finger_pose.fitted(spec) and _check_clip(skin, spec):
            _check_fingers(skin, spec)


def run():
    check_rows()
    check_clips()
