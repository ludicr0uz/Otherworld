"""What a thrown blade does to a body: the knife and the axe each take their
own ThrowDamage off it, draw blood and stay in it: set on the model where it
struck, attached to the bone there, going where the body goes, and taken back
with E from within reach of it and not from beyond. That holds for a body the
blade killed, down on the ground with it, and one whose corpse is gone leaves
the blade where it lay. A gun thrown at a body takes nothing and falls at its
foot.

The body the blade wounds flinches, as it does at any damage: the health
component's flinch is a poll of Health (hit_reaction.py), so the throw has no
trigger of its own to forget. Here it is seen to play, away from the thrower;
the gun, which takes nothing, plays none, and the blade that kills plays none
either (the body ragdolls instead).

The bodies are two zombies with no mind of their own, stood in turn in front
of the player in the open; the other wanderers are gone. The keys are held
and clicked as probe_throw_strike.py, the tree's half, does it.

Run with --windowed and OW_THROW_SHOTS=1 to save a picture of each blade in
the body to Saved/Screenshots/MacEditor, seen through the second body's eyes.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.anim_blueprint import HIT_SLOT
from combat.game_state import DAMAGED_BY_PLAYER_VAR
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.paths import (
    BLOOD_CLASS_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH,
)
from combat.melee_tuning import throw_damage
from combat.throw_tuning import (
    LODGE_POINT_VAR, LODGE_TURN_VAR, THROW_DAMAGE_VAR,
)
from combat.tuning import INTERACT_RADIUS
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.throw import THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR
from combat.weapon_component.throw_strike import THROW_PAST_VAR
from probes.probe_chop_tree import _flat, _trace
from probes.probe_hot_blade import _wanderers
from probes.probe_knife import _file
from probes.probe_throw_strike import (
    AXE, ISM, KNIFE, ON_GROUND_CM, SHOTS, _alive, _dir, _picture, _reticle_on,
    _stand, _take, _throw,
)
from combat import health_vars as HV
from combat.weapon_component import vars as WV

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (THROW_FORCED_VAR, THROW_CLICK_FORCED_VAR, INTERACT_FORCED_VAR,
              WV.EquippedIndex, WV.NeedsRefresh)]
            + [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, DAMAGED_BY_PLAYER_VAR)])

BODY_AT_CM = 300.0        # the body, in front of the player
BODY_HP = 200.0           # room for a blade
FRAIL_HP = 50.0           # ...and a body the axe kills
BODY_VIEW_DEG = -8.0      # the view for a throw at the body
ON_TARGET_CM = 60.0       # the reticle's point, from the body's middle
TAKE_FROM_CM = 130.0      # the player's middle from the body's, taking a blade back
TOO_FAR_CM = 600.0        # ...and from where it cannot be
SWAY_CM = 40.0            # how far a standing body's own motion carries a blade in it
PRESSES = 3               # of E, to take one item out of a small pile
ON_SKIN_CM = 3.0          # the blade's lodge point, from the body it is set on
FLINCH_WITHIN_S = 0.3     # of the throw coming to rest (the shortest clip plays 0.5 s)
FLINCH_OVER_S = 2.0       # ...and the longest is well over by then


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _open(p, player, at):
    """A yaw from ``at`` with nothing in the way of a throw at a body."""
    for deg in range(0, 360, 30):
        reach = at + _dir(0.0, deg) * (BODY_AT_CM + 250.0)
        floor = _trace(p, reach + unreal.Vector(0, 0, 150.0), reach - unreal.Vector(0, 0, 400.0),
                       [player])
        if _trace(p, at, reach, [player]) is None and floor and not isinstance(floor[10], ISM):
            return float(deg)
    return None


def _wound(p, wc, player, item, body, health, at, yaw, pitch, hp=BODY_HP,
           reticle=False):
    """Throw ``item`` at ``body``, which has ``hp``; returns (the health it
    lost, how far over the ground under it the item came to rest, how far
    from the body). With ``reticle`` the view is turned to put the reticle on
    the body first, and the throw goes to its point."""
    def place():
        body.set_actor_location(player.get_actor_location() + _dir(0.0, yaw) * BODY_AT_CM,
                                False, True)

    yield from _stand(p, player, at, yaw, pitch)
    p.set(health, "Health", hp)
    p.set(health, DAMAGED_BY_PLAYER_VAR, False)
    place()
    yield 0.1
    place()
    if reticle:
        aimed = yield from _reticle_on(p, wc, player, body.get_actor_location(),
                                       pitch, yaw)
        p.check("the reticle is put on the body", aimed < ON_TARGET_CM,
                f"its point {aimed:.0f} cm from the body's middle")
    yield from _throw(p, wc, item)
    rest = item.get_actor_location()
    floor = _trace(p, rest + unreal.Vector(0, 0, 50.0), rest - unreal.Vector(0, 0, 500.0),
                   [player, body])
    return (hp - float(p.get(health, "Health")),
            rest.z - floor[4].z if floor else 1.0e6,
            _flat(rest - body.get_actor_location()))


def _flinching(body):
    anim = body.get_editor_property("mesh").get_anim_instance()
    return anim is not None and anim.is_slot_active(HIT_SLOT)


def _flinch(body, within, want=True):
    """Wait up to ``within`` s for ``body`` to be flinching (or, with
    ``want`` False, to have stopped); returns whether it is."""
    waited = 0.0
    while waited < within and _flinching(body) != want:
        yield 0.02
        waited += 0.02
    return _flinching(body)


def _held_by(item):
    """(the actor ``item`` is attached to, at which bone)."""
    return (item.get_attach_parent_actor(),
            str(item.get_editor_property("root_component").get_attach_socket_name()))


def _in_body(p, wc, item, name, body, over, off, yaw):
    """``item`` has just been thrown at ``body``: check it stayed in it."""
    lib = unreal.MathLibrary
    mesh = body.get_editor_property("mesh")
    onto, bone = _held_by(item)
    p.check(f"...and the {name} stays in the body: a pick-up, off the ground, "
            "attached to the bone it struck",
            p.get(item, "Dropped") is True and onto == body
            and mesh.get_bone_index(bone) >= 0 and over > ON_GROUND_CM and off < 60.0
            and not list(p.get(wc, THROW_PAST_VAR)),
            f"on {onto.get_name() if onto else None} at {bone}, {over:.0f} cm over "
            f"the ground, {off:.0f} cm from its middle")
    point = lib.transform_location(item.get_actor_transform(), p.get(item, LODGE_POINT_VAR))
    gap, _on = mesh.get_closest_point_on_collision(point, bone)
    lead = lib.greater_greater_vector_rotator(
        lib.get_forward_vector(lib.negate_rotator(p.get(item, LODGE_TURN_VAR))),
        item.get_actor_rotation())
    p.check("...set on the model, not in the air round it, its point or bit "
            "leading along the throw",
            0.0 <= gap < ON_SKIN_CM and lead.dot(_dir(0.0, yaw)) > 0.9,
            f"{gap:.1f} cm from the {bone} body, lead . throw {lead.dot(_dir(0.0, yaw)):+.2f}")
    return onto == body


def _take_from(p, wc, player, item, about, yaw):
    """Stand beside ``about`` (a point), facing it, and press E. Returns
    (whether ``item`` was taken, how far away it was)."""
    half = player.get_editor_property("capsule_component").get_scaled_capsule_half_height()
    at = about - _dir(0.0, yaw) * TAKE_FROM_CM
    floor = _trace(p, at + unreal.Vector(0, 0, 200.0), at - unreal.Vector(0, 0, 500.0),
                   [player])
    at.z = (floor[4].z if floor else about.z) + half + 5.0
    yield from _stand(p, player, at, yaw)
    gap = (player.get_actor_location() - item.get_actor_location()).length()
    # A press takes the one item nearest the reticle, and a body the blade
    # killed has dropped its gun beside it: press again past that.
    taken = False
    for _press in range(PRESSES):
        taken = yield from _take(p, wc, item)
        if taken:
            break
    return taken, gap


def _zombies(p):
    return [c for c in _wanderers(p)
            if c.get_class().get_name().startswith("BP_ForestWandererAI_Zombie")]


def _bodies(p, wc, player, knife, axe, gun, body, second, at, yaw):
    """The body half: both blades into a living body, the axe into one it
    kills, the knife into one whose corpse then goes, and a gun."""
    health = p.component(body, HEALTH_CLASS_PATH)
    out = _dir(0.0, yaw)
    second.set_actor_location(at - out * 1500.0, False, True)

    # --- alive: it stays in, goes where the body goes, and comes back ----------
    blood = _alive(p, BLOOD_CLASS_PATH)
    lost, over, off = yield from _wound(p, wc, player, knife, body, health, at, yaw,
                                        BODY_VIEW_DEG)
    hit = throw_damage("Knife")
    p.check(f"a thrown knife takes {hit:g} HP off the body it strikes",
            abs(lost - hit) < 1e-3, f"lost {lost:g}")
    p.check("...as the player's doing, and it draws blood",
            p.get(health, DAMAGED_BY_PLAYER_VAR) is True
            and bool(_alive(p, BLOOD_CLASS_PATH) - blood),
            f"DamagedByPlayer {p.get(health, DAMAGED_BY_PLAYER_VAR)}")
    flinched = yield from _flinch(body, FLINCH_WITHIN_S)
    back = p.get(health, LAST_HIT_FROM_VAR)
    p.check("...and the body flinches at it, as at any damage, away from the thrower",
            flinched and back.dot(out) < -0.5,
            f"{HIT_SLOT} active {flinched}, {LAST_HIT_FROM_VAR} . throw {back.dot(out):+.2f}")
    if not _in_body(p, wc, knife, "knife", body, over, off, yaw):
        return
    if SHOTS:
        yield from _picture(p, player, second, knife, yaw)
    was, stood = knife.get_actor_location(), body.get_actor_location()
    body.set_actor_location(stood + _dir(0.0, yaw + 90.0) * 250.0 + out * 200.0, False, True)
    yield 0.3
    went = (knife.get_actor_location() - was) - (body.get_actor_location() - stood)
    # (Its bone is not still: the arm sways as the body stands.)
    p.check("...and goes where the body goes",
            went.length() < SWAY_CM and (knife.get_actor_location() - was).length() > 250.0,
            f"{went.length():.1f} cm off the body's own move")
    far = body.get_actor_location() - out * (TOO_FAR_CM - TAKE_FROM_CM)
    taken, gap = yield from _take_from(p, wc, player, knife, far, yaw)
    p.check("E from beyond reach of the body does not take it",
            not taken and gap > INTERACT_RADIUS and _held_by(knife)[0] == body,
            f"{gap:.0f} cm away")
    taken, gap = yield from _take_from(p, wc, player, knife, body.get_actor_location(), yaw)
    p.check("E beside the living body takes the knife back into the bag, off the body",
            taken and gap < INTERACT_RADIUS and _held_by(knife)[0] != body,
            f"{gap:.0f} cm away, now on "
            f"{_held_by(knife)[0].get_name() if _held_by(knife)[0] else None}")
    if not taken:
        return

    still = yield from _flinch(body, FLINCH_OVER_S, want=False)
    lost, _over, off = yield from _wound(p, wc, player, gun, body, health, at, yaw,
                                         BODY_VIEW_DEG, reticle=True)
    flinched = yield from _flinch(body, FLINCH_WITHIN_S)
    p.check("a gun thrown at the body, which takes nothing, plays no flinch",
            not still and not flinched and lost == 0.0,
            f"{HIT_SLOT} active before {still}, after {flinched}")
    p.check("a gun thrown at the body strikes it, takes nothing and stays in "
            "nothing: it falls at its foot",
            lost == 0.0 and off < 150.0 and not p.get(health, DAMAGED_BY_PLAYER_VAR)
            and not list(p.get(wc, THROW_PAST_VAR)) and _held_by(gun)[0] is None
            and p.get(gun, "Dropped") is True,
            f"lost {lost:g}, at rest {off:.0f} cm from it")
    # Out of the way: the blades are next to be taken from here.
    yield from _take_from(p, wc, player, gun, gun.get_actor_location(), yaw)

    # --- killed by it: the blade goes down with the body, and comes back -------
    lost, over, off = yield from _wound(p, wc, player, axe, body, health, at, yaw,
                                        BODY_VIEW_DEG, FRAIL_HP)
    p.check(f"a thrown axe kills a body with {FRAIL_HP:g} HP",
            lost == FRAIL_HP and p.get(health, "Dead") is True,
            f"lost {lost:g}, Dead {p.get(health, 'Dead')}")
    p.check("...and a body the blade kills does not flinch: it falls",
            not _flinching(body), f"{HIT_SLOT} active {_flinching(body)}")
    up = axe.get_actor_location().z
    if not _in_body(p, wc, axe, "axe", body, over, off, yaw):
        return
    if SHOTS:
        yield from _picture(p, player, second, axe, yaw)
    yield lambda: axe.get_actor_location().z < up - 40.0
    yield 0.3
    p.check("...and the axe goes down with the body it killed, still in it, "
            "still a pick-up",
            _held_by(axe)[0] == body and p.get(axe, "Dropped") is True,
            f"{up - axe.get_actor_location().z:.0f} cm lower")
    taken, gap = yield from _take_from(p, wc, player, axe, axe.get_actor_location(), yaw)
    p.check("E beside the dead body takes the axe back",
            taken and gap < INTERACT_RADIUS and _held_by(axe)[0] != body,
            f"{gap:.0f} cm away")

    # --- the body gone: the blade is left where it lay -------------------------
    health = p.component(second, HEALTH_CLASS_PATH)
    lost, over, off = yield from _wound(p, wc, player, knife, second, health, at, yaw,
                                        BODY_VIEW_DEG)
    if not _in_body(p, wc, knife, "knife, thrown at a second body,", second, over, off, yaw):
        return
    was = knife.get_actor_location()
    second.destroy_actor()
    yield 0.3
    alive = unreal.SystemLibrary.is_valid(knife)
    p.check("a body that is gone (a corpse's time is up) leaves the knife "
            "where it was, a pick-up",
            alive and _held_by(knife)[0] is None and p.get(knife, "Dropped") is True
            and (knife.get_actor_location() - was).length() < 5.0)
    if alive:
        taken, gap = yield from _take_from(p, wc, player, knife, was, yaw)
        p.check("...where E takes it back", taken and gap < INTERACT_RADIUS,
                f"{gap:.0f} cm away")


def _run(p):
    yield lambda: len(_zombies(p)) >= 2
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    bodies = []
    for ctrl in _zombies(p)[:2]:
        bodies.append(ctrl.get_controlled_pawn())
        ctrl.un_possess()
    for other in _wanderers(p):
        other.get_controlled_pawn().destroy_actor()

    bag = {i.get_class().get_name(): i for i in p.get(wc, "Inventory")}
    guns = [i for i in bag.values() if i.get_editor_property("UsesAmmo")]
    sharp = {n: float(p.get(i, THROW_DAMAGE_VAR)) for n, i in bag.items()
             if p.get(i, THROW_DAMAGE_VAR) > 0.0}
    p.check("of what the player is issued, the knife and the axe have a ThrowDamage",
            sharp == {KNIFE: throw_damage("Knife"), AXE: throw_damage("Axe")} and bool(guns),
            str(sharp))
    if set(sharp) != {KNIFE, AXE} or not guns:
        return
    at = player.get_actor_location()
    yaw = _open(p, player, at)
    p.check("there is open ground by the player to stand a body on", yaw is not None)
    if yaw is None:
        return
    yield from _bodies(p, wc, player, bag[KNIFE], bag[AXE], guns[0], bodies[0],
                       bodies[1], at, yaw)
