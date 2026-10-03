"""Clothing by the mouse: a slot's garment dragged onto the worn grid.

    every Tick, after the take-off: WearRequest a slot code (the I panel's
    drag asks, graphics_menu/inv_drag.py):
        WearItem = SlotItems[code], WearRequest = NOT_CLOTHING
        WearItem valid: WearSlot = its ClothingSlot; a slot (a garment) ->
            Inventory.RemoveItem(WearItem)
            what Worn[WearSlot] holds (if anything) -> Inventory, in the slot
                WearItem is leaving                               (a swap)
            Worn[WearSlot] = WearItem (grown to fit), WearItem hidden and
            UNPLACED, NeedsRefresh

The fire key's wear (wear.py) takes the garment taken of the hand; this one
takes it from wherever it is carried, the hand included: taken of Inventory it
is taken of its slot, the slot sync finds the hand empty and the refresh
empties Held. The gate reads the stored WearSlot, not ClothingSlot, so
verify/wear.py still finds one Branch on Held.ClothingSlot.
"""

from uebp.graph import _set, out, then
from combat.slot_tuning import SLOT_VAR, UNPLACED
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, WEAR_ITEM_VAR, WEAR_REQUEST_VAR, WORN_VAR,
)
from combat.paths import ITEM_CLASS_PATH
from uebp.g import _G
from combat.weapon_component.slot_nodes import slot_at
from combat.weapon_component.wear import WEAR_SLOT_VAR, _worn_at
from uebp.nodes.actor import FN_SET_HIDDEN
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_REMOVE_ITEM, FN_ARR_SET, FN_ARR_VALID
from uebp.nodes.math import FN_GE_II
from uebp.nodes.system import FN_IS_VALID

SLOT_ITEMS = "SlotItems"


def _author_wear_request(ed, in_execs):
    """Serve WearRequest (see the module docstring). Returns the exits."""
    g = _G(ed, ITEM_CLASS_PATH)
    asked = g.call(FN_GE_II, A=g.get(WEAR_REQUEST_VAR), B=0)
    serve, idle = g.branch(out(asked), in_execs)
    code = g.get(WEAR_REQUEST_VAR)
    inside = g.call(FN_ARR_VALID, TargetArray=g.get(SLOT_ITEMS), IndexToTest=code)
    known, wild = g.branch(out(inside), [serve])
    # Stored before the request is lowered: every read below is of the copy.
    flow = g.put(WEAR_ITEM_VAR, slot_at(g, code), [known])
    flow = g.put(WEAR_REQUEST_VAR, str(NOT_CLOTHING), [flow, wild])
    item = g.get(WEAR_ITEM_VAR)
    there, nothing = g.branch(out(g.call(FN_IS_VALID, Object=item)), [flow])
    flow = g.put(WEAR_SLOT_VAR, g.iget(item, CLOTHING_SLOT_VAR), [there])
    slot = g.get(WEAR_SLOT_VAR)
    garment, other = g.branch(out(g.call(FN_GE_II, A=slot, B=0)), [flow])
    taken = g.call(FN_ARR_REMOVE_ITEM, [garment], TargetArray=g.get("Inventory"), Item=item)

    # The slot already holds one: it comes off into the slot this one leaves.
    valid, old = _worn_at(g, slot)
    full, empty = g.branch(valid, [then(taken)])
    worn, bare = g.branch(out(g.call(FN_IS_VALID, Object=old)), [full])
    back = g.call(FN_ARR_ADD, [worn], TargetArray=g.get("Inventory"), NewItem=old)
    swapped = g.iput(old, SLOT_VAR, g.iget(item, SLOT_VAR), [then(back)])

    put_on = g.call(FN_ARR_SET, [swapped, bare, empty],
                    TargetArray=g.get(WORN_VAR), Index=slot, Item=item)
    _set(put_on, "bSizeToFit", "true")
    hide = g.call(FN_SET_HIDDEN, [then(put_on)], self=item)
    _set(hide, "bNewHidden", "true")
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [then(hide)])
    flow = g.put("NeedsRefresh", "true", [flow])
    ed.add_comment_to_nodes(
        f"{WEAR_REQUEST_VAR}: the I panel's drag of a slot's item onto the worn grid. "
        "A garment leaves Inventory for Worn[its ClothingSlot], hidden; one already "
        "worn there takes the slot it left (wear_drag.py).", g.made)
    return [flow, idle, nothing, other]
