"""The shotgun's hold: the rifle's ready pose, a shipped clip, with the left
hand's point moved onto the pump. No pose is keyed here (C3): this module
works out one offset, the shotgun's SupportPoint.

WHY THE SHOTGUN NEEDS ONE
-------------------------
The rifle ready pose (PlayerSkin.aim_rifle, Lyra's MM_Rifle_Idle_ADS) holds a
pistol grip under a tall receiver: the left palm stands on edge beside a deep
handguard, its thumb up the side. The AK's and the Val's sight lines run 14 cm
above the grip, so the thumb is nowhere near the picture. The shotgun
(Quaternius Shotgun_3) has a straight stock, a sight line that skims the
receiver 6.4 cm above the grip, and a 5 cm bar of a pump where the middle of
that handguard would be. In the rifle's pose, measured in the weapon's frame:

  - the left thumb's tip is 3.7 cm ABOVE the sight line, 5 cm left of the
    barrel: a finger standing beside the bead;
  - the hand is at the pump's back end: the index's middle joint 1.3 cm
    inside the wood, the pinky's 3 cm behind it.

Until C3 a pose of its own was keyed for it (A_AimShotgun: both thumbs, the
left hand's turn and every finger joint swung onto directions in a table).
Every gun pose is a shipped clip now, so the hand keeps the clip's shape and
is MOVED instead, as one rigid piece.

HOW
---
Down the sights the left hand is held by an IK on a point in the right hand's
space, each gun's own (support_hand.py, BP_WeaponItem.SupportPoint). The
shotgun's is the rifle pose's point plus support_move(): first straight down
until the thumb is under the barrel's top, then pump_seat.seat's descent to
where the fingers' joints fit the pump best with the thumb kept there. On the
worn hand that is 4 cm forward and 5 down: the hand cupped under the pump, its
fingers up the right side, its thumb beside the barrel under the sight line.

WHAT A SHIPPED CLIP COSTS
-------------------------
  - The hand's shape is the rifle pose's, made for a deeper handguard: seated,
    its joints ride 0.5 to 3.8 cm off the wood (the keyed pose had them
    within 1.6).
  - The point holds only down the sights (SupportHand is SightBlend). At the
    hip and on the shoulder the hand is where the clip has it; the camera is
    not on the sights there.
  - The right thumb lies forward along the top of the stock's wrist, 4 cm
    under the sight line, as the clip has it on a pistol grip; the keyed pose
    wrapped it over the wrist.
"""

from asset_pipeline.rig_util import mesh_ref_pose
from combat import pump_seat
from combat.body_pose import _conj, _mul, _norm, _turn
from combat.grip import _grip_location, _grip_rotation, _grip_socket, part_placement
from combat.hold_pose import _q, _shown
from combat.log import _log
from combat.paths import RETIRED_SHOTGUN_AIM_ANIM_PATH
from combat.support_hand import support_at
from combat.weapon_models import SHOTGUN_PUMP, shotgun_outline
from uebp.graph import _assets

# The last joint to the thumb's or the finger's tip (cm), for the seat and
# the checks: there is no bone.
THUMB_TIP_CM = 3.0
FINGER_TIP_CM = 2.5
# The thumb starts this far under the barrel's top before the seat's descent,
# which never crosses pump_seat.THUMB_CLEAR_CM.
THUMB_START_CM = 0.5


def weapon_rotation(skin, comp):
    """The weapon's frame in the component's, a quat, against a component pose
    ``comp`` ({bone: (location, quat, ...)}): the grip socket's turn, then
    GripRotation."""
    _mesh_yaw, socket = _grip_socket()
    bone = str(socket.get_editor_property("bone_name"))
    in_bone = _q(socket.get_editor_property("relative_rotation").quaternion())
    grip = _q(_grip_rotation(skin.aim_rifle).quaternion())
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


def barrel_top():
    """The top of the shotgun's barrel, a z in the weapon's frame: what the
    left thumb stays under, and it is under the sight line."""
    centre, _rot, half = part_placement(shotgun_outline(), "Barrel")
    return centre.z + half.z


