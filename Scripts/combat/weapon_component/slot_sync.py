"""The slot sync: where every carried item is, rebuilt each Tick from the
items' own Slots (slot_tuning has the codes). The last fragment before the
refresh, so whatever moved this frame is placed before the equip runs.

    SlotItems = 15 x None
    for each item in Inventory:
        its Slot a free code -> SlotItems[Slot] = item
        otherwise (UNPLACED, or a code another item took) -> Slot = UNPLACED
    for each item still UNPLACED (picked up, looted, taken off):
        a free weapon slot it fits (a weapon goes to its own slot before
        the bag), or the first free bag slot, or the hand if it is empty
        -> Slot, SlotItems
        (into the hand: HandFrom = UNPLACED, it came from nowhere)
    EquippedIndex = Find(Inventory, SlotItems[HAND])        (-1: empty hands)
    HasRoom = a bag slot free OR the hand empty
    SlotItems[HAND] != Held -> NeedsRefresh

So nothing else keeps the hand: the drop, the throw, eating, wearing, the
number keys and the HUD's drags only change an item's Slot or take it out
of Inventory, and the equip follows. An item left UNPLACED with no slot
at all free stays carried and unshown: a pick-up, a take-off and the loot
window test HasRoom first, and the dev-all-guns cheat gives only guns,
which find their weapon slots.
"""

from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, HAND, HAND_FROM_VAR, HAS_ROOM_VAR, MELEE_SLOT, PRIMARY,
    SLOT_COUNT, SLOT_ITEMS_VAR, SLOT_PICK_VAR, SLOT_VAR, UNPLACED,
)
from combat.paths import ITEM_CLASS_PATH
from uebp.g import _G
from combat.weapon_component.slot_nodes import (
    fits, for_each, for_loop, not_, op, slot_at, valid)
from uebp.graph import out, then
from uebp.nodes.array import FN_ARR_CLEAR, FN_ARR_FIND, FN_ARR_RESIZE, FN_ARR_SET
from uebp.nodes.math import FN_AND, FN_EQ_II, FN_GE_II, FN_LESS_II, FN_NE_OO, FN_OR
from combat.weapon_component import vars as WV


def _author_claim(g, execs):
    """The first pass: each item onto its own Slot. Returns Completed."""
    items = g.get(SLOT_ITEMS_VAR)
    clear = g.call(FN_ARR_CLEAR, execs, TargetArray=items)
    size = g.call(FN_ARR_RESIZE, [then(clear)], TargetArray=items, Size=SLOT_COUNT)
    item, _i, body, done = for_each(g, g.get(WV.Inventory), [then(size)])
    slot = g.iget(item, SLOT_VAR)
    placed = op(g, FN_AND, op(g, FN_GE_II, slot, 0), op(g, FN_LESS_II, slot, SLOT_COUNT))
    yes, no = g.branch(placed, [body])
    clash, free = g.branch(valid(g, slot_at(g, slot)), [yes])
    g.iput(item, SLOT_VAR, str(UNPLACED), [clash, no])
    g.call(FN_ARR_SET, [free], TargetArray=g.get(SLOT_ITEMS_VAR), Index=slot, Item=item)
    return done


def _author_place(g, execs):
    """The second pass: each UNPLACED item into a free weapon slot it fits,
    else the first free bag slot, else the hand. Returns Completed."""
    item, _i, body, done = for_each(g, g.get(WV.Inventory), execs)
    lost = op(g, FN_EQ_II, g.iget(item, SLOT_VAR), UNPLACED)
    yes, _no = g.branch(lost, [body])
    flow = g.put(SLOT_PICK_VAR, str(UNPLACED), [yes])
    armed, unarmed = _author_weapon_slot(g, item, [flow])
    k, kbody, kdone = for_loop(g, BAG_FIRST, BAG_LAST, [unarmed])
    searching = op(g, FN_LESS_II, g.get(SLOT_PICK_VAR), 0)
    look, _ = g.branch(searching, [kbody])
    _taken, empty = g.branch(valid(g, slot_at(g, k)), [look])
    g.put(SLOT_PICK_VAR, k, [empty])

    found = op(g, FN_GE_II, g.get(SLOT_PICK_VAR), 0)
    bagged, full = g.branch(found, [kdone])
    bare = not_(g, valid(g, slot_at(g, HAND)))
    in_hand, _busy = g.branch(bare, [full])
    flow = g.put(SLOT_PICK_VAR, str(HAND), [in_hand])
    flow = g.put(HAND_FROM_VAR, str(UNPLACED), [flow])
    pick = g.get(SLOT_PICK_VAR)
    flow = g.iput(item, SLOT_VAR, pick, [bagged, flow, armed])
    g.call(FN_ARR_SET, [flow], TargetArray=g.get(SLOT_ITEMS_VAR), Index=pick, Item=item)
    return done


def _author_weapon_slot(g, item, execs):
    """Before the bag: SlotPick := the first free weapon slot ``item`` fits
    (none for an item that is no weapon). Returns (found, none): the exec
    pins a find and no find leave by."""
    s, body, done = for_loop(g, PRIMARY, MELEE_SLOT, execs)
    searching = op(g, FN_LESS_II, g.get(SLOT_PICK_VAR), 0)
    look, _ = g.branch(searching, [body])
    free = op(g, FN_AND, fits(g, item, s), not_(g, valid(g, slot_at(g, s))))
    yes, _ = g.branch(free, [look])
    g.put(SLOT_PICK_VAR, s, [yes])
    return g.branch(op(g, FN_GE_II, g.get(SLOT_PICK_VAR), PRIMARY), [done])


def _author_after(g, execs):
    """EquippedIndex, HasRoom and the refresh off the rebuilt SlotItems.
    Returns the exec tails."""
    hand = slot_at(g, HAND)
    find = g.call(FN_ARR_FIND, TargetArray=g.get(WV.Inventory), ItemToFind=hand)
    flow = g.put(WV.EquippedIndex, out(find), execs)
    flow = g.put(SLOT_PICK_VAR, str(UNPLACED), [flow])
    k, body, done = for_loop(g, BAG_FIRST, BAG_LAST, [flow])
    empty, _ = g.branch(not_(g, valid(g, slot_at(g, k))), [body])
    g.put(SLOT_PICK_VAR, k, [empty])
    room = op(g, FN_OR, op(g, FN_GE_II, g.get(SLOT_PICK_VAR), 0), not_(g, valid(g, hand)))
    flow = g.put(HAS_ROOM_VAR, room, [done])
    changed = op(g, FN_NE_OO, slot_at(g, HAND), g.get(WV.Held))
    moved, same = g.branch(changed, [flow])
    return [g.put(WV.NeedsRefresh, "true", [moved]), same]


def _author_slot_sync(ed, in_execs):
    """The whole sync (see the module docstring). Returns the exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    flow = _author_claim(g, in_execs)
    flow = _author_place(g, [flow])
    tails = _author_after(g, [flow])
    ed.add_comment_to_nodes(
        "The slot sync: SlotItems rebuilt from each item's own Slot, the "
        "UNPLACED ones put in a free weapon slot they fit, else the first "
        "free bag slot, else the hand, then "
        "EquippedIndex, HasRoom, and a refresh when the hand's item is not "
        "Held (slot_sync.py).", g.made[:4])
    return tails
