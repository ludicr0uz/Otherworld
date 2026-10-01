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

from combat.grip import fist_in_socket, part_placement
from combat.weapon_specs import _weapon_specs
from combat.verify.common import cdo, check, load

# The handle's centre may sit this far off the fist's centre.
FIST_MISS_CM = 0.5
# How far a joint may sink into the box. A round fist cannot hug a box's
# corners; measured at most 0.33 cm on the five weapons.
JOINT_SINK_CM = 0.5
# How far a wrapping joint may sit off the box: a centimetre of finger and a
# little air. Measured at most 2.9 cm; before the solve it was 9-17 cm.
JOINT_REACH_CM = 3.5
# The index's two outer joints, to the trigger guard. Measured 0.5-1.9 cm.
TRIGGER_REACH_CM = 2.5


def _placed(weapon, parts, name):
    """(Transform into the part's own frame, its half extents) in the socket."""
    centre, rot, half = part_placement(parts, name)
    xf = unreal.MathLibrary.compose_transforms(
        unreal.Transform(location=centre, rotation=rot,
                         scale=unreal.Vector(1.0, 1.0, 1.0)), weapon)
    return xf, unreal.MathLibrary.invert_transform(xf), half


def _box_distance(into, half, point):
    """Signed distance from a point to a box: negative inside."""
    p = unreal.MathLibrary.transform_location(into, point)
    d = [abs(v) - h for v, h in zip(p.to_tuple(), half.to_tuple())]
    out = sum(max(x, 0.0) ** 2 for x in d) ** 0.5
    return out if out > 0.0 else max(d)


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
    handle, into, half = _placed(weapon, parts, part)
    index, rest = fingers[0], fingers[1:]
    wrap = [_box_distance(into, half, j) for j in [index[0]] + [j for f in rest for j in f]]
    on_trigger = None
    if trigger:
        _xf, into_guard, guard_half = _placed(weapon, parts, trigger)
        on_trigger = min(_box_distance(into_guard, guard_half, j) for j in index[1:])
    return dict(miss=(handle.translation - fist).length(),
                sink=-min(wrap), reach=max(wrap), trigger=on_trigger)


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
