"""Down every gun's sights both hands are on that gun's model
(combat/gun_hold.py): the left on the part its row names, the right on the
grip and in no part.

The build seats each gun's SupportPoint, the point the support hand's IK
holds the left wrist on down the sights, on the gun's own model, measured
against the ready pose's first frame; verify/gun_hold.py re-measures that.
What only a running game shows is whether the hand gets there: the pose is
layered over the body's own, the IK does not stretch the arm, and the
shoulder it reaches from is the aiming body's, not the clip's.

For each gun (the two issued and the dev menu's; weapon_models.GUN_HOLDS has its outline and what the
left hand holds, by its Blueprint's name), raised the real way (RaiseForced, then SightsForced), the
live mesh's joints are read in the held gun's own frame (+X down the barrel,
+Y right, +Z up):

  - the left wrist is at the gun's SupportPoint, in the right hand's bone
    space: the arm reaches it;
  - no left finger joint is more than 1.5 cm inside the part (a joint is the
    bone's axis, about a centimetre under the skin; half a centimetre for the
    live blend), every joint within 5.25 cm of it, none in a part beside it;
  - the left thumb's joints are under the sight line;
  - no right finger or thumb joint is more than 2 cm inside any part.

A pistol's part is its grip with the right hand's three wrapping fingers on
it (gun_hold.fist_box), read off the live right hand.

A gun of weapon_models.GUN_FINGERS is held in a clip of its own, its fingers
bent onto its model (combat/finger_pose.py; verify/finger_pose.py measures
the saved clip). Here the live fingers: the gun's AimPose is that clip, and
each of the seven bent fingers (the left hand's four, the right's middle,
ring and little) lies on the model, its riding points (its two outer joints,
its tip, the middles of its outer bones) a skin off it. And lowered again it
is still carried in both hands (CarryPose): the carry knows its clip.
"""

SYSTEMS = ('weapons', 'animation')
# The 50 m probe level's pack reaches the player in four seconds and kills
# them before the fourth gun is up (a dead player's sights never seat).
LEVEL = "/Game/Maps/Lvl_Forest_200m"

import time

import unreal

from combat import finger_fit, gun_hold, hand_seat
from combat.finger_pose import FINGER_NAMES, clip_for
from combat.carry_pose_consts import CARRY_POSE
from combat.carry_tuning import LOWERED_VAR, RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.skin import skin_of_mesh
from combat.support_hand import SUPPORT_POINT_VAR
from combat.weapon_component import vars as WV
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from probes.probe_sight_align import HUD_BP_PATH, _live_hud
from combat.weapon_models import GUN_FINGERS, GUN_HOLDS

WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR)]
SEATED = 0.99           # the camera is on the sights
# The live wrist against the gun's point (cm): the IK's own error is nothing;
# this is the arm falling short of a point it cannot reach (the pump-action's
# first seat, 3.7 cm past the arm, read 3.69 here).
WRIST_CM = 1.0
# As verify/gun_hold.py, with half a centimetre for the live blend.
SINK_CM = 1.5
REACH_CM = 5.25
GRIP_SINK_CM = 2.0
# A fitted gun's finger is laid on the model when every riding point of it
# is this far off it (cm): verify/finger_pose.py's 0.3 to 1.6 of the saved
# clip, with a little for the live blend (measured 0.46 to 1.51; the ready
# pose unfitted leaves five of an AK's seven past it, 1.98 to 2.42). The
# AK's left index is past the front of its handguard and is the pose's.
FINGER_NEAR_CM = 0.1
FINGER_FAR_CM = 1.8
# The shotgun's own (verify/finger_pose.BOUNDS has why: its pump is shallow
# for the pose's hand, 0.17 to 2.66 in the saved clip), {Blueprint: (near, far)}.
FINGER_BOUNDS = {"BP_Shotgun": (-0.1, 3.0)}
FINGERS_LAID = 6
CARRIED = 0.95          # the carry's weight, eased up
CARRY_WAIT_S = 6.0      # wall seconds for it


