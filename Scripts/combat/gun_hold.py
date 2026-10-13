"""Both hands fitted to a gun's model in its ready pose (the hold down the
sights), for every gun of weapon_specs: where each hand's joints are in the
weapon's frame, and the left hand's point moved onto the part it holds.

WHAT IS FITTED
--------------
The right hand is fitted by the grip: grip.py seats the gun's "Grip" part in
the fist, and the gun is rigid to that hand. The left hand is the ready
clip's, made for some other gun: under an AK the rifle pose's hand hung 2 to
7 cm below the handguard with a knuckle in the magazine, and the pistol
pose's left fingers lay inside the right hand's. Down the sights the left
wrist is held by an IK on a point in the right hand's space, each gun's own
(support_hand.py, BP_WeaponItem.SupportPoint). That point is the pose's
(support_hand.support_at) moved by support_move(): the hand, as one rigid
piece, brought to where its fingers' joints fit the part the row names
(hand_seat.seat), with

  - the thumb under a ceiling: the sight line, or the top of a part the row
    names (the shotgun's barrel);
  - no joint in a part beside the one held (the AK's magazine);
  - the wrist within the arm's reach: the IK does not stretch.

Only the place moves. The hand's turn and its fingers are the clip's.

A NEW GUN
---------
Its row of weapon_specs carries `support` (weapon_models.<GUN>_SUPPORT):

    dict(part="Handguard")              a box of its outline
    dict(box=((lo), (hi)))              a box measured off the mesh
    dict(part="Pump", under="Barrel")   ...the thumb under that part's top
    dict(part="Grip", fist=True)        a pistol: the left hand closes over
                                        the right hand's fingers on the grip

A row without one stops the build here (support_of). verify/gun_hold.py then
holds both hands of every row to its model; probes/probe_gun_hands.py reads
the live hands down the sights.
"""

from asset_pipeline.rig_util import mesh_ref_pose
from combat import hand_seat
from combat.body_pose import _conj, _mul, _norm, _turn
from combat.grip import _grip_socket, part_placement
from combat.hold_pose import _q, _shown
from combat.log import _log
from combat.support_hand import support_at
from uebp.graph import _assets

# The last joint to the thumb's or the finger's tip (cm), for the seat and
# the checks: there is no bone.
THUMB_TIP_CM = 3.0
FINGER_TIP_CM = 2.5
# With a part named to keep the thumb under, the thumb starts this far under
# its top before the seat's descent, which never crosses
# hand_seat.THUMB_CLEAR_CM.
THUMB_START_CM = 0.5
# The seat leaves the arm this much short of straight (cm). The IK does not
# stretch the arm, so a point further off is never reached: the pump-action's
# first seat was 3.7 cm past the arm's length and the live wrist stopped 3.7
# cm short of it (probes/probe_gun_hands.py measures the live wrist against
# the point; within the arm it is 0.1 cm off).
ARM_SLACK_CM = 0.25


def support_of(spec):
    """The row's `support`, or an error that says what a gun's row needs."""
    support = spec.get("support")
    if not support or not ("part" in support or "box" in support):
        raise RuntimeError(
            f"{spec['display']}: its row of weapon_specs has no `support` (the part "
            "of the model the left hand holds down the sights): add one, as "
            "weapon_models.RIFLE_SUPPORT (combat/gun_hold.py, \"A NEW GUN\")")
    return support


def part_box(parts, name):
    """An outline part as a box ((lo), (hi)) in the weapon's frame: the box
    the part fits in (a cylinder lies along the barrel)."""
    centre, rot, half = part_placement(parts, name)
    h = (half.z, half.x, half.y) if abs(rot.pitch) > 45.0 else (half.x, half.y, half.z)
    c = (centre.x, centre.y, centre.z)
    return (tuple(a - b for a, b in zip(c, h)), tuple(a + b for a, b in zip(c, h)))


