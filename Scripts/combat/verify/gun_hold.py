"""verify.gun_hold -- both hands are fitted to every gun's model in the hold
it is aimed in (combat/gun_hold.py), re-measured from the ready pose, the
solved grip and the model's outline; nothing here is read off a saved number
but the point itself.

Per row of weapon_specs, so a gun added later is held to it the day it has a
row. The left hand, moved to the gun's SupportPoint as the IK moves it down
the sights: its finger joints on the part the row names (`support`), none in
a part beside it, its thumb under the sight line, the wrist where the arm can
follow. The right hand, which the gun is rigid to: no joint sunk in any part
of the model, its thumb under the sight line (that its fingers close on the
Grip is verify/grip_fit.py's). The live hands: probes/probe_gun_hands.py.
"""

from combat import gun_hold, hand_seat
from combat.skin import player_skin
from combat.support_hand import SUPPORT_POINT_VAR
from combat.verify.common import cdo, check, load
from combat.weapon_models import GUN_HOLDS
from combat.weapon_specs import _weapon_specs

# A joint's axis may sit this far inside the part the hand closes on: a
# finger pressed on it (cm; measured at most 0.75, a tip on the pump).
SINK_CM = 1.0
# How far a left finger's joint may stand off that part: the hand is the
# ready pose's, moved as one piece, and a part narrower than what the pose
# cups leaves the little finger's knuckle off it (measured at most 5.02, the
# shotgun's pump, its thumb held under the barrel; 4.23 the AK's handguard; under 2 the rest).
REACH_CM = 5.25
# A left joint's axis against the parts beside the one held: on a part's
# face at most (measured 0.00, the AK's receiver behind its handguard).
BESIDE_SINK_CM = 0.25
# The right hand's joints against every part of the model: a joint's axis is
# about a centimetre under the skin, and the thumb lies along the receiver
# (measured at most 1.22 inside, the SMG's thumb).
GRIP_SINK_CM = 1.5
# The right thumb stays this far under the sight line (cm; measured 2.5 at
# least, the pistol's).
GRIP_THUMB_UNDER_CM = 2.0


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _worst(boxes, points):
    """(the part, the joint, its signed distance) of the joint deepest in any
    box of ``boxes`` ({part: box}); ``points`` is {joint: where}."""
    return min(((part, name, hand_seat.box_distance(box, p))
                for part, box in boxes.items() for name, p in points.items()),
               key=lambda found: found[2])


def check_rows():
    specs = _weapon_specs()
    names = sorted(spec["path"].rsplit("/", 1)[-1] for spec in specs)
    check("every gun's row has its line of weapon_models.GUN_HOLDS, by which a "
          "running game finds its outline and its support",
          names == sorted(GUN_HOLDS), f"{names} against {sorted(GUN_HOLDS)}")
    for spec in specs:
        outline, held = GUN_HOLDS.get(spec["path"].rsplit("/", 1)[-1], (None, None))
        check(f"{spec['display']}'s line there is its row's outline and support",
              outline is not None and outline() == spec["parts"]
              and held == spec.get("support"))
        support = spec.get("support") or {}
        named = support.get("part")
        check(f"{spec['display']}'s row names what the left hand holds down the "
              "sights: a part of its outline, or a measured box",
              "box" in support or named in {p[0] for p in spec["parts"]}, str(support))
        check(f"...and its saved {SUPPORT_POINT_VAR} is the row's, which the build "
              "measured", tuple(cdo(load(spec["path"])).get_editor_property(
                  SUPPORT_POINT_VAR).to_tuple()) == tuple(
                      float(c) for c in spec["support_point"]),
              str(spec["support_point"]))


def _check_left(skin, spec):
    name = spec["display"]
    comp, _weapon, placed = gun_hold.held(skin, spec)
    fingers, thumb = gun_hold.hand_points(skin, comp, placed)
    box = gun_hold.support_box(skin, spec, comp, placed)
    move = gun_hold.support_move(skin, spec, quiet=True)

    def moved(point):
        return tuple(p + m for p, m in zip(point, move))

    at = {joint: moved(p) for joint, p in fingers.items()}
    dist = {joint: hand_seat.box_distance(box, p) for joint, p in at.items()}
    deepest, furthest = min(dist, key=dist.get), max(dist, key=dist.get)
    on = gun_hold.support_of(spec).get("part", "support")
    check(f"{name}: down the sights the left hand is on its {on}, no finger joint "
          f"more than {SINK_CM:g} cm inside it",
          dist[deepest] > -SINK_CM, f"{deepest} {dist[deepest]:.2f} cm")
    check(f"...its fingers round it: every joint and tip within {REACH_CM:g} cm",
          dist[furthest] < REACH_CM, f"{furthest} {dist[furthest]:.2f} cm off")
    was, now = (hand_seat.misfit(box, list(fingers.values()), m)
                for m in ((0.0, 0.0, 0.0), move))
    check("...no worse a fit than where the ready pose has the hand",
          now <= was + 1e-6, f"worst joint {was:.2f} -> {now:.2f} cm off its seat")
    lo, hi = box
    xs = [p[0] for p in at.values()]
    check("...along the part, not off its end: the fingers' middle is between "
          "its ends", lo[0] < sum(xs) / len(xs) < hi[0],
          f"x {sum(xs) / len(xs):.1f} in {lo[0]:.1f} to {hi[0]:.1f}")
    beside = gun_hold.beside(spec, box)
    if beside:
        part, joint, d = _worst(beside, at)
        check(f"...and no joint more than {BESIDE_SINK_CM:g} cm in a part beside it",
              d > -BESIDE_SINK_CM,
              f"{joint} {d:.2f} cm from the {part}")
    top, line = gun_hold.ceiling(spec), gun_hold.sight_line_z(spec)
    high = max(p[2] for p in thumb) + move[2]
    check(f"...its thumb under the sight line (z {line:.1f})",
          high < top <= line, f"the thumb's top at z {high:.2f}, kept under {top:.2f}")
    shoulder, wrist, length = gun_hold.arm(skin, comp, placed)
    need = _dist(shoulder, moved(wrist))
    check("...and the wrist no further from the shoulder than the arm is long: "
          "the IK that carries the hand does not stretch it", need <= length,
          f"{need:.1f} cm of an arm of {length:.1f}")


def _check_right(skin, spec):
    name = spec["display"]
    comp, _weapon, placed = gun_hold.held(skin, spec)
    fingers, thumb = gun_hold.grip_points(skin, comp, placed)
    points = dict(fingers)
    points.update({f"thumb {i}": p for i, p in enumerate(thumb)})
    parts = {p[0]: gun_hold.part_box(spec["parts"], p[0]) for p in spec["parts"]}
    part, joint, d = _worst(parts, points)
    check(f"{name}: the right hand is on the gun, not in it: no joint more than "
          f"{GRIP_SINK_CM:g} cm inside any part of the model",
          d > -GRIP_SINK_CM, f"{joint} {d:.2f} cm from the {part}")
    line = gun_hold.sight_line_z(spec)
    high = max(p[2] for p in thumb)
    check(f"...and its thumb at least {GRIP_THUMB_UNDER_CM:g} cm under the sight "
          f"line (z {line:.1f})", high < line - GRIP_THUMB_UNDER_CM,
          f"the thumb's top at z {high:.2f}")


def check_hands():
    skin = player_skin()
    for spec in _weapon_specs():
        _check_left(skin, spec)
        _check_right(skin, spec)


def run():
    check_rows()
    check_hands()
