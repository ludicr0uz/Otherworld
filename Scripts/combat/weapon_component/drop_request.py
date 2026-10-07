"""An item set down on the ground: dragged out of the inventory, or the hand's
with the drop key.

    where the keys are (_author_drop_keys):
        the drop key, something in hand -> AskDrop(HAND)
        DropForced >= 0 (a probe)       -> AskDrop(DropForced), lowered
    AskDrop is a Server event (asks.py, task M23): it raises DropRequest on
    the server's copy, which serves it (_author_drop_request), so what is set
    down is the server's item actor. Lying there Dropped, the item's own Tick
    makes it a replicated actor (item_world.py) and every client is sent it;
    the owning client's bag loses it with the next record. A client sets
    nothing down itself. In single player the ask is a plain call.

    every Tick, with authority, before the slots are served: DropRequest a
    slot code, or SLOT_COUNT + a worn slot (the I panel's drag, released
    outside the inventory: graphics_menu/inv_drag.py asks):
        DropWant = DropRequest, DropRequest = NO_REQUEST, DropItem = None
        a slot code:  DropItem = SlotItems[code]; valid ->
                          Inventory.RemoveItem(DropItem)
        a worn slot:  DropItem = Worn[slot]; valid -> Worn[slot] = None
        DropItem valid: set down as the G drop sets the held item down
            (inventory._author_set_down: Dropped, detached, shown, on the
            ground ahead), its Slot UNPLACED, NeedsRefresh

The item is taken from wherever it is carried or worn, the hand included
(the drop key's): out of Inventory it is out of its slot, the slot sync
finds the hand empty and the refresh empties Held, as for a garment dragged
onto the worn grid (wear_drag.py). The item is stored before anything is
removed: SlotItems and Worn are read once. Worn is the server's (wear.py), so
a client's worn garment dragged out is set down by the server like any item.
"""

from uebp.graph import out, then
from combat.ask_consts import ASK_DROP, FROM_PARAM
from combat.record_vars import NO_ASK, DropForced
from combat.slot_tuning import (
    DROP_ITEM_VAR, DROP_REQUEST_VAR, DROP_WANT_VAR, HAND, NO_REQUEST, SLOT_COUNT, SLOT_VAR,
    UNPLACED,
)
from combat.wear_tuning import WORN_VAR
from combat.paths import ITEM_CLASS_PATH
from uebp.g import _G
from combat.weapon_component.inventory import _author_set_down
from combat.weapon_component.slot_moves import _ask
from combat.weapon_component.slot_nodes import slot_at, valid
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.array import FN_ARR_GET, FN_ARR_REMOVE_ITEM, FN_ARR_SET, FN_ARR_VALID
from uebp.nodes.math import FN_GE_II, FN_LESS_II, FN_SUB_II
from combat.weapon_component import vars as WV


def _author_drop_keys(ed, pressed, in_execs):
    """Where the keys are: the drop key with something in hand (``pressed``)
    asks the server to set the hand's item down, and a probe's DropForced
    asks for a slot's. Returns the exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    hit, miss = g.branch(pressed, in_execs)
    flow = [_ask(g, ASK_DROP, [hit], **{FROM_PARAM: HAND}), miss]
    forced, none = g.branch(out(g.call(FN_GE_II, A=g.get(DropForced), B=0)), flow)
    asked = _ask(g, ASK_DROP, [forced], **{FROM_PARAM: g.get(DropForced)})
    flow = [g.put(DropForced, str(NO_ASK), [asked]), none]
    ed.add_comment_to_nodes(
        f"The drop key asks the server to set the hand's item down ({ASK_DROP}, a "
        "Server event: drop_request.py); DropForced is a probe's hand on the same "
        "ask.", g.made)
    return flow


def _author_drop_request(ed, in_execs):
    """Serve DropRequest (see the module docstring). Returns the exits."""
    g = _G(ed, ITEM_CLASS_PATH)
    asked = g.call(FN_GE_II, A=g.get(DROP_REQUEST_VAR), B=0)
    serve, idle = g.branch(out(asked), in_execs)
    # Copied before the request is lowered: every read below is of the copy.
    flow = g.put(DROP_WANT_VAR, g.get(DROP_REQUEST_VAR), [serve])
    flow = g.put(DROP_REQUEST_VAR, str(NO_REQUEST), [flow])
    flow = g.put(DROP_ITEM_VAR, None, [flow])
    want = g.get(DROP_WANT_VAR)
    carried, worn = g.branch(out(g.call(FN_LESS_II, A=want, B=SLOT_COUNT)), [flow])

    # A slot's item: out of Inventory, so out of its slot.
    flow = g.put(DROP_ITEM_VAR, slot_at(g, want), [carried])
    there, empty = g.branch(valid(g, g.get(DROP_ITEM_VAR)), [flow])
    taken = g.call(FN_ARR_REMOVE_ITEM, [there], TargetArray=g.get(WV.Inventory),
                   Item=g.get(DROP_ITEM_VAR))

    # A worn garment: out of Worn (Item left unconnected: Worn[slot] = None).
    at = out(g.call(FN_SUB_II, A=want, B=SLOT_COUNT))
    known, wild = g.branch(out(g.call(FN_ARR_VALID, TargetArray=g.get(WORN_VAR),
                                      IndexToTest=at)), [worn])
    got = g.call(FN_ARR_GET, TargetArray=g.get(WORN_VAR), Index=at)
    flow = g.put(DROP_ITEM_VAR, out(got, "Item"), [known])
    dressed, bare = g.branch(valid(g, g.get(DROP_ITEM_VAR)), [flow])
    off = g.call(FN_ARR_SET, [dressed], TargetArray=g.get(WORN_VAR), Index=at)

    # Either way it is one exec in: a Branch that is always taken joins them.
    item = g.get(DROP_ITEM_VAR)
    go, gone = g.branch(valid(g, item), [then(taken), then(off)])
    owner = out(g.call(FN_GET_OWNER))
    on_ground, in_air = _author_set_down(ed, item, owner, go, g.keep)
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [on_ground, in_air])
    flow = g.put(WV.NeedsRefresh, "true", [flow])
    ed.add_comment_to_nodes(
        f"{DROP_REQUEST_VAR}, served with authority: the I panel's drag of an item "
        "out of the inventory, or the drop key's of the hand's. A slot's item "
        "leaves Inventory, a worn garment leaves Worn, and it is set down on the "
        "ground ahead, Dropped: a replicated actor from its next Tick "
        "(drop_request.py, item_world.py).", g.made)
    return [flow, idle, empty, wild, bare, gone]
