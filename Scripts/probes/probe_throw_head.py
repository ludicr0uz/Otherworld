"""A thrown blade in the head: the knife and the axe, thrown with the reticle
on a body's head, take their ThrowDamage times the body's own HeadMultiplier
(the pellet's), and are left in a bone of its head; thrown at its middle they
take their ThrowDamage whole and are left in a bone that is not.

The head is what the blade is left in: the bone the item is attached to is
the bone the damage was counted on (weapon_component/throw_strike.py), so the
two are checked against each other, both ways.

The body is a zombie with no mind of its own, stood in front of the player
in the open, as in probe_throw_stick.py; the other wanderers are gone.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import math
import os
import shutil

import unreal

from combat.axe import AXE_DISPLAY
from combat.game_state import DAMAGED_BY_PLAYER_VAR
from combat.hit_zones import HEAD_BONES_VAR, HEAD_MULT_VAR
from combat.knife import KNIFE_DISPLAY
from combat.melee_tuning import throw_damage
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.throw_tuning import THROW_DAMAGE_VAR
from combat.tuning import COMBAT
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.throw import THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR
from combat.weapon_component.throw_strike import THROW_BONE_VAR
from probes.probe_chop_tree import _flat
from probes.probe_hot_blade import _wanderers
from probes.probe_knife import _file
from probes.probe_throw_stick import (
    BODY_AT_CM, BODY_VIEW_DEG, _held_by, _open, _take_from, _zombies,
)
from probes.probe_throw_strike import AXE, KNIFE, _dir, _stand, _throw
from combat import health_vars as HV
from combat.weapon_component import vars as WV

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (THROW_FORCED_VAR, THROW_CLICK_FORCED_VAR, INTERACT_FORCED_VAR,
              WV.EquippedIndex, WV.NeedsRefresh)]
            + [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, DAMAGED_BY_PLAYER_VAR)])

BODY_HP = 400.0           # room for every blade, and the head's worth
ON_HEAD_CM = 40.0         # the reticle's point (on the capsule), from the head's middle


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _look_at(p, player, point):
    """Turn the view until the reticle is on ``point``: the camera is off to
    one side of the player's own line and above it, so the view is turned
    from where the camera is, more than once (it moves as the view turns)."""
    cam = unreal.GameplayStatics.get_player_camera_manager(player, 0)
    for _ in range(4):
        to = point - cam.get_camera_location()
        p.controller().set_control_rotation(unreal.Rotator(
            pitch=math.degrees(math.atan2(to.z, _flat(to))),
            yaw=math.degrees(math.atan2(to.y, to.x)), roll=0.0))
        yield 0.1


def _head_middle(body, bone):
    """The middle of the head's physics body: the bone itself is the base of
    the skull, where the neck's body is."""
    mesh = body.get_editor_property("mesh")
    at = mesh.get_socket_location(bone)
    ends = [mesh.get_closest_point_on_collision(at + unreal.Vector(0, 0, dz), bone)[1]
            for dz in (200.0, -200.0)]
    return (ends[0] + ends[1]) * 0.5


def _strike(p, wc, player, item, body, health, at, yaw, head):
    """Throw ``item`` at ``body``: at its head (the reticle on the head bone)
    or, with ``head`` False, at its middle. Returns (the health it lost, the
    bone it was left in, the bone the wound was counted on)."""
    def place():
        body.set_actor_location(player.get_actor_location() + _dir(0.0, yaw) * BODY_AT_CM,
                                False, True)

    yield from _stand(p, player, at, yaw, BODY_VIEW_DEG)
    p.set(health, "Health", BODY_HP)
    place()
    yield 0.1
    place()
    if head:
        middle = _head_middle(body, str(list(p.get(health, HEAD_BONES_VAR))[0]))
        yield from _look_at(p, player, middle)
        aimed = (p.get(wc, "AimPoint") - middle).length()
        # The reticle's point is on the capsule, which stands off the head.
        p.check("the reticle is put on the body's head", aimed < ON_HEAD_CM,
                f"its point {aimed:.0f} cm from the middle of the head")
    yield from _throw(p, wc, item)
    onto, bone = _held_by(item)
    return (BODY_HP - float(p.get(health, "Health")), bone if onto == body else None,
            str(p.get(wc, THROW_BONE_VAR)))


def _run(p):
    yield lambda: len(_zombies(p)) >= 1
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    ctrl = _zombies(p)[0]
    body = ctrl.get_controlled_pawn()
    ctrl.un_possess()
    for other in _wanderers(p):
        if other.get_controlled_pawn() is not None:
            other.get_controlled_pawn().destroy_actor()

    health = p.component(body, HEALTH_CLASS_PATH)
    heads = [str(b) for b in p.get(health, HEAD_BONES_VAR)]
    worth = float(p.get(health, HEAD_MULT_VAR))
    p.check("the body has a head (its hit boxes' HeadBones) worth more than the "
            "rest of it, as a pellet finds it",
            bool(heads) and worth == COMBAT.head_multiplier and worth > 1.0,
            f"{heads} x{worth:g}")
    bag = {i.get_class().get_name(): i for i in p.get(wc, "Inventory")}
    blades = [(name, bag.get(cls), throw_damage(display)) for name, cls, display in
              (("knife", KNIFE, KNIFE_DISPLAY), ("axe", AXE, AXE_DISPLAY))]
    p.check("the knife and the axe are issued, each with its gun_tuning.csv "
            "throw damage",
            all(i is not None and float(p.get(i, THROW_DAMAGE_VAR)) == want
                for _n, i, want in blades),
            str([(n, i and p.get(i, THROW_DAMAGE_VAR), want) for n, i, want in blades]))
    if not heads or any(i is None for _n, i, _w in blades):
        return
    at = player.get_actor_location()
    yaw = _open(p, player, at)
    p.check("there is open ground by the player to stand a body on", yaw is not None)
    if yaw is None:
        return

    for name, item, damage in blades:
        lost, bone, counted = yield from _strike(p, wc, player, item, body, health,
                                                 at, yaw, head=True)
        p.check(f"a {name} thrown at the head is left in a bone of the head",
                bone in heads and counted == bone, f"in {bone}, counted on {counted}")
        p.check(f"...and takes its {damage:g} HP times the head's {worth:g}",
                abs(lost - damage * worth) < 1e-3, f"lost {lost:g}")
        taken, gap = yield from _take_from(p, wc, player, item,
                                           body.get_actor_location(), yaw)
        p.check(f"...and E takes the {name} back out of it", taken, f"{gap:.0f} cm away")
        if not taken:
            return
        lost, bone, counted = yield from _strike(p, wc, player, item, body, health,
                                                 at, yaw, head=False)
        p.check(f"a {name} thrown at the body's middle is left in a bone that is "
                "not the head's",
                bone is not None and bone not in heads and counted == bone,
                f"in {bone}, counted on {counted}")
        p.check(f"...and takes its {damage:g} HP whole", abs(lost - damage) < 1e-3,
                f"lost {lost:g}")
        taken, gap = yield from _take_from(p, wc, player, item,
                                           body.get_actor_location(), yaw)
        if not taken:
            p.check(f"E takes the {name} back", False, f"{gap:.0f} cm away")
            return