def weapon_rotation(spec, comp):
    """The weapon's frame in the component's, a quat, against a component pose
    ``comp`` ({bone: (location, quat, ...)}): the grip socket's turn, then
    GripRotation."""
    _mesh_yaw, socket = _grip_socket()
    bone = str(socket.get_editor_property("bone_name"))
    in_bone = _q(socket.get_editor_property("relative_rotation").quaternion())
    grip = _q(spec["grip_rot"].quaternion())
    return _mul(_mul(comp[bone][1], in_bone), grip)


def weapon_origin(comp, grip_loc):
    """Where the weapon's own origin is in the component, against a component
    pose ``comp``: the grip socket, then GripLocation (the weapon is attached
    at the socket and moved by it, in the socket's frame)."""
    _mesh_yaw, socket = _grip_socket()
    bone = str(socket.get_editor_property("bone_name"))
    in_bone = _q(socket.get_editor_property("relative_rotation").quaternion())
    at = socket.get_editor_property("relative_location")
    loc = tuple(a + g for a, g in zip((at.x, at.y, at.z), _turn(in_bone, grip_loc)))
    return tuple(c + o for c, o in zip(comp[bone][0], _turn(comp[bone][1], loc)))


def thumb_lines(bones, comp):
    """[each joint's line to the next, unit, component space] for one thumb's
    or finger's ``bones``, against a component pose ``comp``. The last
    joint's is its bone's long axis: the axis its parent's line runs down.
    Pure."""
    lines = [_norm(tuple(c - p for c, p in zip(comp[child][0], comp[bone][0])))
             for bone, child in zip(bones, bones[1:])]
    axis = _turn(_conj(comp[bones[-2]][1]), lines[-1])
    return lines + [_turn(comp[bones[-1]][1], axis)]


def finger_points(bones, comp, tip_cm):
    """Where a finger's (or thumb's) joints and tip are in ``comp``:
    component space. Pure."""
    at = [comp[b][0] for b in bones]
    tip = thumb_lines(bones, comp)[-1]
    return at + [tuple(p + tip_cm * d for p, d in zip(at[-1], tip))]


def held(skin, spec):
    """``spec``'s ready pose with the gun in its hand: (the pose in the
    component, the weapon's quat there, a function placing a component point
    in the weapon's frame). Against the solved grip (the row's grip_rot and
    grip_loc): a Grip somebody placed by eye does not move the left hand."""
    mesh = _assets().load_asset(skin.mesh)
    clip = _assets().load_asset(spec["aim"])
    if mesh is None or clip is None:
        raise RuntimeError(f"could not load {skin.mesh} or {spec['aim']}")
    comp = _shown(clip, mesh, mesh_ref_pose(mesh))
    weapon = weapon_rotation(spec, comp)
    origin = weapon_origin(comp, spec["grip_loc"])
    into = _conj(weapon)

    def placed(point):
        return _turn(into, tuple(p - o for p, o in zip(point, origin)))

    return comp, weapon, placed


def _hand(fingers, thumb, comp, placed):
    joints = {}
    for bones in fingers:
        at = [placed(p) for p in finger_points(bones, comp, FINGER_TIP_CM)]
        joints.update(zip(list(bones) + [bones[-1] + " tip"], at))
    return joints, [placed(p) for p in finger_points(thumb, comp, THUMB_TIP_CM)[1:]]


def hand_points(skin, comp, placed):
    """({name: where} for every joint and tip of the left hand's four
    fingers, [the thumb's joints past its first, and its tip]), in the
    weapon's frame."""
    return _hand(skin.support_fingers, skin.support_thumb, comp, placed)


def grip_points(skin, comp, placed):
    """The same for the right hand: the hand the gun is rigid to."""
    return _hand(skin.grip_fingers, skin.grip_thumb, comp, placed)


def sight_line_z(spec):
    """The lowest z of the gun's sight line between its sights, in the
    weapon's frame: what no thumb may stand above."""
    return min(spec["sight_rear"][2], spec["sight_front"][2])


def ceiling(spec):
    """The z the left thumb stays under: the top of the part the row names
    (`under`), else the sight line."""
    under = support_of(spec).get("under")
    return part_box(spec["parts"], under)[1][2] if under else sight_line_z(spec)


