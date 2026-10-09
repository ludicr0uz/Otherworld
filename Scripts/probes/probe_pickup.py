"""The pick-up: one press takes one item, the one nearest the reticle's point.

Three of the level's forage items are moved to 150 cm around the player: one
towards AimPoint, one to the side and one behind. A press must take exactly
the one nearest AimPoint and leave the other two on the ground. The view then
turns right round, which makes the item that was farthest the nearest, and the
next press must take that one: the order follows the reticle, not the order
the actors come in. A press with nothing in reach takes nothing.

No key can be injected into a headless game, so the probe presses the key by
writing InteractForced, which interact.py ORs with the key and clears on the
press (verify/interact.py checks the graph around it).

Any profile on disk is set aside first, so the game starts on the issued
loadout with room in the bag, and put back at the end.
"""

SYSTEMS = ('inventory',)

import math
import os
import shutil

import unreal

from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import INVENTORY_SIZE, INTERACT_RADIUS
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, INTERACT_FORCED_VAR)]

RING_CM = 150.0        # how far from the player the three items are laid
DOWN_CM = 60.0         # below the capsule's centre: about knee height
LOOK_DOWN_DEG = -35.0  # the reticle on the ground a few metres ahead
CLEAR_MARGIN_CM = 30.0 # the nearest must beat the runner-up by this much
SETTLE = 0.2           # game seconds for the aim trace after the view moves


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _dist(a, b):
    return (a - b).length()


def _on_ground(p, items):
    return [i for i in items if i.get_editor_property("Dropped")]


def _in_reach(p, player):
    """Every Dropped item the pick-up would consider, nearest AimPoint first."""
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    aim = p.get(wc, "AimPoint")
    here = player.get_actor_location()
    every = unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH))
    near = [i for i in every if i.get_editor_property("Dropped")
            and _dist(i.get_actor_location(), here) < INTERACT_RADIUS]
    return sorted(near, key=lambda i: _dist(i.get_actor_location(), aim))


def _press(p, wc):
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05


def _look(p, yaw):
    p.controller().set_control_rotation(
        unreal.Rotator(roll=0.0, pitch=LOOK_DOWN_DEG, yaw=yaw))
    yield SETTLE


def _one_press(p, player, wc, mine, label):
    """Press once; check it took exactly the candidate nearest AimPoint."""
    aim = p.get(wc, "AimPoint")
    order = _in_reach(p, player)
    gaps = [_dist(i.get_actor_location(), aim) for i in order]
    clear = len(order) < 2 or gaps[1] - gaps[0] > CLEAR_MARGIN_CM
    p.check(f"{label}: one candidate is clearly the nearest to the reticle's point",
            bool(order) and clear, ", ".join(f"{g:.0f} cm" for g in gaps))
    if not order:
        return None
    carried = list(p.get(wc, "Inventory"))
    yield from _press(p, wc)
    now = list(p.get(wc, "Inventory"))
    took = [i for i in now if i not in carried]
    p.check(f"{label}: the press takes exactly one item",
            len(took) == 1 and len(now) == len(carried) + 1,
            f"{len(took)} taken, {len(carried)} -> {len(now)} carried")
    # A taken level actor is destroyed and a fresh one of its class carried
    # (task A2, pickup.py): the nearest is gone, and the bag's new item is its kind.
    p.check(f"{label}: ...the one nearest the reticle's point",
            len(took) == 1 and took[0].get_class() == order[0].get_class()
            and not unreal.SystemLibrary.is_valid(order[0]),
            f"took {[i.get_name() for i in took]}, nearest {order[0].get_name()} "
            f"(still there: {unreal.SystemLibrary.is_valid(order[0])})")
    left = [i for i in mine if i is not order[0]]
    p.check(f"{label}: ...and the others stay on the ground",
            all(i.get_editor_property("Dropped") for i in left)
            and not unreal.SystemLibrary.is_valid(order[0]),
            f"{len(_on_ground(p, left))} of {len(left)} still Dropped")
    return order[0]


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    start = len(p.get(wc, "Inventory"))
    p.check("the bag has room for three more", start + 3 <= INVENTORY_SIZE,
            f"{start} of {INVENTORY_SIZE} carried")

    yaw = p.controller().get_control_rotation().yaw
    yield from _look(p, yaw)

    stray = _in_reach(p, player)
    here = player.get_actor_location()
    for i in stray:   # forage that happens to lie at the spawn: out of reach
        i.set_actor_location(here + unreal.Vector(0.0, 0.0, 5000.0), False, True)

    every = unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH))
    mine = [i for i in every
            if i.get_editor_property("Dropped") and i not in stray][:3]
    p.check("the level has three items lying in it to lay around the player",
            len(mine) == 3, f"{len(mine)} found")
    if len(mine) < 3:
        return

    # Laid in the order behind, side, ahead, so the item the first press must
    # take is not simply the first of the three.
    for item, turn in zip(mine, (180.0, 90.0, 0.0)):
        a = math.radians(yaw + turn)
        item.set_actor_location(
            here + unreal.Vector(RING_CM * math.cos(a), RING_CM * math.sin(a),
                                 -DOWN_CM), False, True)
    behind, _side, ahead = mine
    yield SETTLE
    p.check("all three lie within reach of the player",
            set(_in_reach(p, player)) == set(mine),
            f"{len(_in_reach(p, player))} in reach")

    first = yield from _one_press(p, player, wc, mine, "looking ahead")
    p.check("looking ahead, the item ahead is the one taken", first == ahead,
            first.get_name() if first else "nothing")

    yield from _look(p, yaw + 180.0)
    second = yield from _one_press(p, player, wc, mine, "turned round")
    p.check("turned round, the item that was behind is the one taken",
            second == behind, second.get_name() if second else "nothing")

    yield from _one_press(p, player, wc, mine, "the last one")
    p.check("three presses took the three items, one each (each level actor gone, a "
            "fresh one of its kind carried)",
            len(p.get(wc, "Inventory")) == start + 3
            and not any(unreal.SystemLibrary.is_valid(i) for i in mine),
            f"{len(p.get(wc, 'Inventory'))} carried")

    carried = len(p.get(wc, "Inventory"))
    yield from _press(p, wc)
    p.check("a press with nothing in reach takes nothing",
            len(p.get(wc, "Inventory")) == carried and not _in_reach(p, player),
            f"{len(p.get(wc, 'Inventory'))} carried")
