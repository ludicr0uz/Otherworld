"""Chopping a tree: the axe's blows on a trunk leave wood beside it.

The player is stood in front of the nearest tree with no forage round it,
facing the trunk, and swings by writing KnifeQueued (probe_knife.py says why).
With the axe in hand each blow must count, and the CHOPS_PER_WOOD-th must
leave one BP_Wood on the ground beside the trunk, Dropped, which E then takes
into the bag. The same blows with the knife must leave nothing: only an item
that Chops cuts a tree. Last, the fire key with the wood in hand must do
nothing to it.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import math
import os
import shutil

import unreal

from combat.chop_tuning import (
    CHOP_COUNT_VAR, CHOPS_PER_WOOD, CHOPS_VAR, WOOD_OUT_CM,
)
from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component.knife import KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_knife import _file, _held_name
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (WV.EquippedIndex, WV.NeedsRefresh, KNIFE_QUEUED_VAR, INTERACT_FORCED_VAR,
             FIRE_FORCED_VAR)]

AXE, KNIFE, WOOD = "BP_Axe_C", "BP_Knife_C", "BP_Wood_C"
CHEST_CM = 110.0          # where on the trunk the probe looks for it
STAND_BACK_CM = 75.0      # the player's middle, from the trunk's bark
CLEAR_CM = 500.0          # no forage this close to the tree chosen
VISIBILITY = unreal.TraceTypeQuery.TRACE_TYPE_QUERY1


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _trace(p, start, end, ignore=()):
    hit = unreal.SystemLibrary.line_trace_single(
        p.world(), start, end, VISIBILITY, False, list(ignore),
        unreal.DrawDebugTrace.NONE, True)
    return hit.to_tuple() if hit else None


def _flat(v):
    return math.hypot(v.x, v.y)


def _items(p, name=None):
    cls = unreal.load_object(None, ITEM_CLASS_PATH)
    found = unreal.GameplayStatics.get_all_actors_of_class(p.world(), cls)
    return [a for a in found if name is None or a.get_class().get_name() == name]


def _trees(p):
    """Every tree as (component, instance index, where it stands)."""
    out = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Actor):
        for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            if comp.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION:
                continue
            for i in range(comp.get_instance_count()):
                out.append((comp, i, comp.get_instance_transform(i, True).translation))
    return out


def _stand(p, player, base):
    """A place to stand facing the trunk at ``base``: (where, yaw, the bark
    in front, the ground there), or None if no side of it is clear."""
    for deg in range(0, 360, 45):
        side = unreal.Vector(math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0)
        far = base + side * 300.0
        floor = _trace(p, far + unreal.Vector(0, 0, 200.0), far - unreal.Vector(0, 0, 400.0),
                       [player])
        if floor is None or isinstance(floor[10], unreal.InstancedStaticMeshComponent):
            continue
        ground = floor[4].z
        chest = unreal.Vector(far.x, far.y, ground + CHEST_CM)
        bark = _trace(p, chest, unreal.Vector(base.x, base.y, chest.z), [player])
        if bark is None or not isinstance(bark[10], unreal.InstancedStaticMeshComponent):
            continue
        half = player.get_editor_property("capsule_component").get_scaled_capsule_half_height()
        at = bark[4] + side * STAND_BACK_CM
        at.z = ground + half + 5.0
        return at, deg + 180.0, bark, ground
    return None


def _swing(p, wc):
    p.set(wc, KNIFE_QUEUED_VAR, True)
    yield lambda: not p.get(wc, KNIFE_QUEUED_VAR)
    yield lambda: not p.get(wc, KNIFE_PENDING_VAR)
    yield 0.02


def _equip(p, wc, name):
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.set(wc, "EquippedIndex", bag.index(name))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: _held_name(p, wc) == name
    yield 0.05


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    flags = {i.get_class().get_name(): bool(p.get(i, CHOPS_VAR))
             for i in p.get(wc, "Inventory")}
    p.check("of what the player is issued, only the axe Chops",
            AXE in bag and flags == {n: n == AXE for n in bag}, str(flags))
    if AXE not in bag:
        return

    lying = [a.get_actor_location() for a in _items(p) if p.get(a, "Dropped")]
    here = player.get_actor_location()
    spot = None
    for comp, index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length()):
        if any(_flat(at - base) < CLEAR_CM for at in lying):
            continue
        spot = _stand(p, player, base)
        if spot:
            break
    p.check("the level has a tree to stand in front of", spot is not None)
    if spot is None:
        return
    at, yaw, bark, ground = spot
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    player.set_actor_location_and_rotation(at, turn, False, True)
    player.get_controller().set_control_rotation(turn)
    yield 0.3
    player.set_actor_location_and_rotation(at, turn, False, True)

    yield from _equip(p, wc, AXE)
    p.check("there is no wood in the world before a blow", not _items(p, WOOD))
    for n in range(1, CHOPS_PER_WOOD):
        yield from _swing(p, wc)
        p.check(f"axe blow {n} on the trunk is counted, and leaves no wood yet",
                p.get(wc, CHOP_COUNT_VAR) == n and not _items(p, WOOD),
                f"count {p.get(wc, CHOP_COUNT_VAR)}, wood {len(_items(p, WOOD))}")
    yield from _swing(p, wc)
    wood = _items(p, WOOD)
    p.check(f"blow {CHOPS_PER_WOOD} leaves one piece of wood, and the count starts over",
            len(wood) == 1 and p.get(wc, CHOP_COUNT_VAR) == 0,
            f"wood {len(wood)}, count {p.get(wc, CHOP_COUNT_VAR)}")
    if len(wood) != 1:
        return
    log = wood[0]
    where = log.get_actor_location()
    off = _flat(where - bark[4])
    # The cut is where the blow's 25 cm sphere touched the bark, a little off
    # the point this probe's line found.
    p.check(f"...beside the tree: about {WOOD_OUT_CM:.0f} cm from the cut, on the ground",
            abs(off - WOOD_OUT_CM) < 30.0 and abs(where.z - ground) < 40.0,
            f"{off:.1f} cm from the cut, {where.z - ground:.1f} cm above the ground")
    p.check("...not under the player's feet",
            _flat(where - player.get_actor_location()) > 30.0,
            f"{_flat(where - player.get_actor_location()):.1f} cm from the player")
    # The log's length is the item's +Z (it is held on end): flat is Z level.
    p.check("...laid flat, not standing on its end",
            abs(log.get_actor_up_vector().z) < 0.05, f"{log.get_actor_up_vector()}")
    p.check("...lying there to be picked up: Dropped, shown, named Wood, with its icon",
            p.get(log, "Dropped") and not log.get_editor_property("hidden")
            and str(p.get(log, "DisplayName")) == "Wood" and p.get(log, "Icon") is not None,
            f"dropped {p.get(log, 'Dropped')} icon {p.get(log, 'Icon')}")

    yield from _equip(p, wc, KNIFE)
    for _ in range(CHOPS_PER_WOOD):
        yield from _swing(p, wc)
    p.check("the knife's blows on the same trunk cut nothing",
            len(_items(p, WOOD)) == 1 and p.get(wc, CHOP_COUNT_VAR) == 0,
            f"wood {len(_items(p, WOOD))}, count {p.get(wc, CHOP_COUNT_VAR)}")

    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check("E takes the wood into the bag",
            bag.count(WOOD) == 1 and not p.get(log, "Dropped"), str(bag))
    if WOOD not in bag:
        return

    yield from _equip(p, wc, WOOD)
    p.set(wc, FIRE_FORCED_VAR, True)
    yield 0.1
    p.set(wc, FIRE_FORCED_VAR, False)
    yield 0.1
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check("the fire key with the wood in hand spends nothing and cuts nothing",
            p.get(wc, "Held") == log and bag.count(WOOD) == 1
            and len(_items(p, WOOD)) == 1, str(bag))
