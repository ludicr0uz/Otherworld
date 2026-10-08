"""Clothing on the weapon component: putting a garment on, and taking one off.

    the fire key tapped with a garment in hand (consume.py's use gate, where
    Held.ClothingSlot is a slot), on the local player's machine:
        Server_Wear(), TriggerSpent
    Server_Wear, a reliable Server event (task M24; in single player a plain
    call, run there and then). Refused unless this machine's Held is a
    garment:
        WearItem = Held, WearSlot = Held.ClothingSlot
        Inventory.RemoveIndex(EquippedIndex)
        what Worn[WearSlot] holds (if anything) -> Inventory      (a swap)
        Worn[WearSlot] = WearItem (grown to fit), WearItem hidden and UNPLACED
        Held = None, EquippedIndex clamped, NeedsRefresh

    where the keys are (_author_wear_asks): a probe's TakeOffForced and
    WearForced call AskTakeOff and AskWear, as the I panel does (Server events
    too: asks.py).

    every Tick, with authority, before the slots are served: TakeOffSlot a
    slot (the I panel asks, graphics_menu/wear_tick.py):
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

All of it is the server's: Worn is its item actors, written down each Tick as
WornClass (record.py), which the owning client's Worn is a picture of
(view_worn.py). A client wears and takes off nothing itself.

WearItem and WearSlot are stored before anything moves: Held is cleared below,
and ClothingSlot is a pure read off it. Worn is read only behind
IsValidIndex: it starts empty and is grown by the first wear into a slot.
"""

from net.guard import author_guard
from uebp import net
from uebp.graph import _connect, _loose_pin, _pin, _set, out, then
from combat.ask_consts import ASK_TAKE_OFF, ASK_WEAR, FROM_PARAM, SLOT_PARAM, TO_PARAM
from combat.paths import ITEM_CLASS_PATH
from combat.record_vars import NO_ASK, TakeOffForced, TakeOffForcedTo, WearForced
from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, HAND, HAS_ROOM_VAR, SLOT_PICK_VAR, SLOT_VAR, UNPLACED,
)
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, SERVER_WEAR, TAKE_OFF_TO_VAR, TAKE_OFF_VAR,
    WEAR_ITEM_VAR, WORN_VAR,
)
from uebp.g import _G
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.slot_moves import _ask
from uebp.nodes.actor import FN_SET_HIDDEN
from uebp.nodes.array import (
    FN_ARR_ADD, FN_ARR_GET, FN_ARR_LEN, FN_ARR_REMOVE, FN_ARR_SET, FN_ARR_VALID)
from uebp.nodes.math import (
    FN_AND, FN_EQ_II, FN_GE_II, FN_LE_II, FN_MIN_II, FN_OR, FN_SELECT_II, FN_SUB_II)
from uebp.nodes.system import FN_IS_VALID
from combat.weapon_component import vars as WV

WEAR_SLOT_VAR = "WearSlot"     # the slot WearItem goes into (declared in build.py)


def _worn_at(g, slot):
    """(IsValidIndex(Worn, slot), Worn[slot]) -- read the second only behind
    a Branch on the first."""
    worn = g.get(WORN_VAR)
    valid = g.call(FN_ARR_VALID, TargetArray=worn, IndexToTest=slot)
    item = g.call(FN_ARR_GET, TargetArray=worn, Index=slot)
    return out(valid), _loose_pin(item, "Item", is_input=False)


def _is_garment(g, held):
    """Pure: Held.ClothingSlot >= 0."""
    slot_n = g.keep(g.ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(slot_n, "self"))
    return out(g.call(FN_GE_II, A=out(slot_n, CLOTHING_SLOT_VAR), B=0))


def _author_wear_gate(ed, held, exec_in):
    """Branch on Held.ClothingSlot >= 0: a garment is worn, by the server
    (Server_Wear), and the press is spent here, where the key is.
    Returns (the wear's exit, the exec pin for what is not a garment)."""
    g = _G(ed, ITEM_CLASS_PATH)
    worn, other = g.branch(_is_garment(g, held), [exec_in])
    asked = _ask(g, SERVER_WEAR, [worn])
    flow = g.put(TRIGGER_SPENT, "true", [asked])
    ed.add_comment_to_nodes(
        "Consumable with a ClothingSlot: a garment, worn rather than eaten. The "
        f"wear is the server's ({SERVER_WEAR}); the press is spent, as eating "
        "spends it (wear.py).", g.made)
    return flow, other