def support_box(skin, spec, comp, placed):
    """The box the left hand closes on, in the weapon's frame: the row's part
    or its measured box; with `fist`, that box grown to hold the right hand's
    three wrapping fingers closed on it, skin and all (a pistol's hold: the
    left hand closes over the right)."""
    support = support_of(spec)
    box = support["box"] if "box" in support else part_box(spec["parts"], support["part"])
    if not support.get("fist"):
        return box
    fingers, _thumb = grip_points(skin, comp, placed)
    wrapping = {b for finger in skin.grip_fingers[1:] for b in finger}
    return fist_box(box, [p for name, p in fingers.items()
                          if name.replace(" tip", "") in wrapping])


def fist_box(box, wrapping):
    """``box`` grown to hold ``wrapping``, the joints and tips of the right
    hand's middle, ring and little fingers, with the skin on them. Pure."""
    return hand_seat.union(box, hand_seat.grown(hand_seat.bounding(wrapping),
                                                hand_seat.SEAT_OFF_CM))


def beside(spec, box):
    """{part: its box} for every part of the outline that shares no volume
    with ``box``: what the left hand must stay out of."""
    out = {part[0]: part_box(spec["parts"], part[0]) for part in spec["parts"]}
    return {name: b for name, b in out.items() if not hand_seat.overlaps(b, box)}


def arm(skin, comp, placed):
    """(the left shoulder, the left wrist, both in the weapon's frame, the
    arm's length shoulder to wrist with the elbow straight)."""
    bones = skin.pose_bones
    shoulder, elbow, wrist = (comp[bones[b]][0]
                              for b in ("upperarm_l", "forearm_l", "hand_l"))
    length = sum(sum((a - b) ** 2 for a, b in zip(p, q)) ** 0.5
                 for p, q in ((shoulder, elbow), (elbow, wrist)))
    return placed(shoulder), placed(wrist), length


def support_move(skin, spec, quiet=False):
    """How far the left hand is moved off the ready pose's place to sit on
    the gun, (x, y, z) cm in the weapon's frame."""
    comp, _weapon, placed = held(skin, spec)
    fingers, thumb = hand_points(skin, comp, placed)
    box = support_box(skin, spec, comp, placed)
    top = ceiling(spec)
    # A part to keep the thumb under: straight down to it first, so the
    # descent starts from a hand that is allowed.
    drop = (min(0.0, top - THUMB_START_CM - max(p[2] for p in thumb))
            if support_of(spec).get("under") else 0.0)
    joints = [(x, y, z + drop) for x, y, z in fingers.values()]
    shoulder, wrist, length = arm(skin, comp, placed)
    seat = hand_seat.seat(
        box, joints, [(x, y, z + drop) for x, y, z in thumb], top,
        obstacles=list(beside(spec, box).values()),
        reach=(shoulder, (wrist[0], wrist[1], wrist[2] + drop), length - ARM_SLACK_CM))
    move = (seat[0], seat[1], seat[2] + drop)
    if not quiet:
        was, now = (hand_seat.misfit(box, list(fingers.values()), m)
                    for m in ((0.0, 0.0, 0.0), move))
        _log(f"{spec['display']}: the left hand's point moved ({move[0]:.1f}, "
             f"{move[1]:.1f}, {move[2]:.1f}) cm in the weapon's frame onto its "
             f"{support_of(spec).get('part', 'support')}: its worst joint {was:.2f} -> "
             f"{now:.2f} cm from riding {hand_seat.SEAT_OFF_CM:g} cm off it")
    return move


def support_point(skin, spec, quiet=False):
    """The gun's SupportPoint: where its ready pose has the left hand
    (support_at), moved by support_move(), in the right hand's bone space."""
    comp, weapon, _placed = held(skin, spec)
    move = _turn(weapon, support_move(skin, spec, quiet))
    in_hand = _turn(_conj(comp[skin.pose_bones["hand_r"]][1]), move)
    return tuple(round(a + m, 3) for a, m in zip(support_at(skin, spec["aim"]), in_hand))
