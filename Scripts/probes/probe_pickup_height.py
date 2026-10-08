"""The pick-up's reach has a height: an item close by on the map but well
above or below the player is not taken (weapon_component/interact.py,
INTERACT_HEIGHT).

One of the level's items is put 40 cm out and 200 cm above the player's
middle (inside INTERACT_RADIUS as a sphere, outside INTERACT_HEIGHT): a press
must leave it. The same item 200 cm below is left too. Put 120 cm out and
60 cm below, about knee height, the next press must take it: the positive
case, so the gate is shown to open. Its physics is switched off so it stays
where it is put. Any profile on disk is set aside and put back, as in
probe_pickup.py.
"""

import os
import shutil

import unreal

from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import INTERACT_RADIUS
from combat.weapon_component.interact import INTERACT_FORCED_VAR, INTERACT_HEIGHT
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, INTERACT_FORCED_VAR)]


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _press(p, wc):
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05


def _put(item, at):
    for c in item.get_components_by_class(unreal.PrimitiveComponent):
        c.set_simulate_physics(False)
    item.set_actor_location(at, False, True)


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    here = player.get_actor_location()
    every = unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH))
    loose = [i for i in every if i.get_editor_property("Dropped")]
    p.check("the level has an item lying in it", bool(loose), f"{len(loose)} found")
    if not loose:
        return
    item, rest = loose[0], loose[1:]
    for i in rest:   # anything else near the spawn: well out of reach
        if (i.get_actor_location() - here).length() < 3.0 * INTERACT_RADIUS:
            _put(i, here + unreal.Vector(0.0, 0.0, 5000.0))

    for label, dz in (("above", 200.0), ("below", -200.0)):
        _put(item, here + unreal.Vector(40.0, 0.0, dz))
        yield 0.05
        gap = (item.get_actor_location() - player.get_actor_location())
        carried = len(p.get(wc, "Inventory"))
        yield from _press(p, wc)
        p.check(f"an item {abs(dz):.0f} cm {label} the player's middle (over "
                f"{INTERACT_HEIGHT:.0f}) is not taken",
                item.get_editor_property("Dropped")
                and len(p.get(wc, "Inventory")) == carried
                and gap.length() < INTERACT_RADIUS and abs(gap.z) > INTERACT_HEIGHT,
                f"3D {gap.length():.0f} cm, dz {gap.z:.0f} cm, "
                f"Dropped={item.get_editor_property('Dropped')}")

    _put(item, here + unreal.Vector(120.0, 0.0, -60.0))
    yield 0.05
    carried = len(p.get(wc, "Inventory"))
    yield from _press(p, wc)
    # A taken level actor is destroyed and a fresh one of its class carried
    # (task A2, pickup.py): the reference held here is gone.
    p.check("the same item at knee height 120 cm out is taken",
            not unreal.SystemLibrary.is_valid(item)
            and len(p.get(wc, "Inventory")) == carried + 1,
            f"{carried} -> {len(p.get(wc, 'Inventory'))} carried, "
            f"the level actor valid {unreal.SystemLibrary.is_valid(item)}")
