"""What a thrown blade does to a tree: the knife and the axe lodge in the
trunk where they hit, point or bit first, and hang there as a pick-up that E
takes back; thrown too high up the trunk to be reached, or thrown as a gun is,
the item falls to the foot of the tree instead. (What it does to a body is
probe_throw_stick.py's.)

The player is stood THROW_FROM_CM from the nearest tree with a clear line to
its trunk and no forage round it, and the keys are held and clicked as
probe_throw.py does it. The wanderers are gone, but for one stood aside: the
pictures are taken through its eyes.

Run with --windowed and OW_THROW_SHOTS=1 to save a picture of each blade in
the trunk to Saved/Screenshots/MacEditor, seen from beside it through the
body's eyes (the game's own camera is behind the player).

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

SYSTEMS = ('throw',)

import math
import os
import shutil

import unreal

from combat.paths import (
    BULLET_IMPACT_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.melee_tuning import throw_damage
from combat.throw_tuning import (
    LODGE_MAX_HEIGHT_CM, LODGE_POINT_VAR, LODGE_TURN_VAR, THROW_DAMAGE_VAR,
    THROW_MELEE_PITCH_UP_DEG, THROW_START_FORWARD, THROW_START_UP,
)
from combat.slot_tuning import BAG_FIRST, BAG_LAST, HAND, MELEE_SLOT, SLOT_VAR
from combat.tuning import INTERACT_RADIUS
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.throw import (
    THROW_AIMING_VAR, THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR,
)
from combat.weapon_component.throw_flight import THROWN_VAR
from probes.probe_chop_tree import CLEAR_CM, _flat, _items, _trace, _trees
from probes.probe_hot_blade import _of, _wanderers
from probes.probe_knife import _file
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (THROW_FORCED_VAR, THROW_CLICK_FORCED_VAR, INTERACT_FORCED_VAR,
             WV.EquippedIndex, WV.NeedsRefresh)]

KNIFE, AXE = "BP_Knife_C", "BP_Axe_C"
THROW_FROM_CM = 400.0     # the player's middle, from the bark
PICK_FROM_CM = 75.0       # ...and when taking the blade back
GUN_VIEW_DEG = 0.0        # the view for a gun's throw: level, the reticle on the trunk
ON_TARGET_CM = 60.0       # the reticle's point, from the middle of what it was put on
HIGH_VIEW_DEG = (20.0, 25.0, 30.0, 35.0, 40.0)
ON_GROUND_CM = 40.0       # an item this near the ground is lying on it
ISM = unreal.InstancedStaticMeshComponent
SHOTS = bool(os.environ.get("OW_THROW_SHOTS"))
SHOT_FROM_CM = (110.0, 60.0)   # the eye from the blade: to its side, and back


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _dir(pitch, yaw):
    return unreal.MathLibrary.get_forward_vector(
        unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0))


def _launch(at, yaw):
    """Where a throw leaves from, for a player stood at ``at`` facing ``yaw``."""
    return at + _dir(0.0, yaw) * THROW_START_FORWARD + unreal.Vector(0, 0, THROW_START_UP)


def _spot(p, player, base):
    """A place to throw at the trunk at ``base`` from, or None: (where to
    stand, the yaw that faces it, where to stand to take a blade back, the
    ground at the trunk, a view pitch that throws a blade too high to lodge)."""
    half = player.get_editor_property("capsule_component").get_scaled_capsule_half_height()
    for deg in range(0, 360, 45):
        side = _dir(0.0, deg)
        yaw = deg + 180.0
        far = base + side * (THROW_FROM_CM + 60.0)
        floor = _trace(p, far + unreal.Vector(0, 0, 200.0), far - unreal.Vector(0, 0, 400.0),
                       [player])
        foot = _trace(p, base + side * 150.0 + unreal.Vector(0, 0, 200.0),
                      base + side * 150.0 - unreal.Vector(0, 0, 400.0), [player])
        if not floor or not foot or isinstance(floor[10], ISM) or isinstance(foot[10], ISM):
            continue
        chest = unreal.Vector(far.x, far.y, floor[4].z + half)
        bark = _trace(p, chest, unreal.Vector(base.x, base.y, chest.z), [player])
        if not bark or not isinstance(bark[10], ISM):
            continue
        at = bark[4] + side * THROW_FROM_CM
        at.z = floor[4].z + half + 5.0
        # The blade's own line to the trunk, and one that meets it too high.
        start = _launch(at, yaw)
        line = _trace(p, start, start + _dir(THROW_MELEE_PITCH_UP_DEG, yaw) * 600.0, [player])
        if (not line or not isinstance(line[10], ISM)
                or not 60.0 < line[4].z - base.z < LODGE_MAX_HEIGHT_CM - 40.0):
            continue
        for view in HIGH_VIEW_DEG:
            up = _trace(p, start,
                        start + _dir(view + THROW_MELEE_PITCH_UP_DEG, yaw) * 900.0, [player])
            if up and isinstance(up[10], ISM) and up[4].z - base.z > LODGE_MAX_HEIGHT_CM + 60.0:
                near = bark[4] + side * PICK_FROM_CM
                near.z = foot[4].z + half + 5.0
                return at, yaw, near, foot[4].z, view
    return None


def _stand(p, player, at, yaw, pitch=0.0):
    player.set_actor_location_and_rotation(
        at, unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0), False, True)
    p.controller().set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0))
    yield 0.2


def _reticle_on(p, wc, player, target, pitch, yaw):
    """Turn the view, at ``pitch``, until the reticle rests on what stands at
    ``target``: the camera is off to one side of the player's own line, so
    facing a thing does not put the reticle on it. Returns how far the
    reticle's point is from ``target`` over the ground, in cm."""
    cam = unreal.GameplayStatics.get_player_camera_manager(player, 0)
    for _ in range(3):
        p.controller().set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0))
        yield 0.1
        to = target - cam.get_camera_location()
        yaw = math.degrees(math.atan2(to.y, to.x))
    p.controller().set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0))
    yield 0.1
    return _flat(p.get(wc, "AimPoint") - target)


