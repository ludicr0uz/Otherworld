"""AskLootTake(Body, Index): the loot window's take, out of a body and into
the bag. The HUD calls it with the body searched and the caret's row.

    the owner alive, Body valid, HasRoom (a bag slot, or empty hands: the
    slot sync's), and Body.Loot[Index] there:
        spawn Loot[Index] at the owner, cast to BP_WeaponItem, Dropped = false,
        Inventory += it, NeedsRefresh
        every body array (Loot, LootNames, LootIcons, LootTints)
            .RemoveIndex(Index)

The item is spawned only now: a body carries classes, not hidden actors
(loot/roll.py). The slot sync finds the new item a bag slot, or the hand; the
held item stays held, as with a pick-up. Every refusal is the component's:
the window only shows whether the bag is full.
"""

from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
from uebp.g import _G
from uebp.net import custom_event
from uebp.vars import INT, obj
from combat.ask_consts import ASK_LOOT_TAKE, BODY_PARAM, INDEX_PARAM
from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH
from combat.slot_tuning import HAS_ROOM_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from loot.consts import BODY_ARRAYS, LOOT_VAR
from uebp.nodes.actor import FN_GET_OWNER, FN_GET_TRANSFORM
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_GET, FN_ARR_REMOVE, FN_ARR_VALID
from uebp.nodes.math import FN_NOT
from uebp.nodes.palette import NODE_CAST_ITEM, NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID
from combat import item_vars as IV
from combat.weapon_component import vars as WV


def author_loot_take(ed):
    """The event (see the module docstring)."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(custom_event(ed, ASK_LOOT_TAKE, [(BODY_PARAM, obj(HEALTH_CLASS_PATH)),
                                                    (INDEX_PARAM, INT)]))
    body, index = out(event, BODY_PARAM), out(event, INDEX_PARAM)
    alive, _ = g.branch(out(g.call(FN_NOT, A=g.get(OWNER_DEAD_VAR))), [then(event)])
    there, _ = g.branch(out(g.call(FN_IS_VALID, Object=body)), [alive])
    room, _ = g.branch(g.get(HAS_ROOM_VAR), [there])
    # A body may carry nothing: Loot[Index] of an empty array is not read.
    loot = g.iget(body, LOOT_VAR, HEALTH_CLASS_PATH)
    some, _ = g.branch(out(g.call(FN_ARR_VALID, TargetArray=loot, IndexToTest=index)), [room])

    cls = g.call(FN_ARR_GET, TargetArray=loot, Index=index)
    where = g.call(FN_GET_TRANSFORM, self=out(g.call(FN_GET_OWNER)))
    spawn = g.keep(_palette(ed, NODE_SPAWN))
    _connect(out(cls, "Item"), _pin(spawn, "Class"))
    _connect(out(where), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(some, _pin(spawn, "execute"))
    cast = g.keep(_palette(ed, NODE_CAST_ITEM))
    _connect(out(spawn), _pin(cast, "Object"))
    _connect(then(spawn), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    flow = g.iput(item, IV.Dropped, "false", [then(cast)])
    add = g.call(FN_ARR_ADD, [flow], TargetArray=g.get(WV.Inventory), NewItem=item)
    flow = g.put(WV.NeedsRefresh, "true", [then(add)])
    for var in BODY_ARRAYS:
        gone = g.call(FN_ARR_REMOVE, [flow], TargetArray=g.iget(body, var, HEALTH_CLASS_PATH),
                      IndexToRemove=index)
        flow = then(gone)
    ed.add_comment_to_nodes(
        f"{ASK_LOOT_TAKE}: the loot window's take. With room, and something at that "
        "row of the body, the item is spawned into Inventory and leaves the body "
        "(loot_take.py).", g.made)
