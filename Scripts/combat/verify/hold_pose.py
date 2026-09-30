"""verify.hold_pose -- the hold poses (combat/hold_pose.py): A_HoldItem and
A_HoldKnife are on the worn skeleton, their arms point where the tables say,
the hands land where a carry and a fighting stance put them, the fist is the
pistol pose's, and the knife and the food are held in them (guns are not).
"""

import math

import unreal

from combat.grip import fist_in_socket
from combat.hold_pose import CHILD, HOLD_ITEM_DIRS, HOLD_KNIFE_DIRS, HOLD_POSES
from combat.knife import knife_outline
from combat.paths import HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, KNIFE_BP_PATH
from combat.skin import player_skin
from combat.verify.common import cdo, check, load
from combat.verify.grip_fit import check_handles_in_fist
from combat.weapon_specs import _weapon_specs

# Where the hands must land, cm, in the body frame (+Y forward, +Z up),
# relative to the hips bone.
CARRY_REACH_CM = 15.0       # the carried item is out in front of the hips
CARRY_HEIGHT_CM = (-25.0, 35.0)   # between the thigh and the ribs
KNIFE_REACH_CM = 20.0       # the knife is held out before the body
KNIFE_OVER_CARRY_CM = 15.0  # and higher than a carried item
ARM_DIR_DOT = 0.99          # an arm within ~8 deg of its table direction
FIST_SAME_CM = 0.5          # the fist, in the grip socket's frame


def _pose(anim):
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
        anim, 0.0, unreal.AnimPoseEvaluationOptions())

    def at(bone):
        t = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)
        return (t.translation.x, t.translation.y, t.translation.z)
    return at


def _sub(a, b):
    return tuple(p - q for p, q in zip(a, b))


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def check_hold_clips():
    skin = player_skin()
    worn = load(skin.mesh)
    for path, dirs in HOLD_POSES:
        name = path.rsplit("/", 1)[-1]
        clip = load(path)
        check(f"{name} exists on the worn skeleton",
              clip is not None and worn is not None
              and clip.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
              str(clip))
        if clip is None:
            continue
        at = _pose(clip)
        bad = []
        for role, want in dirs.items():
            kind, side = role.rsplit("_", 1)
            b = skin.pose_bones
            got = _unit(_sub(at(b[f"{CHILD[kind]}_{side}"]), at(b[role])))
            dot = sum(p * q for p, q in zip(got, _unit(want)))
            if dot < ARM_DIR_DOT:
                bad.append(f"{role} {dot:.3f}")
        check(f"...its arms point where the table says", not bad, str(bad))


def check_hands_placed():
    skin = player_skin()
    b = skin.pose_bones
    carry, knife = load(HOLD_ITEM_ANIM_PATH), load(HOLD_KNIFE_ANIM_PATH)
    if carry is None or knife is None:
        check("both hold poses load", False)
        return
    c, k = _pose(carry), _pose(knife)
    hand_c = _sub(c(b["hand_r"]), c(b["hips"]))
    hand_k = _sub(k(b["hand_r"]), k(b["hips"]))
    check("A_HoldItem carries the item in front of the body at the waist",
          hand_c[1] > CARRY_REACH_CM and CARRY_HEIGHT_CM[0] < hand_c[2] < CARRY_HEIGHT_CM[1],
          f"right hand {tuple(round(v, 1) for v in hand_c)} from the hips")
    check("...with the left arm left hanging",
          c(b["hand_l"])[2] < c(b["forearm_l"])[2] < c(b["upperarm_l"])[2])
    check("A_HoldKnife holds the knife out, higher than a carried item",
          hand_k[1] > KNIFE_REACH_CM and hand_k[2] > hand_c[2] + KNIFE_OVER_CARRY_CM,
          f"right hand {tuple(round(v, 1) for v in hand_k)} from the hips")
    check("...with the left fist up as a guard",
          k(b["hand_l"])[2] > k(b["forearm_l"])[2]
          and k(b["hand_l"])[1] > k(b["hips"])[1] + KNIFE_REACH_CM,
          f"left hand {tuple(round(v, 1) for v in _sub(k(b['hand_l']), k(b['hips'])))}")
    fist = fist_in_socket(skin.aim_pistol)[0]
    off = {path.rsplit("/", 1)[-1]: round((fist_in_socket(path)[0] - fist).length(), 2)
           for path in (HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH)}
    check("...and both close the right hand as the pistol pose does (fist within 0.5 cm)",
          all(d < FIST_SAME_CM for d in off.values()), str(off))


def check_held_in_hold_poses():
    item, knife = load(HOLD_ITEM_ANIM_PATH), load(HOLD_KNIFE_ANIM_PATH)
    d = cdo(load(KNIFE_BP_PATH))
    check("the knife's ready pose is A_HoldKnife",
          d is not None and knife is not None and d.get_editor_property("AimPose") == knife,
          str(d.get_editor_property("AimPose") if d else None))
    guns = [s["display"] for s in _weapon_specs()
            if cdo(load(s["path"])).get_editor_property("AimPose") in (item, knife)]
    check("no gun is held in a hold pose", not guns, str(guns))
    check_handles_in_fist([("Knife", KNIFE_BP_PATH, HOLD_KNIFE_ANIM_PATH,
                            knife_outline(), "Grip", None)])


def run():
    check_hold_clips()
    check_hands_placed()
    check_held_in_hold_poses()