def _throw(p, wc, item):
    """Equip ``item``, hold the throw key, click, and wait for it to come to
    rest."""
    p.set(wc, "EquippedIndex", list(p.get(wc, "Inventory")).index(item))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    yield 0.1
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.05
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield lambda: not p.get(wc, THROW_AIMING_VAR) or item not in list(p.get(wc, "Inventory"))
    p.set(wc, THROW_CLICK_FORCED_VAR, False)
    yield lambda: item not in list(p.get(wc, "Inventory"))
    p.set(wc, THROW_FORCED_VAR, False)
    yield lambda: p.get(wc, THROWN_VAR) is None
    yield 0.05


def _take(p, wc, item):
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05
    return item in list(p.get(wc, "Inventory")) and not p.get(item, "Dropped")


def _alive(p, class_path):
    """The names of that class's actors: a burst lives well under a second,
    so a new one is told by its name, not by the count."""
    cls = unreal.load_object(None, class_path)
    return {a.get_name() for a in
            unreal.GameplayStatics.get_all_actors_of_class(p.world(), cls)}


def _picture(p, player, eye, item, yaw):
    """Save a picture of ``item`` where it is (windowed runs only), looking
    through ``eye``, a body stood beside it and hidden."""
    pc, at = p.controller(), item.get_actor_location()
    cam = (at + _dir(0.0, yaw + 90.0) * SHOT_FROM_CM[0]
           - _dir(0.0, yaw) * SHOT_FROM_CM[1])
    look = unreal.MathLibrary.find_look_at_rotation(cam, at)
    eye.set_actor_hidden_in_game(True)
    eye.set_actor_location_and_rotation(
        cam - unreal.Vector(0, 0, eye.get_editor_property("base_eye_height")),
        look, False, True)
    pc.set_view_target_with_blend(eye)
    yield 0.6
    unreal.SystemLibrary.execute_console_command(p.world(), "shot")
    yield 0.4
    pc.set_view_target_with_blend(player)
    eye.set_actor_hidden_in_game(False)
    yield 0.1


def _lodge(p, wc, player, item, name, spot, base, eye):
    """Throw ``item`` at the trunk and check it lodges there; take it back."""
    lib = unreal.MathLibrary
    at, yaw, near, ground, _view = spot
    yield from _stand(p, player, at, yaw)
    chips = _alive(p, BULLET_IMPACT_CLASS_PATH)
    yield from _throw(p, wc, item)
    rest, rot = item.get_actor_location(), item.get_actor_rotation()
    up = rest.z - base.z
    p.check(f"the {name} thrown at a tree stays in the trunk, off the ground, "
            "and is a pick-up",
            p.get(item, "Dropped") is True and ON_GROUND_CM < rest.z - ground
            and up < LODGE_MAX_HEIGHT_CM + 30.0 and _flat(rest - base) < 120.0,
            f"{rest.z - ground:.0f} cm over the ground, {_flat(rest - base):.0f} cm "
            "from the tree's middle")
    # What leads into the wood, in the world: the item's own turn undone.
    lead = lib.greater_greater_vector_rotator(
        lib.get_forward_vector(lib.negate_rotator(p.get(item, LODGE_TURN_VAR))), rot)
    point = lib.transform_location(item.get_actor_transform(), p.get(item, LODGE_POINT_VAR))
    bark = _trace(p, point - lead * 100.0, point + lead * 40.0, [player])
    p.check("...its point or bit into the wood: along the throw, and into the bark",
            lead.dot(_dir(0.0, yaw)) > 0.9 and bark is not None
            and isinstance(bark[10], ISM) and lead.dot(bark[7]) < -0.3,
            f"lead . throw {lead.dot(_dir(0.0, yaw)):+.2f}"
            + (f", lead . bark's normal {lead.dot(bark[7]):+.2f}" if bark else ", no bark"))
    p.check(f"...set {(point - bark[4]).length() if bark else -1:.1f} cm from the "
            "bark at the point of it meant to be there",
            bark is not None and (point - bark[4]).length() < 3.0)
    p.check("...leaving chips where it struck",
            bool(_alive(p, BULLET_IMPACT_CLASS_PATH) - chips))
    yield 0.4
    p.check("...and it hangs there: it does not move",
            (item.get_actor_location() - rest).length() < 0.1)
    if SHOTS:
        yield from _picture(p, player, eye, item, yaw)

    yield from _stand(p, player, near, yaw)
    gap = (player.get_actor_location() - item.get_actor_location()).length()
    lodged = p.get(item, "Lodged")
    taken = yield from _take(p, wc, item)
    p.check(f"E at the trunk takes the {name} back",
            taken and gap < INTERACT_RADIUS, f"{gap:.0f} cm away")
    yield lambda: p.get(wc, "Held") == item
    p.check("...into the empty hands it was thrown from, no longer Lodged",
            p.get(wc, "Held") == item and p.get(item, SLOT_VAR) == HAND
            and p.get(item, "Lodged") is False and lodged is True,
            f"slot {p.get(item, SLOT_VAR)}, was Lodged {lodged}")


