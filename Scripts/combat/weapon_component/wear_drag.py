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

The fire key's wear (wear.py) takes the garment out of the hand; this one
takes it from wherever it is carried, the hand included: out of Inventory it
is out of its slot, the slot sync finds the hand empty and the refresh
empties Held. The gate reads the stored WearSlot, not ClothingSlot, so
verify/wear.py still finds one Branch on Held.ClothingSlot.
"""

from combat.graph import BEL, _set
from combat.nodes import FN_ARR_ADD, FN_ARR_SET, FN_IS_VALID, FN_SET_HIDDEN
from combat.slot_tuning import SLOT_VAR, UNPLACED
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, WEAR_ITEM_VAR, WEAR_REQUEST_VAR, WORN_VAR,
)
from combat.weapon_component.common import _G
from combat.weapon_component.slot_nodes import slot_at
from combat.weapon_component.wear import FN_GE_II, WEAR_SLOT_VAR, _out, _worn_at

FN_ARR_REMOVE_ITEM = "/Script/Engine.KismetArrayLibrary.Array_RemoveItem"
FN_ARR_VALID = "/Script/Engine.KismetArrayLibrary.Array_IsValidIndex"
SLOT_ITEMS = "SlotItems"


def _author_wear_request(ed, in_execs, x0, y0):
    """Serve WearRequest (see the module docstring). Returns the exits."""
    g = _G(ed)
    asked = g.call(FN_GE_II, x0, y0 + 300, A=g.get(WEAR_REQUEST_VAR, x0 - 240, y0 + 300), B=0)
    serve, idle = g.branch(_out(asked), in_execs, x0 + 260, y0)
    code = g.get(WEAR_REQUEST_VAR, x0 + 280, y0 + 300)
    inside = g.call(FN_ARR_VALID, x0 + 280, y0 + 500,
                    TargetArray=g.get(SLOT_ITEMS, x0 + 40, y0 + 500), IndexToTest=code)
    known, wild = g.branch(_out(inside), [serve], x0 + 520, y0)
    # Stored before the request is lowered: every read below is of the copy.
    flow = g.put(WEAR_ITEM_VAR, slot_at(g, code, x0 + 780, y0 + 300), [known], x0 + 780, y0)
    flow = g.put(WEAR_REQUEST_VAR, str(NOT_CLOTHING), [flow, wild], x0 + 1040, y0)
    item = g.get(WEAR_ITEM_VAR, x0 + 1040, y0 + 300)
    there, nothing = g.branch(_out(g.call(FN_IS_VALID, x0 + 1300, y0 + 300, Object=item)),
                              [flow], x0 + 1300, y0)
    flow = g.put(WEAR_SLOT_VAR, g.iget(item, CLOTHING_SLOT_VAR, x0 + 1560, y0 + 300),
                 [there], x0 + 1560, y0)
    slot = g.get(WEAR_SLOT_VAR, x0 + 1820, y0 + 300)
    garment, other = g.branch(_out(g.call(FN_GE_II, x0 + 2080, y0 + 300, A=slot, B=0)),
                              [flow], x0 + 2080, y0)
    out = g.call(FN_ARR_REMOVE_ITEM, x0 + 2340, y0, [garment],
                 TargetArray=g.get("Inventory", x0 + 2100, y0 + 500), Item=item)

    # The slot already holds one: it comes off into the slot this one leaves.
    valid, old = _worn_at(g, slot, x0 + 2600, y0 + 440)
    full, empty = g.branch(valid, [BEL.find_then_pin(out)], x0 + 2860, y0)
    worn, bare = g.branch(_out(g.call(FN_IS_VALID, x0 + 2860, y0 + 600, Object=old)),
                          [full], x0 + 3120, y0)
    back = g.call(FN_ARR_ADD, x0 + 3380, y0, [worn],
                  TargetArray=g.get("Inventory", x0 + 3140, y0 + 300), NewItem=old)
    swapped = g.iput(old, SLOT_VAR, g.iget(item, SLOT_VAR, x0 + 3400, y0 + 300),
                     [BEL.find_then_pin(back)], x0 + 3640, y0)

    put_on = g.call(FN_ARR_SET, x0 + 3900, y0, [swapped, bare, empty],
                    TargetArray=g.get(WORN_VAR, x0 + 3660, y0 + 300), Index=slot, Item=item)
    _set(put_on, "bSizeToFit", "true")
    hide = g.call(FN_SET_HIDDEN, x0 + 4160, y0, [BEL.find_then_pin(put_on)], self=item)
    _set(hide, "bNewHidden", "true")
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [BEL.find_then_pin(hide)], x0 + 4420, y0)
    flow = g.put("NeedsRefresh", "true", [flow], x0 + 4680, y0)
    ed.add_comment_to_nodes(
        f"{WEAR_REQUEST_VAR}: the I panel's drag of a slot's item onto the worn grid. "
        "A garment leaves Inventory for Worn[its ClothingSlot], hidden; one already "
        "worn there takes the slot it left (wear_drag.py).", g.made)
    return [flow, idle, nothing, other]
