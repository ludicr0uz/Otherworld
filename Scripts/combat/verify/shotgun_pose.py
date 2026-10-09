"""verify.shotgun_pose -- how the shotgun is held (combat/shotgun_hold.py):
in the rifle's ready pose, a shipped clip (no pose keyed for it is left), its
grip solved in that pose, and the left hand's point moved onto the pump: down
the sights the thumb is under the barrel's top, so under the sight line, and
the fingers are round the wood, not in it.
"""

from asset_pipeline import lyra_paths as LYRA
from combat import item_vars as IV
from combat import pump_seat
from combat.grip import _grip_rotation
from combat.paths import RETIRED_SHOTGUN_AIM_ANIM_PATH, SHOTGUN_BP_PATH
from combat.shotgun_hold import (
    THUMB_TIP_CM, barrel_top, finger_points, hand_points, held, support_move,
    support_point,
)
from combat.skin import player_skin
from combat.support_hand import SUPPORT_POINT_VAR, support_at
from combat.verify.common import cdo, check, load
from combat.weapon_models import SHOTGUN_PUMP
from combat.weapon_specs import _weapon_specs, two_handed_poses
from uebp.graph import _assets

SAME_RAD = 2e-3
# A joint axis may sit this far inside the wood: a finger pressed on it (cm).
SINK_CM = 1.0
# How far a left finger's joint may stand off the pump. The hand is the rifle
# pose's, shaped for a deeper handguard, moved as one piece: measured at most
# 3.8 (the pose keyed until C3 closed every joint within 1.6; unmoved, the
# rifle pose's are up to 4.1 off with one 1.3 inside).
PUMP_REACH_CM = 4.25
# The grip thumb lies forward along the top of the stock's wrist: at least
# this far under the sight line (cm; measured 4.1).
GRIP_THUMB_UNDER_CM = 3.0
# The hand is moved at least this far to be seated (cm; measured 6.5).
MOVED_CM = 2.0


def _fmt(v):
    return "(" + ", ".join(f"{c:.2f}" for c in v) + ")"


def pump_distance(point):
    """Signed distance from a point in the weapon's frame to the pump's box
    (SHOTGUN_PUMP): negative inside."""
    return pump_seat.box_distance(SHOTGUN_PUMP, point)


def check_shotgun_clip():
    skin = player_skin()
    worn, rifle, bp = load(skin.mesh), load(skin.aim_rifle), load(SHOTGUN_BP_PATH)
    if None in (worn, rifle, bp):
        check("the shotgun, the rifle pose and the worn body exist", False)
        return
    pose = cdo(bp).get_editor_property(IV.AimPose)
    check("the shotgun is held in the rifle's ready pose, on the worn skeleton",
          pose == rifle
          and rifle.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
          str(pose))
    check("no pose keyed for it is left: A_AimShotgun is gone",
          not _assets().does_asset_exist(RETIRED_SHOTGUN_AIM_ANIM_PATH))
    if skin.gas:
        source = load(LYRA.AIM_RIFLE)
        check("...and that pose is a shipped clip: Lyra's MM_Rifle_Idle_ADS, as "
              "long as Lyra's and key for key",
              skin.aim_rifle == LYRA.uefn_clip(LYRA.AIM_RIFLE) and source is not None
              and abs(rifle.get_play_length() - source.get_play_length()) < 1e-3
              and rifle.data_model_interface.get_number_of_keys()
              == source.data_model_interface.get_number_of_keys(),
              f"{skin.aim_rifle}, {rifle.get_play_length():.3f} s")
    held_in = sorted(s["display"] for s in _weapon_specs()
                     if s["aim"] in two_handed_poses(skin))
    check("the three long guns are held in it, in both hands",
          held_in == ["Rifle", "Shotgun", "Sniper"], str(held_in))


def check_grip():
    skin = player_skin()
    bp = load(SHOTGUN_BP_PATH)
    if bp is None or load(skin.aim_rifle) is None:
        return
    got, want = cdo(bp).get_editor_property("GripRotation"), _grip_rotation(skin.aim_rifle)
    check("the shotgun's grip is solved in the rifle pose: the hand is the same hand",
          got.quaternion().angular_distance(want.quaternion()) < SAME_RAD,
          f"{got} against {want}")