def _points(mesh, held, fingers, thumb):
    """({joint or tip: where} for ``fingers``, [the thumb's joints past its
    first]) of the live mesh, in the held gun's frame. A tip is the last
    bone's line carried on: the live mesh has no bone there."""
    into = held.get_actor_transform().inverse()

    def at(bone):
        v = unreal.MathLibrary.transform_location(into, mesh.get_socket_location(bone))
        return (v.x, v.y, v.z)

    out = {}
    for bones in fingers:
        last, before = at(bones[-1]), at(bones[-2])
        n = sum((a - b) ** 2 for a, b in zip(last, before)) ** 0.5 or 1.0
        out.update({b: at(b) for b in bones})
        out[bones[-1] + " tip"] = tuple(
            a + gun_hold.FINGER_TIP_CM * (a - b) / n for a, b in zip(last, before))
    return out, [at(b) for b in thumb[1:]]


def _worst(boxes, points):
    return min(((part, name, hand_seat.box_distance(box, p))
                for part, box in boxes.items() for name, p in points.items()),
               key=lambda found: found[2])


def _check_gun(p, mesh, held, skin, name):
    outline, support = GUN_HOLDS[name]
    parts = outline()
    boxes = {part[0]: gun_hold.part_box(parts, part[0]) for part in parts}
    right, right_thumb = _points(mesh, held, skin.grip_fingers, skin.grip_thumb)
    left, left_thumb = _points(mesh, held, skin.support_fingers, skin.support_thumb)
    box = support["box"] if "box" in support else boxes[support["part"]]
    if support.get("fist"):
        wrapping = {b for finger in skin.grip_fingers[1:] for b in finger}
        box = gun_hold.fist_box(box, [v for k, v in right.items()
                                      if k.replace(" tip", "") in wrapping])
    on = support.get("part", "handguard")

    want = held.get_editor_property(SUPPORT_POINT_VAR)
    got = unreal.MathLibrary.inverse_transform_location(
        mesh.get_socket_transform(skin.pose_bones["hand_r"]),
        mesh.get_socket_location(skin.pose_bones["hand_l"]))
    off = (got - want).length()
    p.check(f"{name}: down its sights the left wrist is at the gun's own point, "
            f"within {WRIST_CM:g} cm: the arm reaches it",
            off < WRIST_CM, f"{off:.2f} cm off {want.to_tuple()}")
    dist = {b: hand_seat.box_distance(box, v) for b, v in left.items()}
    deepest, furthest = min(dist, key=dist.get), max(dist, key=dist.get)
    p.check(f"...the left hand on its {on}, no finger joint more than "
            f"{SINK_CM:g} cm inside it",
            dist[deepest] > -SINK_CM, f"{deepest} {dist[deepest]:.2f} cm")
    p.check(f"...its fingers round it: every joint and tip within {REACH_CM:g} cm",
            dist[furthest] < REACH_CM, f"{furthest} {dist[furthest]:.2f} cm off")
    beside = {k: b for k, b in boxes.items() if not hand_seat.overlaps(b, box)}
    if beside:
        part, joint, d = _worst(beside, left)
        p.check(f"...and no joint more than {SINK_CM:g} cm in a part beside it",
                d > -SINK_CM, f"{joint} {d:.2f} cm from the {part}")
    line = held.get_editor_property("SightAim").z
    high = max(v[2] for v in left_thumb)
    p.check(f"...its thumb's joints under the sight line (z {line:.1f})",
            high < line, f"highest joint z {high:.2f}")
    hand = dict(right)
    hand.update({f"thumb {i}": v for i, v in enumerate(right_thumb)})
    part, joint, d = _worst(boxes, hand)
    p.check(f"...and the right hand on the gun, no joint more than {GRIP_SINK_CM:g} "
            "cm inside any part", d > -GRIP_SINK_CM, f"{joint} {d:.2f} cm from the {part}")


def _finger(mesh, held, bones):
    """A live finger's three joints and its tip in the held gun's frame, the
    tip down its last bone's own line as the build has it
    (gun_hold.finger_points): _points carries the middle bone's line on,
    which a bent last joint leaves."""
    gun = held.get_actor_transform()
    comp = {}
    for bone in bones:
        xf = unreal.MathLibrary.make_relative_transform(
            mesh.get_socket_transform(bone), gun)
        t, q = xf.translation, xf.rotation
        comp[bone] = ((t.x, t.y, t.z), (q.x, q.y, q.z, q.w))
    return gun_hold.finger_points(bones, comp, gun_hold.FINGER_TIP_CM)