def held(skin):
    """The rifle pose with the shotgun in its hand: (the pose in the
    component, the weapon's quat there, a function placing a component point
    in the weapon's frame)."""
    mesh = _assets().load_asset(skin.mesh)
    rifle = _assets().load_asset(skin.aim_rifle)
    if mesh is None or rifle is None:
        raise RuntimeError(f"could not load {skin.mesh} or {skin.aim_rifle}")
    comp = _shown(rifle, mesh, mesh_ref_pose(mesh))
    weapon = weapon_rotation(skin, comp)
    grip_rot = _grip_rotation(skin.aim_rifle)
    origin = weapon_origin(comp, _grip_location(skin.aim_rifle, grip_rot, shotgun_outline()))
    into = _conj(weapon)

    def placed(point):
        return _turn(into, tuple(p - o for p, o in zip(point, origin)))

    return comp, weapon, placed


def hand_points(skin, comp, placed):
    """({name: where} for every joint and tip of the left hand's four
    fingers, [the thumb's joints past its first, and its tip]), in the
    weapon's frame."""
    fingers = {}
    for bones in skin.support_fingers:
        at = [placed(p) for p in finger_points(bones, comp, FINGER_TIP_CM)]
        fingers.update(zip(list(bones) + [bones[-1] + " tip"], at))
    thumb = [placed(p) for p in finger_points(skin.support_thumb, comp, THUMB_TIP_CM)[1:]]
    return fingers, thumb


def support_move(skin, quiet=False):
    """How far the left hand is moved off the rifle pose's place to sit on
    the pump, (x, y, z) cm in the weapon's frame."""
    comp, _weapon, placed = held(skin)
    fingers, thumb = hand_points(skin, comp, placed)
    top = barrel_top()
    drop = min(0.0, top - THUMB_START_CM - max(p[2] for p in thumb))
    joints = [(x, y, z + drop) for x, y, z in fingers.values()]
    seat = pump_seat.seat(SHOTGUN_PUMP, joints, [(x, y, z + drop) for x, y, z in thumb], top)
    move = (seat[0], seat[1], seat[2] + drop)
    if not quiet:
        was, now = (pump_seat.misfit(SHOTGUN_PUMP, list(fingers.values()), m)
                    for m in ((0.0, 0.0, 0.0), move))
        _log(f"the shotgun: the left hand's point moved ({move[0]:.1f}, {move[1]:.1f}, "
             f"{move[2]:.1f}) cm in the weapon's frame onto the pump, the thumb under "
             f"the barrel's top: its worst joint {was:.2f} -> {now:.2f} cm from riding "
             f"{pump_seat.SEAT_OFF_CM:g} cm off the wood")
    return move


def support_point(skin, quiet=False):
    """The shotgun's SupportPoint: where the rifle pose has the left hand
    (support_at), moved by support_move(), in the right hand's bone space."""
    comp, weapon, _placed = held(skin)
    move = _turn(weapon, support_move(skin, quiet))
    in_hand = _turn(_conj(comp[skin.pose_bones["hand_r"]][1]), move)
    return tuple(round(a + m, 3) for a, m in zip(support_at(skin, skin.aim_rifle), in_hand))


def retire_keyed_pose():
    """Delete A_AimShotgun, the pose keyed for the shotgun until C3, from a
    checkout that still has it. After the weapons are built: until then the
    shotgun's Blueprint names it."""
    if _assets().does_asset_exist(RETIRED_SHOTGUN_AIM_ANIM_PATH):
        if not _assets().delete_asset(RETIRED_SHOTGUN_AIM_ANIM_PATH):
            raise RuntimeError(f"could not delete {RETIRED_SHOTGUN_AIM_ANIM_PATH}")
        _log(f"deleted {RETIRED_SHOTGUN_AIM_ANIM_PATH}: the shotgun is held in "
             "the rifle's ready pose")
