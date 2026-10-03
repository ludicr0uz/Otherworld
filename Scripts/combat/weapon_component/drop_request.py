"""An item dragged out of the inventory: set down on the ground.

    every Tick, after the wear request: DropRequest a slot code, or
    SLOT_COUNT + a worn slot (the I panel's drag, released outside the
    inventory: graphics_menu/inv_drag.py asks):
        DropWant = DropRequest, DropRequest = NO_REQUEST, DropItem = None
        a slot code:  DropItem = SlotItems[code]; valid ->
                          Inventory.RemoveItem(DropItem)
        a worn slot:  DropItem = Worn[slot]; valid -> Worn[slot] = None
        DropItem valid: set down as the G drop sets the held item down
            (inventory._author_set_down: Dropped, detached, shown, on the
            ground ahead), its Slot UNPLACED, NeedsRefresh

The G drop takes the hand's item; this one takes it from wherever it is
carried or worn, the hand included: out of Inventory it is out of its slot,
the slot sync finds the hand empty and the refresh empties Held, as for a
garment dragged onto the worn grid (wear_drag.py). The item is stored before
anything is removed: SlotItems and Worn are read once.
"""

from uebp.graph import out, then
from combat.slot_tuning import (
    DROP_ITEM_VAR, DROP_REQUEST_VAR, DROP_WANT_VAR, NO_REQUEST, SLOT_COUNT, SLOT_VAR, UNPLACED,
)
from combat.wear_tuning import WORN_VAR
from combat.paths import ITEM_CLASS_PATH
from uebp.g import _G
from combat.weapon_component.inventory import _author_set_down
from combat.weapon_component.slot_nodes import slot_at, valid
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.array import FN_ARR_GET, FN_ARR_REMOVE_ITEM, FN_ARR_SET, FN_ARR_VALID
from uebp.nodes.math import FN_GE_II, FN_LESS_II, FN_SUB_II
from combat.weapon_component import vars as WV


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
        f"{DROP_REQUEST_VAR}: the I panel's drag of an item out of the inventory. "
        "A slot's item leaves Inventory, a worn garment leaves Worn, and it is set "
        "down on the ground ahead as the drop key sets the held one down "
        "(drop_request.py).", g.made)
    return [flow, idle, empty, wild, bare, gone]
