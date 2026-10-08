"""AskLootTake(Body, Index, Want): the loot window's take, out of a body and
into the bag. The HUD calls it with the body searched, the caret's row and
the class the window showed there.

    the owner alive, Body valid and within LOOT_TAKE_REACH_CM of the owner
    on this machine, HasRoom (a bag slot, or empty hands: the slot sync's),
    Body.Loot[Index] there and still the class asked for:
        spawn Loot[Index] at the owner, cast to BP_WeaponItem, Dropped = false,
        Inventory += it, NeedsRefresh
        every body array (Loot, LootNames, LootIcons, LootTints)
            .RemoveIndex(Index)

A reliable Server event (task M23): the owning client's window asks, and the
server's copy of the body is the one searched. Two players reaching for one
row: the first ask takes it, and the second finds the row gone, or another
item moved up into it, which is not what it asked for (Want), so it takes
nothing. The body's arrays replicate, so the loser's window shows the row
gone, and nothing reached its bag: a client's bag is the server's record. In
single player the event is a plain call.

The item is spawned only now: a body carries classes, not hidden actors
(loot/roll.py). The slot sync finds the new item a bag slot, or the hand; the
held item stays held, as with a pick-up. Every refusal is the component's:
the window only shows whether the bag is full.
"""

from net.guard import author_guard
from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
from uebp.g import _G
from uebp.net import server_event
from uebp.vars import INT, cls, obj
from combat.ask_consts import ASK_LOOT_TAKE, BODY_PARAM, INDEX_PARAM, WANT_PARAM
from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH
from combat.slot_tuning import HAS_ROOM_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from loot.consts import BODY_ARRAYS, LOOT_TAKE_REACH_CM, LOOT_VAR
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER, FN_GET_TRANSFORM
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_GET, FN_ARR_REMOVE, FN_ARR_VALID
from uebp.nodes.math import FN_DISTANCE, FN_EQ_CC, FN_LE_FF, FN_NOT
from uebp.nodes.palette import NODE_CAST_ITEM, NODE_SPAWN
from uebp.nodes.system import FN_IS_VALID
from combat import item_vars as IV
from combat.weapon_component import vars as WV


# What a body's Loot holds: class-of-Actor (loot/roll.py), so Want is too.
ACTOR_CLASS_PATH = "/Script/Engine.Actor"


def author_loot_take(ed):
    """The event (see the module docstring)."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(server_event(ed, ASK_LOOT_TAKE, [(BODY_PARAM, obj(HEALTH_CLASS_PATH)),
                                                    (INDEX_PARAM, INT),
                                                    (WANT_PARAM, cls(ACTOR_CLASS_PATH))]))
    body, index = out(event, BODY_PARAM), out(event, INDEX_PARAM)
    go, _refused = author_guard(g, ASK_LOOT_TAKE, [then(event)])
    alive, _ = g.branch(out(g.call(FN_NOT, A=g.get(OWNER_DEAD_VAR))), [go])
    there, _ = g.branch(out(g.call(FN_IS_VALID, Object=body)), [alive])
    # In reach on this machine: a client is not taken at its word.
    gap = g.call(FN_DISTANCE,
                 V1=out(g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER, self=body)))),
                 V2=out(g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))))
    near, _ = g.branch(out(g.call(FN_LE_FF, A=out(gap), B=str(LOOT_TAKE_REACH_CM))), [there])
    room, _ = g.branch(g.get(HAS_ROOM_VAR), [near])
    # A body may carry nothing: Loot[Index] of an empty array is not read.
    loot = g.iget(body, LOOT_VAR, HEALTH_CLASS_PATH)
    some, _ = g.branch(out(g.call(FN_ARR_VALID, TargetArray=loot, IndexToTest=index)), [room])
    # Still what the window showed: another player's take may have moved the
    # next row up into this one.
    kind = g.call(FN_ARR_GET, TargetArray=loot, Index=index)
    some, _ = g.branch(out(g.call(FN_EQ_CC, A=out(kind, "Item"), B=out(event, WANT_PARAM))),
                       [some])

    cls_at = g.call(FN_ARR_GET, TargetArray=loot, Index=index)
    where = g.call(FN_GET_TRANSFORM, self=out(g.call(FN_GET_OWNER)))
    spawn = g.keep(_palette(ed, NODE_SPAWN))
    _connect(out(cls_at, "Item"), _pin(spawn, "Class"))
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
        f"{ASK_LOOT_TAKE}: the loot window's take, a Server event. With the body in "
        "reach on this machine, room, and what was asked for still at that row of "
        "the body, the item is spawned into Inventory and leaves the body: of two "
        "players asking for one row, the first (loot_take.py).", g.made)
