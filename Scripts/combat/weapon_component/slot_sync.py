"""The slot sync: where every carried item is, rebuilt each Tick from the
items' own Slots (slot_tuning has the codes). The last fragment before the
refresh, so whatever moved this frame is placed before the equip runs.

    SlotItems = 15 x None
    for each item in Inventory:
        its Slot a free code -> SlotItems[Slot] = item
        otherwise (UNPLACED, or a code another item took) -> Slot = UNPLACED
    for each item still UNPLACED (picked up, looted, taken off):
        the first free bag slot, or the hand if it is empty, or a free
        weapon slot it fits -> Slot, SlotItems
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

from combat.nodes import FN_AND, FN_ARR_SET, FN_EQ_II, FN_LESS_II, FN_OR
from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, HAND, HAND_FROM_VAR, HAS_ROOM_VAR, MELEE_SLOT, PRIMARY,
    SLOT_COUNT, SLOT_ITEMS_VAR, SLOT_PICK_VAR, SLOT_VAR, UNPLACED,
)
from combat.weapon_component.common import _G
from combat.weapon_component.slot_nodes import (
    FN_ARR_CLEAR, FN_ARR_FIND, FN_ARR_RESIZE, FN_GE_II, FN_NE_OO,
    fits, for_each, for_loop, not_, op,
    slot_at, valid,
)
from uebp.graph import out, then


def _author_claim(g, execs, x0, y0):
    """The first pass: each item onto its own Slot. Returns Completed."""
    items = g.get(SLOT_ITEMS_VAR, x0, y0 + 300)
    clear = g.call(FN_ARR_CLEAR, x0 + 240, y0, execs, TargetArray=items)
    size = g.call(FN_ARR_RESIZE, x0 + 500, y0, [then(clear)], TargetArray=items,
                  Size=SLOT_COUNT)
    item, _i, body, done = for_each(g, g.get("Inventory", x0 + 500, y0 + 300),
                                    [then(size)], x0 + 760, y0)
    slot = g.iget(item, SLOT_VAR, x0 + 1000, y0 + 300)
    placed = op(g, FN_AND, op(g, FN_GE_II, slot, 0, x0 + 1260, y0 + 300),
                op(g, FN_LESS_II, slot, SLOT_COUNT, x0 + 1260, y0 + 440),
                x0 + 1520, y0 + 300)
    yes, no = g.branch(placed, [body], x0 + 1780, y0)
    clash, free = g.branch(valid(g, slot_at(g, slot, x0 + 1780, y0 + 500),
                                 x0 + 2040, y0 + 500), [yes], x0 + 2040, y0)
    g.iput(item, SLOT_VAR, str(UNPLACED), [clash, no], x0 + 2300, y0 + 300)
    g.call(FN_ARR_SET, x0 + 2300, y0, [free], TargetArray=g.get(SLOT_ITEMS_VAR, x0 + 2060,
                                                                 y0 + 700),
           Index=slot, Item=item)
    return done


def _author_place(g, execs, x0, y0):
    """The second pass: each UNPLACED item into the first free bag slot, or
    the hand. Returns Completed."""
    item, _i, body, done = for_each(g, g.get("Inventory", x0, y0 + 300), execs, x0 + 240, y0)
    lost = op(g, FN_EQ_II, g.iget(item, SLOT_VAR, x0 + 480, y0 + 300), UNPLACED,
              x0 + 740, y0 + 300)
    yes, _no = g.branch(lost, [body], x0 + 1000, y0)
    flow = g.put(SLOT_PICK_VAR, str(UNPLACED), [yes], x0 + 1260, y0)
    k, kbody, kdone = for_loop(g, BAG_FIRST, BAG_LAST, [flow], x0 + 1520, y0)
    searching = op(g, FN_LESS_II, g.get(SLOT_PICK_VAR, x0 + 1520, y0 + 500), 0,
                   x0 + 1780, y0 + 500)
    look, _ = g.branch(searching, [kbody], x0 + 1780, y0 + 200)
    _taken, empty = g.branch(valid(g, slot_at(g, k, x0 + 2040, y0 + 700), x0 + 2300, y0 + 700),
                             [look], x0 + 2300, y0 + 200)
    g.put(SLOT_PICK_VAR, k, [empty], x0 + 2560, y0 + 200)

    found = op(g, FN_GE_II, g.get(SLOT_PICK_VAR, x0 + 1780, y0 - 300), 0, x0 + 2040, y0 - 300)
    bagged, full = g.branch(found, [kdone], x0 + 2300, y0 - 400)
    bare = not_(g, valid(g, slot_at(g, HAND, x0 + 2300, y0 - 700), x0 + 2560, y0 - 700),
                x0 + 2820, y0 - 700)
    in_hand, busy = g.branch(bare, [full], x0 + 2820, y0 - 400)
    flow = g.put(SLOT_PICK_VAR, str(HAND), [in_hand], x0 + 3080, y0 - 400)
    flow = g.put(HAND_FROM_VAR, str(UNPLACED), [flow], x0 + 3340, y0 - 400)
    armed = _author_weapon_slot(g, item, [busy], x0 + 2820, y0 - 1600)
    pick = g.get(SLOT_PICK_VAR, x0 + 3340, y0 - 100)
    flow = g.iput(item, SLOT_VAR, pick, [bagged, flow, armed], x0 + 3600, y0 - 400)
    g.call(FN_ARR_SET, x0 + 3860, y0 - 400, [flow],
           TargetArray=g.get(SLOT_ITEMS_VAR, x0 + 3600, y0 - 100), Index=pick, Item=item)
    return done


def _author_weapon_slot(g, item, execs, x0, y0):
    """With the bag full and the hand taken: SlotPick := a free weapon slot
    ``item`` fits. Returns the exec pin a find leaves by (none: nothing)."""
    s, body, done = for_loop(g, PRIMARY, MELEE_SLOT, execs, x0, y0)
    searching = op(g, FN_LESS_II, g.get(SLOT_PICK_VAR, x0, y0 + 500), 0, x0 + 260, y0 + 500)
    look, _ = g.branch(searching, [body], x0 + 260, y0)
    free = op(g, FN_AND, fits(g, item, s, x0 + 520, y0 + 700),
              not_(g, valid(g, slot_at(g, s, x0 + 520, y0 + 500), x0 + 780, y0 + 500),
                   x0 + 1040, y0 + 500), x0 + 2000, y0 + 500)
    yes, _ = g.branch(free, [look], x0 + 2000, y0)
    g.put(SLOT_PICK_VAR, s, [yes], x0 + 2260, y0)
    found, _none = g.branch(op(g, FN_GE_II, g.get(SLOT_PICK_VAR, x0 + 2260, y0 + 500),
                               PRIMARY, x0 + 2520, y0 + 500), [done], x0 + 2520, y0)
    return found


def _author_after(g, execs, x0, y0):
    """EquippedIndex, HasRoom and the refresh off the rebuilt SlotItems.
    Returns the exec tails."""
    hand = slot_at(g, HAND, x0, y0 + 600)
    find = g.call(FN_ARR_FIND, x0 + 260, y0 + 400, TargetArray=g.get("Inventory", x0, y0 + 400),
                  ItemToFind=hand)
    flow = g.put("EquippedIndex", out(find), execs, x0 + 520, y0)
    flow = g.put(SLOT_PICK_VAR, str(UNPLACED), [flow], x0 + 780, y0)
    k, body, done = for_loop(g, BAG_FIRST, BAG_LAST, [flow], x0 + 1040, y0)
    empty, _ = g.branch(not_(g, valid(g, slot_at(g, k, x0 + 1040, y0 + 500), x0 + 1300,
                                      y0 + 500), x0 + 1560, y0 + 500), [body], x0 + 1560, y0)
    g.put(SLOT_PICK_VAR, k, [empty], x0 + 1820, y0)
    room = op(g, FN_OR, op(g, FN_GE_II, g.get(SLOT_PICK_VAR, x0 + 1820, y0 + 500), 0,
                           x0 + 2080, y0 + 500),
              not_(g, valid(g, hand, x0 + 2080, y0 + 640), x0 + 2340, y0 + 640),
              x0 + 2600, y0 + 500)
    flow = g.put(HAS_ROOM_VAR, room, [done], x0 + 2600, y0)
    changed = op(g, FN_NE_OO, slot_at(g, HAND, x0 + 2600, y0 + 800),
                 g.get("Held", x0 + 2600, y0 + 940), x0 + 2860, y0 + 800)
    moved, same = g.branch(changed, [flow], x0 + 2860, y0)
    return [g.put("NeedsRefresh", "true", [moved], x0 + 3120, y0), same]


def _author_slot_sync(ed, in_execs, x0, y0):
    """The whole sync (see the module docstring). Returns the exec tails."""
    g = _G(ed)
    flow = _author_claim(g, in_execs, x0, y0)
    flow = _author_place(g, [flow], x0 + 2800, y0)
    tails = _author_after(g, [flow], x0 + 7000, y0)
    ed.add_comment_to_nodes(
        "The slot sync: SlotItems rebuilt from each item's own Slot, the "
        "UNPLACED ones put in the first free bag slot or the hand, then "
        "EquippedIndex, HasRoom, and a refresh when the hand's item is not "
        "Held (slot_sync.py).", g.made[:4])
    return tails
