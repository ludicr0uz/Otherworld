"""A weapon picked up goes to its weapon slot before the bag.

The player sets an issued item down (DropRequest: what a drag out of the
inventory writes), the probe lays it on the ground ahead, under the reticle,
and presses the interact key (InteractForced, as probe_pickup.py does). Where
the slot sync then puts it:

    the pistol, its slot free             -> the pistol slot
    the knife, the melee slot free        -> the melee slot
    the knife, the axe in the melee slot  -> the bag
    the matches (no weapon)               -> the bag
    the shotgun, out of the hand          -> the primary slot, hands empty

(A blade taken back out of what it was thrown into goes to empty hands
instead: probe_throw_strike.py and probe_throw_stick.py.)

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import math
import os
import shutil

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, DROP_REQUEST_VAR, HAND, MELEE_SLOT, MOVE_FROM_VAR, MOVE_TO_VAR,
    NO_REQUEST, PISTOL_SLOT, PRIMARY, SLOT_ITEMS_VAR, SLOT_VAR,
)
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from probes.probe_pickup import DOWN_CM, RING_CM, SETTLE, _file, _in_reach, _look, _press

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (DROP_REQUEST_VAR, INTERACT_FORCED_VAR, MOVE_FROM_VAR, MOVE_TO_VAR)]


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _ask(p, wc, var, value):
    p.set(wc, var, value)
    yield lambda: p.get(wc, var) == NO_REQUEST
    yield SETTLE


def _round_trip(p, player, wc, item, yaw):
    """Set ``item`` down out of the slot it is in, lay it ahead and pick it
    up. Returns the slot it comes back in (None: not taken)."""
    yield from _ask(p, wc, DROP_REQUEST_VAR, p.get(item, SLOT_VAR))
    if item in list(p.get(wc, "Inventory")):
        return None
    a = math.radians(yaw)
    item.set_actor_location(
        player.get_actor_location()
        + unreal.Vector(RING_CM * math.cos(a), RING_CM * math.sin(a), -DOWN_CM),
        False, True)
    yield SETTLE
    yield from _press(p, wc)
    yield SETTLE
    if item not in list(p.get(wc, "Inventory")):
        return None
    return p.get(item, SLOT_VAR)


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    shotgun, pistol, knife, axe, matches = list(p.get(wc, "Inventory"))[:5]
    p.check("the issued items are where the probe expects them: the shotgun in hand, "
            "the pistol and the knife in their slots, the axe and the matches in the bag",
            [p.get(i, SLOT_VAR) for i in (shotgun, pistol, knife, axe, matches)]
            == [HAND, PISTOL_SLOT, MELEE_SLOT, BAG_FIRST, BAG_FIRST + 1])

    yaw = p.controller().get_control_rotation().yaw
    yield from _look(p, yaw)
    here = player.get_actor_location()
    for i in _in_reach(p, player):   # forage that happens to lie at the spawn
        i.set_actor_location(here + unreal.Vector(0.0, 0.0, 5000.0), False, True)

    slot = yield from _round_trip(p, player, wc, pistol, yaw)
    p.check("the pistol picked up goes to the pistol slot, not the bag, and the "
            "shotgun stays in hand",
            slot == PISTOL_SLOT and p.get(wc, "Held") == shotgun, f"slot {slot}")

    slot = yield from _round_trip(p, player, wc, knife, yaw)
    p.check("the knife picked up off the ground goes to the free melee slot",
            slot == MELEE_SLOT, f"slot {slot}")

    yield from _ask(p, wc, DROP_REQUEST_VAR, MELEE_SLOT)
    p.set(wc, MOVE_TO_VAR, MELEE_SLOT)
    yield from _ask(p, wc, MOVE_FROM_VAR, BAG_FIRST)
    took = p.get(axe, SLOT_VAR) == MELEE_SLOT
    a = math.radians(yaw)
    knife.set_actor_location(
        player.get_actor_location()
        + unreal.Vector(RING_CM * math.cos(a), RING_CM * math.sin(a), -DOWN_CM),
        False, True)
    yield SETTLE
    yield from _press(p, wc)
    yield SETTLE
    slot = p.get(knife, SLOT_VAR)
    p.check("with the axe in the melee slot, the knife picked up goes to the bag",
            took and knife in list(p.get(wc, "Inventory"))
            and BAG_FIRST <= slot <= BAG_LAST, f"slot {slot}, the axe moved {took}")

    slot = yield from _round_trip(p, player, wc, matches, yaw)
    p.check("the matches, no weapon, go to the bag",
            slot is not None and BAG_FIRST <= slot <= BAG_LAST, f"slot {slot}")

    slot = yield from _round_trip(p, player, wc, shotgun, yaw)
    yield SETTLE
    p.check("the shotgun set down out of the hand and picked up goes to the primary "
            "slot: not the bag, and not the empty hands",
            slot == PRIMARY and p.get(wc, "Held") is None
            and p.get(wc, SLOT_ITEMS_VAR)[HAND] is None, f"slot {slot}")
