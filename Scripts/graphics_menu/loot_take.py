"""Taking the selected item out of a body and into the player's bag.

    cls = LootTarget.Loot[LootSel]
    spawn cls at the pawn, cast to BP_WeaponItem, Dropped = false,
    Inventory += it, NeedsRefresh                       (as dev_guns does)
    every body array (Loot, LootNames, LootIcons, LootTints) .RemoveIndex(LootSel)

The item is spawned only now: a body carries classes, not hidden actors
(loot/roll.py). The caller has already checked there is room (the weapon
component's HasRoom), so the slot sync finds the new item a bag slot, or
the hand. The held item stays held, as with a pick-up.
"""

from combat.graph import BEL, _connect, _loose_pin, _palette, _pin, _set
from uebp.graph import out
from combat.nodes import (
    FN_ARR_ADD, FN_ARR_GET, FN_ARR_REMOVE, FN_GET_TRANSFORM, NODE_CAST_ITEM, NODE_SPAWN,
)
from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.dev_guns import _call, _get, _setter
from graphics_menu.loot_consts import LOOT_SEL_VAR, LOOT_TARGET_VAR
from loot.consts import BODY_ARRAYS, LOOT_VAR


def _body(ed, var, made):
    """LootTarget's array ``var``."""
    return _get(ed, var, made, HEALTH_CLASS_PATH, _get(ed, LOOT_TARGET_VAR, made))


def author_take(ed, wc, pawn_out, in_execs, made):
    """The take (see the module docstring). ``wc`` is the player's cast weapon
    component. Returns the exec tails."""
    sel = _get(ed, LOOT_SEL_VAR, made)
    cls = _call(ed, FN_ARR_GET, made, TargetArray=_body(ed, LOOT_VAR, made), Index=sel)
    where = _call(ed, FN_GET_TRANSFORM, made, self=pawn_out)
    spawn = _palette(ed, NODE_SPAWN)
    made.append(spawn)
    _connect(_pin(cls, "Item", is_input=False), _pin(spawn, "Class"))
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    for e in in_execs:
        _connect(e, _pin(spawn, "execute"))
    cast = _palette(ed, NODE_CAST_ITEM)
    made.append(cast)
    _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(spawn), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    flow = _setter(ed, "Dropped", "false", [BEL.find_then_pin(cast)], made, ITEM_CLASS_PATH, item)
    add = _call(ed, FN_ARR_ADD, made,
                TargetArray=_get(ed, "Inventory", made,
                                 WEAPON_COMP_CLASS_PATH, wc))
    _connect(item, _loose_pin(add, "NewItem"))
    _connect(flow, _pin(add, "execute"))
    flow = _setter(ed, "NeedsRefresh", "true", [BEL.find_then_pin(add)],
                   made, WEAPON_COMP_CLASS_PATH, wc)
    for var in BODY_ARRAYS:
        gone = _call(ed, FN_ARR_REMOVE, made,
                     TargetArray=_body(ed, var, made),
                     IndexToRemove=_get(ed, LOOT_SEL_VAR, made))
        _connect(flow, _pin(gone, "execute"))
        flow = BEL.find_then_pin(gone)
    return [flow, _pin(cast, "CastFailed", is_input=False)]
