"""Clothing on the weapon component: putting a garment on, and taking one off.

    the fire key tapped with a garment in hand (consume.py's use gate, where
    Held.ClothingSlot is a slot):
        WearItem = Held, WearSlot = Held.ClothingSlot
        Inventory.RemoveIndex(EquippedIndex)
        what Worn[WearSlot] holds (if anything) -> Inventory      (a swap)
        Worn[WearSlot] = WearItem (grown to fit), WearItem hidden and UNPLACED
        Held = None, EquippedIndex clamped, NeedsRefresh, TriggerSpent

    every Tick, before the refresh: TakeOffSlot a slot (the I panel asks,
    graphics_menu/wear_tick.py):
        TakeOffSlot = NOT_CLOTHING
        SlotPick = TakeOffTo, TakeOffTo = UNPLACED
        Worn[slot] valid and HasRoom (a bag slot or the hand free) ->
            Inventory += Worn[slot], its Slot = SlotPick if that is the hand
            or a bag slot (a drag dropped it there; the slot sync sends it to
            the first free bag slot if another item has that one), else
            UNPLACED; Worn[slot] = None, NeedsRefresh

Dragging a slot's garment onto the worn grid is wear_drag.py's.

A worn garment is the same actor that was picked up: out of Inventory, so the
equip loop never shows it, and hidden here once, since it leaves the bag from
the hand. Taking it off puts that actor back in the bag, still hidden and not
Dropped, as a pick-up with something else in hand would be.

WearItem and WearSlot are stored before anything moves: Held is cleared below,
and ClothingSlot is a pure read off it. Worn is read only behind
IsValidIndex: it starts empty and is grown by the first wear into a slot.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    FN_ARR_ADD, FN_ARR_GET, FN_ARR_LEN, FN_ARR_REMOVE, FN_ARR_SET, FN_ARR_VALID,
    FN_AND, FN_EQ_II, FN_IS_VALID, FN_LESS_II, FN_MIN_II, FN_OR, FN_SELECT_II,
    FN_SET_HIDDEN, FN_SUB_II,
)
from combat.paths import ITEM_CLASS_PATH
from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, HAND, HAS_ROOM_VAR, SLOT_PICK_VAR, SLOT_VAR, UNPLACED,
)
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_ITEM_VAR, WORN_VAR,
)
from combat.weapon_component.common import _G
from combat.weapon_component.consume import TRIGGER_SPENT

FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_LE_II = "/Script/Engine.KismetMathLibrary.LessEqual_IntInt"
WEAR_SLOT_VAR = "WearSlot"     # the slot WearItem goes into (declared in build.py)


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _worn_at(g, slot, x, y):
    """(IsValidIndex(Worn, slot), Worn[slot]) -- read the second only behind
    a Branch on the first."""
    worn = g.get(WORN_VAR, x, y)
    valid = g.call(FN_ARR_VALID, x + 240, y, TargetArray=worn, IndexToTest=slot)
    item = g.call(FN_ARR_GET, x + 240, y + 160, TargetArray=worn, Index=slot)
    return _out(valid), _loose_pin(item, "Item", is_input=False)


def _author_wear_gate(ed, held, exec_in, x0, y0, wx, wy):
    """Branch on Held.ClothingSlot >= 0: a garment is worn (the wear at wx, wy).
    Returns (the wear's exit, the exec pin for what is not a garment)."""
    g = _G(ed)
    slot_n = g.keep(ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH),
                    x0, y0 + 300)
    _connect(held, _pin(slot_n, "self"))
    garment = g.call(FN_GE_II, x0 + 240, y0 + 300, A=_out(slot_n, CLOTHING_SLOT_VAR), B=0)
    worn, other = g.branch(_out(garment), [exec_in], x0 + 480, y0)
    ed.add_comment_to_nodes(
        "Consumable with a ClothingSlot: a garment, worn rather than eaten.", g.made)
    return _author_wear(ed, held, worn, wx, wy), other


