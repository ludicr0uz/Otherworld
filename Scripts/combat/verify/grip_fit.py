"""verify.grip_fit -- the handle is in the fist: the saved GripLocation puts
each weapon's Grip part where the fingers close in its ready pose, and the
index finger at the trigger.

Mirrors grip._grip_location. Read from the saved CDO and re-measured off the
pose, so a GripLocation that was never solved (the old zero, which hung the
weapon off the wrist 8-14 cm from the fingers) or a finger layout that moved
since the build both fail here.

Distances are to a finger JOINT, which is the bone's axis and sits about a
centimetre under the skin; a part is measured as its box (a cylinder's box is
the one it fits in).
"""

import unreal

from combat.grip import (
    box_distance, fist_in_socket, placed_part, wrapping_joints,
)
from combat.weapon_models import TRIGGER_REACH_CM
from combat.weapon_specs import _weapon_specs
from combat.verify.common import cdo, check, load

# The handle's centre may sit this far off the fist's centre (the build eases
# it up to grip.SEAT_EASE_MAX_CM off, out of a joint that would stand in it).
FIST_MISS_CM = 0.5
# How far a joint may sink into the box. A round fist cannot hug a box's
# corners; measured at most 0.33 cm on the five weapons.
JOINT_SINK_CM = 0.5
# How far a wrapping joint may sit off the box: a centimetre of finger and a
# little air. Measured at most 2.9 cm; before the solve it was 9-17 cm.
JOINT_REACH_CM = 3.5
# The index's two outer joints, to the trigger guard: TRIGGER_REACH_CM
# (weapon_models.py). Measured 0.3-1.9 cm; a row whose pose rests the index
# elsewhere says how far (trigger_reach).


def grip_fit(bp, aim, parts, part, trigger=None):
    """Measurements of how `part` sits in the hand during the pose `aim`:
    miss (cm off the fist's centre), sink and reach (the deepest and the
    furthest wrapping joint), and trigger (the index to `trigger`, or None).

    The wrapping joints are the index's knuckle and all of the other three
    fingers. The index's outer joints are on the trigger, not the handle.
    """
    d = cdo(bp)
    weapon = unreal.Transform(location=d.get_editor_property("GripLocation"),
                              rotation=d.get_editor_property("GripRotation"),
                              scale=unreal.Vector(1.0, 1.0, 1.0))
    fist, fingers = fist_in_socket(aim)
    handle, into, half = placed_part(weapon, parts, part)
    index = fingers[0]
    wrap = [box_distance(into, half, j) for j in wrapping_joints(fingers)]
    on_trigger = None
    if trigger:
        _xf, into_guard, guard_half = placed_part(weapon, parts, trigger)
        on_trigger = min(box_distance(into_guard, guard_half, j) for j in index[1:])
    return dict(miss=(handle.translation - fist).length(),
                sink=-min(wrap), reach=max(wrap), trigger=on_trigger)


def fist_off(skin, pose):
    """How far (cm) the worst right finger joint of ``pose`` is, in the grip
    socket's frame, from where a carried item's fist has it
    (hold_pose.closed_fist): the pistol pose's fingers, the index
    ``skin.fist_index``'s where that is named."""
    got, pistol = fist_in_socket(pose)[1], fist_in_socket(skin.aim_pistol)[1]
    want = ([fist_in_socket(skin.fist_index)[1][0]] if skin.fist_index
            else pistol[:1]) + pistol[1:]
    return max((g - w).length() for a, b in zip(got, want) for g, w in zip(a, b))


def check_handles_in_fist(items):
    """items: (label, blueprint path, ready pose, parts, part held by,
    the trigger part or None[, how far the index may rest off it])."""
    for name, path, aim, parts, part, trigger, *reach in items:
        trigger_reach = reach[0] if reach else TRIGGER_REACH_CM
        bp = load(path)
        if not bp:
            check(f"{name}: asset exists", False)
            continue
        fit = grip_fit(bp, aim, parts, part, trigger)
        check(f"{name}: in its ready pose the {part} is in the middle of the fist",
              fit["miss"] < FIST_MISS_CM, f"{fit['miss']:.2f} cm off")
        check(f"{name}: no finger passes through the {part}",
              fit["sink"] < JOINT_SINK_CM,
              f"deepest joint {fit['sink']:.2f} cm in" if fit["sink"] > 0
              else f"every joint clear by {-fit['sink']:.2f} cm")
        check(f"{name}: the fingers are closed on the {part}",
              fit["reach"] < JOINT_REACH_CM, f"furthest joint {fit['reach']:.2f} cm off")
        if trigger:
            check(f"{name}: the index finger is at the {trigger}",
                  fit["trigger"] < trigger_reach, f"{fit['trigger']:.2f} cm off")


def run():
    check_handles_in_fist([(s["display"], s["path"], s["aim"], s["parts"],
                            "Grip", "TriggerGuard",
                            s.get("trigger_reach", TRIGGER_REACH_CM))
                           for s in _weapon_specs()])