def check_support_point():
    skin = player_skin()
    bp = load(SHOTGUN_BP_PATH)
    if bp is None or load(skin.aim_rifle) is None:
        return
    got = cdo(bp).get_editor_property(SUPPORT_POINT_VAR).to_tuple()
    want, pose = support_point(skin, quiet=True), support_at(skin, skin.aim_rifle)
    check(f"the shotgun's {SUPPORT_POINT_VAR} is the rifle pose's moved onto the "
          "pump, re-measured",
          max(abs(g - w) for g, w in zip(got, want)) < 0.01, f"{got} against {want}")
    moved = sum((g - p) ** 2 for g, p in zip(got, pose)) ** 0.5
    check(f"...at least {MOVED_CM:g} cm from where the pose has the hand",
          moved > MOVED_CM, f"{moved:.2f} cm from {pose}")
    for spec in _weapon_specs():
        if spec["path"] == SHOTGUN_BP_PATH or spec["aim"] != skin.aim_rifle:
            continue
        theirs = cdo(load(spec["path"])).get_editor_property(SUPPORT_POINT_VAR).to_tuple()
        check(f"...and the {spec['display']} keeps the pose's own point",
              max(abs(t - p) for t, p in zip(theirs, pose)) < 0.01, str(theirs))


def _seated():
    """(skin, the blueprint, the left fingers' joints and the thumb's as the
    IK holds them down the sights, a function placing a component point in
    the weapon's frame), or None."""
    skin = player_skin()
    bp = load(SHOTGUN_BP_PATH)
    if bp is None or load(skin.aim_rifle) is None or load(skin.mesh) is None:
        check("the shotgun, the rifle pose and the worn body exist", False)
        return None
    comp, _weapon, placed = held(skin)
    fingers, thumb = hand_points(skin, comp, placed)
    move = support_move(skin, quiet=True)

    def moved(point):
        return tuple(p + m for p, m in zip(point, move))

    return (skin, bp, {name: moved(p) for name, p in fingers.items()},
            [moved(p) for p in thumb], (comp, placed))


def check_shotgun_thumbs():
    found = _seated()
    if found is None:
        return
    skin, bp, _fingers, thumb, (comp, placed) = found
    top = barrel_top()
    line_z = min(cdo(bp).get_editor_property("SightAim").z,
                 cdo(bp).get_editor_property("SightOffset").z)
    high = max(p[2] for p in thumb)
    check(f"down the sights the support thumb is under the barrel's top (z {top:g}), "
          f"so under the sight line (z {line_z:.2f})",
          high < top < line_z, ", ".join(_fmt(p) for p in thumb))
    grip = [placed(p) for p in finger_points(skin.grip_thumb, comp, THUMB_TIP_CM)[1:]]
    check(f"the grip thumb is at least {GRIP_THUMB_UNDER_CM:g} cm under the sight line",
          max(p[2] for p in grip) < line_z - GRIP_THUMB_UNDER_CM,
          ", ".join(_fmt(p) for p in grip))


def check_support_fingers():
    found = _seated()
    if found is None:
        return
    _skin, _bp, joints, _thumb, _pose = found
    dist = {name: pump_distance(p) for name, p in joints.items()}
    deepest, furthest = min(dist, key=dist.get), max(dist, key=dist.get)
    check("down the sights the left hand is under the pump, not in it: no finger "
          f"joint is more than {SINK_CM:g} cm inside the wood",
          dist[deepest] > -SINK_CM, f"{deepest} {dist[deepest]:.2f} cm")
    check(f"...and its fingers are round it: every joint and tip within "
          f"{PUMP_REACH_CM:g} cm of the wood",
          dist[furthest] < PUMP_REACH_CM, f"{furthest} {dist[furthest]:.2f} cm off")
    lo, hi = SHOTGUN_PUMP
    ahead = [name for name, p in joints.items() if not lo[0] - PUMP_REACH_CM < p[0] < hi[0]]
    check("...along the pump's length, none past its front end", not ahead, str(ahead))


def run():
    check_shotgun_clip()
    check_grip()
    check_support_point()
    check_shotgun_thumbs()
    check_support_fingers()