def author_wear_event(ed):
    """Server_Wear(): the fire key's wear, on the machine that owns the
    inventory. Refused unless its own Held is there and a garment. Before
    the Tick, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_WEAR, []))
    go, _refused = author_guard(g, SERVER_WEAR, [then(event)])
    held = g.get(WV.Held)
    there, _empty = g.branch(out(g.call(FN_IS_VALID, Object=held)), [go])
    garment, _other = g.branch(_is_garment(g, held), [there])
    ed.add_comment_to_nodes(
        f"{SERVER_WEAR} (wear.py): the owning client's fire key with a garment in "
        "hand. Refused unless this machine's Held is one.", g.made)
    _author_wear(ed, held, garment)


def _author_wear_asks(ed, in_execs):
    """A probe's hand on the I panel's two asks (record_vars.FORCED), where
    the keys are, lowered as taken. Returns the exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    forced, none = g.branch(out(g.call(FN_GE_II, A=g.get(TakeOffForced), B=0)), in_execs)
    asked = _ask(g, ASK_TAKE_OFF, [forced], **{SLOT_PARAM: g.get(TakeOffForced),
                                               TO_PARAM: g.get(TakeOffForcedTo)})
    flow = [g.put(TakeOffForced, str(NO_ASK), [asked]), none]
    forced, none = g.branch(out(g.call(FN_GE_II, A=g.get(WearForced), B=0)), flow)
    asked = _ask(g, ASK_WEAR, [forced], **{FROM_PARAM: g.get(WearForced)})
    flow = [g.put(WearForced, str(NO_ASK), [asked]), none]
    ed.add_comment_to_nodes(
        f"TakeOffForced and WearForced: a probe's hand on {ASK_TAKE_OFF} and "
        f"{ASK_WEAR}, the I panel's asks, Server events both (wear.py).", g.made)
    return flow


def _author_wear(ed, held, exec_in):
    """Put the held garment on (see the module docstring). Returns the exit."""
    g = _G(ed, ITEM_CLASS_PATH)
    flow = g.put(WEAR_ITEM_VAR, held, [exec_in])
    slot_n = g.keep(ed.add_get_member_variable_node(CLOTHING_SLOT_VAR, ITEM_CLASS_PATH))
    _connect(held, _pin(slot_n, "self"))
    flow = g.put(WEAR_SLOT_VAR, out(slot_n, CLOTHING_SLOT_VAR), [flow])
    inv = g.get(WV.Inventory)
    flow = then(g.call(FN_ARR_REMOVE, [flow], TargetArray=inv,
                                    IndexToRemove=g.get(WV.EquippedIndex)))

    # The slot already holds one: it goes back into the bag, which the
    # removal above has just made room in.
    slot = g.get(WEAR_SLOT_VAR)
    valid, old = _worn_at(g, slot)
    there, empty = g.branch(valid, [flow])
    worn, bare = g.branch(out(g.call(FN_IS_VALID, Object=old)), [there])
    back = g.call(FN_ARR_ADD, [worn], TargetArray=g.get(WV.Inventory), NewItem=old)

    item = g.get(WEAR_ITEM_VAR)
    put_on = g.call(FN_ARR_SET,
                    [then(back), bare, empty],
                    TargetArray=g.get(WORN_VAR),
                    Index=g.get(WEAR_SLOT_VAR), Item=item)
    _set(put_on, "bSizeToFit", True)
    hide = g.call(FN_SET_HIDDEN, [then(put_on)], self=item)
    _set(hide, "bNewHidden", True)
    # Out of every slot: taken off, it comes back UNPLACED and the slot sync
    # finds it a bag slot, rather than claiming the hand it left.
    flow = g.iput(item, SLOT_VAR, str(UNPLACED), [then(hide)])
    flow = g.put(WV.Held, None, [flow])

    # Min(EquippedIndex, Length - 1), as eating leaves it (consume.py).
    count = g.call(FN_ARR_LEN, TargetArray=g.get(WV.Inventory))
    last = g.call(FN_SUB_II, A=out(count), B=1)
    clamp = g.call(FN_MIN_II, A=g.get(WV.EquippedIndex), B=out(last))
    flow = g.put(WV.EquippedIndex, out(clamp), [flow])
    flow = g.put(WV.NeedsRefresh, "true", [flow])
    ed.add_comment_to_nodes(
        "A garment is worn, not fired: out of Inventory and into Worn[its "
        "ClothingSlot], hidden; one already worn there goes back into the "
        "bag (wear.py).", g.made)
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
    back = g.call(FN_ARR_ADD, [fits], TargetArray=g.get(WV.Inventory), NewItem=item)
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
    flow = g.put(WV.NeedsRefresh, "true", [then(off)])
    ed.add_comment_to_nodes(
        f"{TAKE_OFF_VAR}, served with authority: the I panel asks for a garment to come off. While the "
        "bag has room, Worn[slot] goes back into Inventory and the slot is "
        "emptied (wear.py).", g.made)
    return [flow, idle, nothing, bare, full]