def _falls(p, wc, player, item, label, spot, base, pitch, reticle=False):
    """Throw ``item`` at the trunk with the view at ``pitch``: it must come
    down to the ground at the tree's foot. With ``reticle`` the view is turned
    to put the reticle on the trunk first: the throw goes to its point."""
    at, yaw, near, ground, _view = spot
    yield from _stand(p, player, at, yaw, pitch)
    aimed = 0.0
    if reticle:
        aimed = yield from _reticle_on(p, wc, player, base, pitch, yaw)
    yield from _throw(p, wc, item)
    rest = item.get_actor_location()
    p.check(label,
            p.get(item, "Dropped") is True and abs(rest.z - ground) < ON_GROUND_CM + 30.0
            and _flat(rest - base) < 200.0 and aimed < ON_TARGET_CM,
            f"{rest.z - ground:.0f} cm over the ground, {_flat(rest - base):.0f} cm "
            "from the tree's middle"
            + (f", the reticle {aimed:.0f} cm from it" if reticle else ""))
    yield from _stand(p, player, near, yaw)


def _run(p):
    yield lambda: _of(p, "Zombie") is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    # One zombie with no mind of its own, to see through; the rest are gone.
    ctrl = _of(p, "Zombie")
    body = ctrl.get_controlled_pawn()
    ctrl.un_possess()
    for other in _wanderers(p):
        other.get_controlled_pawn().destroy_actor()

    bag = {i.get_class().get_name(): i for i in p.get(wc, "Inventory")}
    guns = [i for i in bag.values() if i.get_editor_property("UsesAmmo")]
    sharp = {n: float(p.get(i, THROW_DAMAGE_VAR)) for n, i in bag.items()
             if p.get(i, THROW_DAMAGE_VAR) > 0.0}
    p.check("of what the player is issued, the knife and the axe have a ThrowDamage",
            sharp == {KNIFE: throw_damage("Knife"), AXE: throw_damage("Axe")} and len(guns) >= 2,
            str(sharp))
    if set(sharp) != {KNIFE, AXE} or len(guns) < 2:
        return
    knife, axe = bag[KNIFE], bag[AXE]

    # --- the tree ---------------------------------------------------------------
    lying = [a.get_actor_location() for a in _items(p) if p.get(a, "Dropped")]
    here = player.get_actor_location()
    spot = base = None
    for _comp, _index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length())[:60]:
        if any(_flat(at - base) < CLEAR_CM for at in lying):
            continue
        spot = _spot(p, player, base)
        if spot:
            break
    p.check("the level has a tree to throw at, with a clear line to its trunk",
            spot is not None)
    if spot is None:
        return
    yield from _lodge(p, wc, player, knife, "knife", spot, base, body)
    yield from _lodge(p, wc, player, axe, "axe", spot, base, body)
    yield from _falls(p, wc, player, knife,
                      f"a knife that strikes the trunk more than {LODGE_MAX_HEIGHT_CM:g} "
                      "cm up glances off: it falls to the foot of the tree",
                      spot, base, spot[4])
    taken = yield from _take(p, wc, knife)
    yield 0.2
    p.check("...where E takes it back: not Lodged, so not to the empty hands (the axe "
            "is in the melee slot: to the bag)",
            taken and p.get(axe, SLOT_VAR) == MELEE_SLOT
            and BAG_FIRST <= p.get(knife, SLOT_VAR) <= BAG_LAST and p.get(wc, "Held") is None,
            f"slot {p.get(knife, SLOT_VAR)}, the axe in {p.get(axe, SLOT_VAR)}")
    yield from _falls(p, wc, player, guns[0],
                      "a gun thrown at the trunk does not lodge: it falls to the "
                      "foot of the tree", spot, base, GUN_VIEW_DEG, reticle=True)