def _check_fingers(p, mesh, held, skin, name):
    """The live fingers of a gun whose fingers are fitted."""
    outline, support = GUN_HOLDS[name]
    parts = outline()
    boxes = [gun_hold.part_box(parts, part[0]) for part in parts]
    box = support["box"] if "box" in support else gun_hold.part_box(parts, support["part"])
    # What the left fingers lie on, as finger_pose.solid has it.
    beside = boxes if finger_fit.through(support) else (
        [box] + [b for b in boxes if not hand_seat.overlaps(b, box)])
    near_cm, far_cm = FINGER_BOUNDS.get(name, (FINGER_NEAR_CM, FINGER_FAR_CM))
    pose = held.get_editor_property("AimPose")
    want = clip_for(name).rsplit("/", 1)[-1]
    p.check(f"{name}: it is held in its own clip, {want}",
            pose is not None and pose.get_name() == want, str(pose))
    fingers = [(f"left {n}", bones, beside)
               for n, bones in zip(FINGER_NAMES, skin.support_fingers)]
    fingers += [(f"right {n}", bones, boxes)
                for n, bones in list(zip(FINGER_NAMES, skin.grip_fingers))[1:]]
    laid, said = [], []
    for label, bones, on in fingers:
        d = [finger_fit.nearest(on, [pt])
             for pt in finger_fit.riding(_finger(mesh, held, bones))]
        said.append(f"{label} {min(d):.2f} to {max(d):.2f}")
        if min(d) > near_cm and max(d) < far_cm:
            laid.append(label)
    p.check(f"...and its fingers lie on the model: at least {FINGERS_LAID} of the "
            f"seven with every riding point {near_cm:g} to {far_cm:g} cm "
            "off it", len(laid) >= FINGERS_LAID, "; ".join(said))


def probe(p):
    yield lambda: p.pawn() is not None
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield lambda: len(p.get(wc, "Inventory")) > 0
    mesh = p.pawn().get_editor_property("mesh")
    # player_skin() asks the editor's asset subsystem, which a game has not.
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    skin = skin_of_mesh(worn)
    p.check("the player wears a known skin", skin is not None, worn)
    # Two guns are issued; the dev menu's request puts the rest in the bag.
    layers = p.pose_instance(mesh)
    hud = _live_hud(p)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    guns = [name for name in GUN_HOLDS if name + "_C" in bag]
    p.check("every gun of GUN_HOLDS is in the bag", len(guns) == len(GUN_HOLDS), str(bag))
    if skin is None:
        return
    for name in guns:
        index = bag.index(name + "_C")
        p.set(wc, "EquippedIndex", index)
        p.set(wc, "NeedsRefresh", True)
        yield lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index]
        held = p.get(wc, "Held")
        p.set(wc, RAISE_FORCED_VAR, True)
        yield 0.8
        p.set(wc, SIGHTS_FORCED_VAR, True)
        yield lambda: p.get(wc, SEAT_VAR) > SEATED
        yield 0.3
        _check_gun(p, mesh, held, skin, name)
        if name in GUN_FINGERS:
            _check_fingers(p, mesh, held, skin, name)
        p.set(wc, SIGHTS_FORCED_VAR, False)
        p.set(wc, RAISE_FORCED_VAR, False)
        yield lambda: p.get(wc, SEAT_VAR) < 0.01
        if name in GUN_FINGERS:
            # Its HandPose is no longer the rifle's ready pose, which the
            # carry asks for: its own clip is one of CarryAlso.
            end = time.time() + CARRY_WAIT_S
            yield lambda: p.get(layers, CARRY_POSE) > CARRIED or time.time() > end
            p.check(f"...and lowered it is carried in both hands as the rifle's pose "
                    f"is: {CARRY_POSE} is up",
                    p.get(wc, LOWERED_VAR) and p.get(layers, CARRY_POSE) > CARRIED,
                    f"{CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}, lowered "
                    f"{p.get(wc, LOWERED_VAR)}")
