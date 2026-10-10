"""An item sits in the hand where its Grip component says (combat/grip_handle.py).

Every item the player starts with is equipped in turn: it rests under the
grip socket at the inverse of its Grip's relative transform, which for a grip
nobody moved is the build's solved GripLocation, so the game looks as it did
before the component existed.

Then the positive case: the knife's Grip is moved 2 cm on the live item, as
moving it in the Blueprint editor moves it on every item spawned after, and
the next equip seats the knife 2 cm from where it was. Nothing is rebuilt, and
GripLocation, which the game no longer reads, has not changed.
"""

SYSTEMS = ('weapons',)

import unreal

from combat.grip_handle import GRIP
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh)]

NEAR_CM = 0.05
MOVE_CM = 2.0


def _rel(item):
    """A copy: the struct read back is a view that later reads overwrite."""
    v = item.root_component.get_editor_property("relative_location")
    return unreal.Vector(v.x, v.y, v.z)


def _grip(item):
    return item.find_component_by_tag(unreal.SceneComponent, GRIP)


def _seat(item):
    """Where the item's Grip puts it under the socket."""
    return _grip(item).get_relative_transform().inverse().translation


def _equip(p, wc, item):
    p.set(wc, "EquippedIndex", list(p.get(wc, "Inventory")).index(item))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item and not p.get(wc, "NeedsRefresh")
    yield 0.1


def probe(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    items = [i for i in p.get(wc, "Inventory") if i]
    p.check("the player carries items to hold", len(items) >= 3, str(len(items)))
    knife = None
    for item in items:
        name = str(item.get_editor_property("DisplayName"))
        if name == "Knife":
            knife = item
        if _grip(item) is None:
            p.check(f"{name}: has a Grip", False)
            continue
        yield from _equip(p, wc, item)
        got, want = _rel(item), _seat(item)
        p.check(f"{name}: sits in the hand where its Grip says",
                (got - want).length() < NEAR_CM, f"{got} for {want}")
        seed = item.get_editor_property("GripLocation")
        p.check(f"{name}: an unmoved Grip is the solved grip",
                (want - seed).length() < NEAR_CM, f"{want} for {seed}")
    p.check("the player carries the knife", knife is not None)
    if knife is None:
        return

    yield from _equip(p, wc, knife)
    before = _rel(knife)
    grip = _grip(knife)
    at = grip.get_editor_property("relative_location")
    grip.set_editor_property("relative_location",
                             unreal.Vector(at.x + MOVE_CM, at.y, at.z))
    other = next(i for i in items if i != knife)
    yield from _equip(p, wc, other)
    yield from _equip(p, wc, knife)
    after = _rel(knife)
    p.check("a Grip moved 2 cm seats the knife 2 cm away at the next equip",
            abs((after - before).length() - MOVE_CM) < NEAR_CM,
            f"{before} -> {after}")
    p.check("...where the moved Grip says", (after - _seat(knife)).length() < NEAR_CM,
            f"{after} for {_seat(knife)}")
    seed = knife.get_editor_property("GripLocation")
    p.check("...and not where GripLocation, the seed, still says",
            (after - seed).length() > MOVE_CM - NEAR_CM, f"{after} against {seed}")
