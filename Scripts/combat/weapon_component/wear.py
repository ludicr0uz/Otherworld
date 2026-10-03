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

from uebp.graph import _connect, _loose_pin, _pin, _set, out, then
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
from uebp.g import _G
from combat.weapon_component.consume import TRIGGER_SPENT

FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_LE_II = "/Script/Engine.KismetMathLibrary.LessEqual_IntInt"
WEAR_SLOT_VAR = "WearSlot"     # the slot WearItem goes into (declared in build.py)


def _worn_at(g, slot):
    """(IsValidIndex(Worn, slot), Worn[slot]) -- read the second only behind
    a Branch on the first."""
    worn = g.get(WORN_VAR)
    valid = g.call(FN_ARR_VALID, TargetArray=worn, IndexToTest=slot)
    item = g.call(FN_ARR_GET, TargetArray=worn, Index=slot)
    return out(valid), _loose_pin(item, "Item", is_input=False)


def _author_wear_gate(ed, held, exec_in):
    """Branch on Held.ClothingSlot >= 0: a garment is worn (the wear at wx, wy).
    Returns (the wear's exit, the exec pin for what is not a garment)."""
    g = _G(ed, ITEM_CLASS_PATH)
    slot_n = g.keep(ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(slot_n, "self"))
    garment = g.call(FN_GE_II, A=out(slot_n, CLOTHING_SLOT_VAR), B=0)
    worn, other = g.branch(out(garment), [exec_in])
    ed.add_comment_to_nodes(
        "Consumable with a ClothingSlot: a garment, worn rather than eaten.", g.made)
    return _author_wear(ed, held, worn), other


def _author_wear(ed, held, exec_in):
    """Put the held garment on (see the module docstring). Returns the exit."""
    g = _G(ed, ITEM_CLASS_PATH)
    flow = g.put(WEAR_ITEM_VAR, held, [exec_in])
    slot_n = g.keep(ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(slot_n, "self"))
    flow = g.put(WEAR_SLOT_VAR, out(slot_n, CLOTHING_SLOT_VAR), [flow])
    inv = g.get("Inventory")
    flow = then(g.call(FN_ARR_REMOVE, [flow], TargetArray=inv,
                                    IndexToRemove=g.get("EquippedIndex")))

    # The slot already holds one: it goes back into the bag, which the
    # removal above has just made room in.
    slot = g.get(WEAR_SLOT_VAR)
    valid, old = _worn_at(g, slot)
    there, empty = g.branch(valid, [flow])
    worn, bare = g.branch(out(g.call(FN_IS_VALID, Object=old)), [there])
    back = g.call(FN_ARR_ADD, [worn], TargetArray=g.get("Inventory"), NewItem=old)

    item = g.get(WEAR_ITEM_VAR)
    put_on = g.call(FN_ARR_SET,
                    [then(back), bare, empty],
                    TargetArray=g.get(WORN_VAR),
                    Index=g.get(WEAR_SLOT_VAR), Item=item)
    _set(put_on, "bSizeToFit", "true")
    hide = g.call(FN_SET_HIDDEN, [then(put_on)], self=item)
    _set(hide, "bNewHidden", "true")
    # Out of every slot: taken off, it comes back UNPLACED and the slot sync
    # finds it a bag slot, rather than claiming the hand it left.
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [then(hide)])
    flow = g.put("Held", None, [flow])

    # Min(EquippedIndex, Length - 1), as eating leaves it (consume.py).
    count = g.call(FN_ARR_LEN, TargetArray=g.get("Inventory"))
    last = g.call(FN_SUB_II, A=out(count), B=1)
    clamp = g.call(FN_MIN_II, A=g.get("EquippedIndex"), B=out(last))
    flow = g.put("EquippedIndex", out(clamp), [flow])
    flow = g.put("NeedsRefresh", "true", [flow])
    flow = g.put(TRIGGER_SPENT, "true", [flow])
    ed.add_comment_to_nodes(
        "A garment is worn, not fired: out of Inventory and into Worn[its "
        "ClothingSlot], hidden; one already worn there goes back into the "
        "bag. The press is spent, as eating spends it (wear.py).", g.made)
    return flow


def _author_take_off(ed, in_execs):
    """Serve TakeOffSlot (see the module docstring). Returns the exits."""
    g = _G(ed, ITEM_CLASS_PATH)
    asked = g.call(FN_GE_II, A=g.get(TAKE_OFF_VAR), B=0)
    serve, idle = g.branch(out(asked), in_execs)
    # Copied before the request is lowered: every read below is of the copy.
    flow = g.put(WEAR_SLOT_VAR, g.get(TAKE_OFF_VAR), [serve])
    flow = g.put(TAKE_OFF_VAR, str(NOT_CLOTHING), [flow])
    # Where a drag dropped it, copied and lowered with the request.
    flow = g.put(SLOT_PICK_VAR, g.get(TAKE_OFF_TO_VAR), [flow])
    flow = g.put(TAKE_OFF_TO_VAR, str(UNPLACED), [flow])
    slot = g.get(WEAR_SLOT_VAR)
    valid, item = _worn_at(g, slot)
    there, nothing = g.branch(valid, [flow])
    room = g.get(HAS_ROOM_VAR)
    worn, bare = g.branch(out(g.call(FN_IS_VALID, Object=item)), [there])
    fits, full = g.branch(room, [worn])
    back = g.call(FN_ARR_ADD, [fits], TargetArray=g.get("Inventory"), NewItem=item)
    # The hand or a bag slot only: a garment fits no weapon slot.
    to = g.get(SLOT_PICK_VAR)
    in_bag = g.call(FN_AND,
                    A=out(g.call(FN_GE_II, A=to, B=BAG_FIRST)),
                    B=out(g.call(FN_LE_II, A=to, B=BAG_LAST)))
    place = g.call(FN_OR, A=out(g.call(FN_EQ_II, A=to, B=HAND)), B=out(in_bag))
    code = g.call(FN_SELECT_II, A=to, B=UNPLACED, bPickA=out(place))
    placed = g.iput(item, SLOT_VAR, out(code), [then(back)])
    # Item left unconnected: Worn[slot] = None.
    off = g.call(FN_ARR_SET, [placed], TargetArray=g.get(WORN_VAR), Index=g.get(WEAR_SLOT_VAR))
    flow = g.put("NeedsRefresh", "true", [then(off)])
    ed.add_comment_to_nodes(
        f"{TAKE_OFF_VAR}: the I panel asks for a garment to come off. While the "
        "bag has room, Worn[slot] goes back into Inventory and the slot is "
        "emptied (wear.py).", g.made)
    return [flow, idle, nothing, bare, full]