def _author_wear(ed, held, exec_in, x0, y0):
    """Put the held garment on (see the module docstring). Returns the exit."""
    g = _G(ed)
    flow = g.put(WEAR_ITEM_VAR, held, [exec_in], x0, y0)
    slot_n = g.keep(ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH),
                    x0, y0 + 300)
    _connect(held, _pin(slot_n, "self"))
    flow = g.put(WEAR_SLOT_VAR, _out(slot_n, CLOTHING_SLOT_VAR), [flow], x0 + 260, y0)
    inv = g.get("Inventory", x0 + 260, y0 + 300)
    flow = BEL.find_then_pin(g.call(FN_ARR_REMOVE, x0 + 520, y0, [flow], TargetArray=inv,
                                    IndexToRemove=g.get("EquippedIndex", x0 + 260,
                                                        y0 + 440)))

    # The slot already holds one: it goes back into the bag, which the
    # removal above has just made room in.
    slot = g.get(WEAR_SLOT_VAR, x0 + 780, y0 + 300)
    valid, old = _worn_at(g, slot, x0 + 780, y0 + 440)
    there, empty = g.branch(valid, [flow], x0 + 1040, y0)
    worn, bare = g.branch(_out(g.call(FN_IS_VALID, x0 + 1040, y0 + 600, Object=old)),
                          [there], x0 + 1300, y0)
    back = g.call(FN_ARR_ADD, x0 + 1560, y0, [worn],
                  TargetArray=g.get("Inventory", x0 + 1300, y0 + 300), NewItem=old)

    item = g.get(WEAR_ITEM_VAR, x0 + 1820, y0 + 440)
    put_on = g.call(FN_ARR_SET, x0 + 1820, y0,
                    [BEL.find_then_pin(back), bare, empty],
                    TargetArray=g.get(WORN_VAR, x0 + 1820, y0 + 300),
                    Index=g.get(WEAR_SLOT_VAR, x0 + 1820, y0 + 580), Item=item)
    _set(put_on, "bSizeToFit", "true")
    hide = g.call(FN_SET_HIDDEN, x0 + 2080, y0, [BEL.find_then_pin(put_on)], self=item)
    _set(hide, "bNewHidden", "true")
    # Out of every slot: taken off, it comes back UNPLACED and the slot sync
    # finds it a bag slot, rather than claiming the hand it left.
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [BEL.find_then_pin(hide)], x0 + 2080,
                  y0 - 300)
    flow = g.put("Held", None, [flow], x0 + 2340, y0)

    # Min(EquippedIndex, Length - 1), as eating leaves it (consume.py).
    count = g.call(FN_ARR_LEN, x0 + 2340, y0 + 300,
                   TargetArray=g.get("Inventory", x0 + 2100, y0 + 300))
    last = g.call(FN_SUB_II, x0 + 2600, y0 + 300, A=_out(count), B=1)
    clamp = g.call(FN_MIN_II, x0 + 2860, y0 + 300,
                   A=g.get("EquippedIndex", x0 + 2600, y0 + 440), B=_out(last))
    flow = g.put("EquippedIndex", _out(clamp), [flow], x0 + 2860, y0)
    flow = g.put("NeedsRefresh", "true", [flow], x0 + 3120, y0)
    flow = g.put(TRIGGER_SPENT, "true", [flow], x0 + 3380, y0)
    ed.add_comment_to_nodes(
        "A garment is worn, not fired: out of Inventory and into Worn[its "
        "ClothingSlot], hidden; one already worn there goes back into the "
        "bag. The press is spent, as eating spends it (wear.py).", g.made)
    return flow


def _author_take_off(ed, in_execs, x0, y0):
    """Serve TakeOffSlot (see the module docstring). Returns the exits."""
    g = _G(ed)
    asked = g.call(FN_GE_II, x0, y0 + 300, A=g.get(TAKE_OFF_VAR, x0 - 240, y0 + 300), B=0)
    serve, idle = g.branch(_out(asked), in_execs, x0 + 260, y0)
    # Copied before the request is lowered: every read below is of the copy.
    flow = g.put(WEAR_SLOT_VAR, g.get(TAKE_OFF_VAR, x0 + 280, y0 + 300), [serve],
                 x0 + 520, y0)
    flow = g.put(TAKE_OFF_VAR, str(NOT_CLOTHING), [flow], x0 + 780, y0)
    # Where a drag dropped it, copied and lowered with the request.
    flow = g.put(SLOT_PICK_VAR, g.get(TAKE_OFF_TO_VAR, x0 + 540, y0 - 300), [flow],
                 x0 + 780, y0 - 300)
    flow = g.put(TAKE_OFF_TO_VAR, str(UNPLACED), [flow], x0 + 1040, y0 - 300)
    slot = g.get(WEAR_SLOT_VAR, x0 + 1040, y0 + 300)
    valid, item = _worn_at(g, slot, x0 + 1040, y0 + 440)
    there, nothing = g.branch(valid, [flow], x0 + 1300, y0)
    room = g.get(HAS_ROOM_VAR, x0 + 1560, y0 + 700)
    worn, bare = g.branch(_out(g.call(FN_IS_VALID, x0 + 1300, y0 + 600, Object=item)),
                          [there], x0 + 1560, y0)
    fits, full = g.branch(room, [worn], x0 + 1820, y0)
    back = g.call(FN_ARR_ADD, x0 + 2080, y0, [fits],
                  TargetArray=g.get("Inventory", x0 + 1820, y0 + 300), NewItem=item)
    # The hand or a bag slot only: a garment fits no weapon slot.
    to = g.get(SLOT_PICK_VAR, x0 + 1820, y0 + 900)
    in_bag = g.call(FN_AND, x0 + 2340, y0 + 1040,
                    A=_out(g.call(FN_GE_II, x0 + 2080, y0 + 1040, A=to, B=BAG_FIRST)),
                    B=_out(g.call(FN_LE_II, x0 + 2080, y0 + 1180, A=to, B=BAG_LAST)))
    place = g.call(FN_OR, x0 + 2600, y0 + 900,
                   A=_out(g.call(FN_EQ_II, x0 + 2080, y0 + 900, A=to, B=HAND)),
                   B=_out(in_bag))
    code = g.call(FN_SELECT_II, x0 + 2860, y0 + 900, A=to, B=UNPLACED, bPickA=_out(place))
    placed = g.iput(item, SLOT_VAR, _out(code), [BEL.find_then_pin(back)], x0 + 2340,
                    y0 - 300)
    # Item left unconnected: Worn[slot] = None.
    off = g.call(FN_ARR_SET, x0 + 2340, y0, [placed],
                 TargetArray=g.get(WORN_VAR, x0 + 2100, y0 + 300),
                 Index=g.get(WEAR_SLOT_VAR, x0 + 2100, y0 + 440))
    flow = g.put("NeedsRefresh", "true", [BEL.find_then_pin(off)], x0 + 2600, y0)
    ed.add_comment_to_nodes(
        f"{TAKE_OFF_VAR}: the I panel asks for a garment to come off. While the "
        "bag has room, Worn[slot] goes back into Inventory and the slot is "
        "emptied (wear.py).", g.made)
    return [flow, idle, nothing, bare, full]
