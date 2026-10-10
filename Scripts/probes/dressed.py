"""A probe's player with a garment on: picked up and worn the way a player
does it, and how its component under the body then stands.

    put_on(p, player, wc, "Jacket")   the level's test garment of that name
                        (Lvl_Forest_200m has one of each), or one spawned
                        where none lies, laid in front of the player, taken
                        with E (InteractForced) and worn with the fire key
                        (FireForced). Returns the worn item, or None
    part(player, "Jacket")   the component under the body that draws it
                        (Torso, Legs, Feet: weapon_component/wear_draw.py)
    drawn(part)         it has its garment's mesh and shows
    still(p, held, stop)    the level's wanderers rooted where they stand, and
                        walking again

A probe that calls put_on adds WRITABLE below to its own. The pick-up, the
hold and the press are probe_clothing's, which imports them from here.
"""

SYSTEMS = ('clothing',)

import math

import unreal

from clothing.specs import GARMENTS
from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH
from combat.tuning import INTERACT_RADIUS
from combat.wear_tuning import NOT_CLOTHING, WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (WV.EquippedIndex, WV.NeedsRefresh, INTERACT_FORCED_VAR, FIRE_FORCED_VAR)]

RING_CM = 150.0
DOWN_CM = 60.0
LOOK_DOWN_DEG = -35.0
SETTLE = 0.2


def bag(p, wc):
    return list(p.get(wc, "Inventory"))


def still(p, held, stop):
    """The level's wanderers reach the player about six seconds in, and a dead
    player sheds the bag a probe is working. They are rooted where they
    stand while it runs (no movement mode) and walk again as it ends: the
    probes after this one in a launch share them."""
    if stop:
        ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
        held.extend(c.get_controlled_pawn() for c in ctrls
                    if c.get_class().get_name().startswith("BP_ForestWandererAI")
                    and c.get_controlled_pawn() is not None)
    for pawn in held:
        if unreal.SystemLibrary.is_valid(pawn):
            move = pawn.get_movement_component()
            if stop:
                move.disable_movement()
            else:
                move.set_movement_mode(unreal.MovementMode.MOVE_WALKING)


def pick_up(p, player, wc, item, yaw):
    """Lay ``item`` 150 cm ahead and press E. The take of a level actor destroys
    it and puts a fresh one of its class in the bag (task A2, pickup.py):
    returns that one, or None if nothing of its kind arrived."""
    a = math.radians(yaw)
    here = player.get_actor_location()
    before = list(bag(p, wc))
    item.set_actor_location(
        here + unreal.Vector(RING_CM * math.cos(a), RING_CM * math.sin(a), -DOWN_CM),
        False, True)
    yield SETTLE
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05
    fresh = [b for b in bag(p, wc) if b not in before and b.get_class() == item.get_class()]
    return fresh[0] if fresh and not unreal.SystemLibrary.is_valid(item) else None


def hold(p, wc, item):
    p.set(wc, "EquippedIndex", bag(p, wc).index(item))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    yield 0.05


def fire(p, wc, item):
    """One press on ``item`` in hand. FireForced is a held key that counts as a
    press on every frame it is up, so it comes down on the first frame the
    item has left the bag: held longer, it wears what slides into the hand."""
    p.set(wc, FIRE_FORCED_VAR, True)
    yield lambda: item not in bag(p, wc)
    p.set(wc, FIRE_FORCED_VAR, False)
    yield 0.1


def _garment(display):
    return next(g for g in GARMENTS if g.display == display)


def put_on(p, player, wc, display):
    """Pick up the garment called ``display`` and wear it. The view is put
    back as it was. Returns the item now in Worn, or None."""
    spec = _garment(display)
    every = unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH))
    here = player.get_actor_location()
    item = next((a for a in every if a.get_editor_property("Dropped")
                 and a.get_editor_property("DisplayName") == display), None)
    for a in every:   # whatever else lies in reach: E would take it instead
        if a is not item and a.get_editor_property("Dropped") \
                and (a.get_actor_location() - here).length() < INTERACT_RADIUS * 2:
            a.set_actor_location(a.get_actor_location() + unreal.Vector(0.0, 0.0, 5000.0),
                                 False, True)
    if item is None:
        item = unreal.OtherworldLoadLibrary.spawn_actor_at(
            p.world(), unreal.load_class(None, spec.class_path),
            unreal.Transform(here + unreal.Vector(0.0, 0.0, 300.0),
                             unreal.Rotator(0.0, 0.0, 0.0), unreal.Vector(1.0, 1.0, 1.0)))
        if item is None:
            return None
        yield SETTLE
    view = p.controller().get_control_rotation()
    p.controller().set_control_rotation(
        unreal.Rotator(roll=0.0, pitch=LOOK_DOWN_DEG, yaw=view.yaw))
    yield SETTLE
    got = yield from pick_up(p, player, wc, item, view.yaw)
    if got is None and unreal.SystemLibrary.is_valid(item) and item in bag(p, wc):
        got = item          # not a level actor: the take keeps the very actor
    p.controller().set_control_rotation(view)
    if got is None:
        return None
    yield from hold(p, wc, got)
    yield from fire(p, wc, got)
    worn = list(p.get(wc, WORN_VAR))
    slot = spec.slot_index
    assert got.get_editor_property("ClothingSlot") != NOT_CLOTHING
    return got if slot < len(worn) and worn[slot] == got else None


def part(player, display):
    """The component under the body that draws the garment called ``display``."""
    name = _garment(display).worn[0]
    return next((c for c in player.get_components_by_class(unreal.SkeletalMeshComponent)
                 if c.get_name() == name), None)


def drawn(comp, display):
    """``comp`` has the garment's mesh and shows (to someone: OwnerNoSee is
    the per-view hide, and is read apart from this)."""
    mesh = comp.get_skeletal_mesh_asset() if comp else None
    return (mesh is not None
            and mesh.get_path_name().split(".")[0] == _garment(display).worn[1]
            and comp.is_visible() and not comp.get_editor_property("hidden_in_game"))
