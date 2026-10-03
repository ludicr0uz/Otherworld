"""The slots' keys and moves on the weapon component's Tick (slot_tuning has
the codes). Each only changes items' Slots; slot_sync.py, after them, places
them and the equip follows.

    keys (with the switch block's place in Tick):
        1 2 3 4         SlotRequest = primary / secondary / pistol / melee
        5 6 7 8 9       SlotRequest = the bag's first five slots
        Q               NextRequest, served at once: SlotRequest = the next
                        filled bag slot after the one the hand's item came
                        from, round the bag (the first filled one when the
                        hand's item is not the bag's); the weapon slots are
                        not on it, they have 1-4
    the request (a key, or the HUD: a bag slot picked in the I panel):
        the slot holds an item ->
            the hand's item (if any) goes home first: the first slot from
            primary on that it fits and that is free (the asked slot counts
            as free: a swap). A weapon finds its weapon slot before the bag,
            so a gun in hand goes back to the primary or secondary when a
            quick slot is pressed. No home: nothing moves.
            Then the asked item -> the hand, HandFrom = the slot.
        the slot is empty -> the hand's item goes back into it if it came
            from it (1 pressed again: the gun is put away, hands empty)
    the move (the HUD's drag, MoveFrom -> MoveTo):
        the item fits MoveTo and whatever is there fits MoveFrom -> swapped;
        an empty MoveTo just takes it. Only a weapon fits a weapon slot.

Each request is copied and lowered before anything reads it, so a request
is served once; the items are read off SlotItems, which the sync wrote at
the end of last frame.
"""

from combat.slot_tuning import (
    BAG_FIRST, BAG_LAST, BAG_SIZE, HAND, HAND_FROM_VAR, MOVE_DST_VAR, MOVE_FROM_VAR,
    MOVE_SRC_VAR, MOVE_TO_VAR, NEXT_REQUEST_VAR, NO_REQUEST, PRIMARY, SLOT_COUNT, SLOT_KEYS,
    SLOT_PICK_VAR, SLOT_REQUEST_VAR, SLOT_VAR, SLOT_WANT_VAR,
)
from combat.paths import ITEM_CLASS_PATH
from uebp.g import _G
from combat.weapon_component.slot_nodes import fits, for_loop, not_, op, slot_at, valid
from uebp.graph import out
from uebp.nodes.actor import FN_WAS_PRESSED
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_EQ_II, FN_GE_II, FN_LESS_II, FN_LE_II, FN_MOD_II, FN_NEQ_II, FN_OR,
    FN_SELECT_II, FN_SUB_II)


def _author_find_home(g, item, freed, execs):
    """SlotPick := the first slot from PRIMARY on that ``item`` fits and
    that is empty or is ``freed`` (an int pin), else NO_REQUEST.
    Returns Completed."""
    flow = g.put(SLOT_PICK_VAR, str(NO_REQUEST), execs)
    s, body, done = for_loop(g, PRIMARY, BAG_LAST, [flow])
    searching = op(g, FN_LESS_II, g.get(SLOT_PICK_VAR), 0)
    look, _ = g.branch(searching, [body])
    free = op(g, FN_OR, op(g, FN_EQ_II, s, freed), not_(g, valid(g, slot_at(g, s))))
    home = op(g, FN_AND, fits(g, item, s), free)
    yes, _ = g.branch(home, [look])
    g.put(SLOT_PICK_VAR, s, [yes])
    return done


def _author_slot_request(g, in_execs):
    """Serve SlotRequest (see the module docstring). Returns the exec tails."""
    asked = op(g, FN_AND, op(g, FN_GE_II, g.get(SLOT_REQUEST_VAR), PRIMARY),
               op(g, FN_LESS_II, g.get(SLOT_REQUEST_VAR), SLOT_COUNT))
    serve, idle = g.branch(asked, in_execs)
    flow = g.put(SLOT_WANT_VAR, g.get(SLOT_REQUEST_VAR), [serve])
    flow = g.put(SLOT_REQUEST_VAR, str(NO_REQUEST), [flow])
    want = g.get(SLOT_WANT_VAR)
    target = slot_at(g, want)
    hand = slot_at(g, HAND)
    filled, empty = g.branch(valid(g, target), [flow])

    # A filled slot: the hand's item goes home, then the asked one comes up.
    holding, bare = g.branch(valid(g, hand), [filled])
    searched = _author_find_home(g, hand, want, [holding])
    found = op(g, FN_GE_II, g.get(SLOT_PICK_VAR), PRIMARY)
    homed, no_home = g.branch(found, [searched])
    stowed = g.iput(hand, SLOT_VAR, g.get(SLOT_PICK_VAR), [homed])
    took = g.iput(target, SLOT_VAR, str(HAND), [stowed, bare])
    took = g.put(HAND_FROM_VAR, want, [took])

    # An empty slot: the hand's item goes back if that is where it came from.
    holding2, bare2 = g.branch(valid(g, hand), [empty])
    came = op(g, FN_AND, op(g, FN_EQ_II, g.get(HAND_FROM_VAR), want), fits(g, hand, want))
    back, stay = g.branch(came, [holding2])
    put_back = g.iput(hand, SLOT_VAR, want, [back])
    return [took, no_home, put_back, stay, bare2, idle]


def _author_slot_move(g, in_execs):
    """Serve MoveFrom -> MoveTo (see the module docstring). Returns the exec
    tails."""
    asked = op(g, FN_GE_II, g.get(MOVE_FROM_VAR), 0)
    serve, idle = g.branch(asked, in_execs)
    flow = g.put(MOVE_SRC_VAR, g.get(MOVE_FROM_VAR), [serve])
    flow = g.put(MOVE_DST_VAR, g.get(MOVE_TO_VAR), [flow])
    flow = g.put(MOVE_FROM_VAR, str(NO_REQUEST), [flow])
    flow = g.put(MOVE_TO_VAR, str(NO_REQUEST), [flow])
    src_i = g.get(MOVE_SRC_VAR)
    dst_i = g.get(MOVE_DST_VAR)
    sane = op(g, FN_AND,
              op(g, FN_AND, op(g, FN_GE_II, dst_i, 0),
                 op(g, FN_LESS_II, dst_i, SLOT_COUNT)),
              op(g, FN_AND, op(g, FN_LESS_II, src_i, SLOT_COUNT),
                 op(g, FN_NEQ_II, src_i, dst_i)))
    ok, bad = g.branch(sane, [flow])
    src = slot_at(g, src_i)
    dst = slot_at(g, dst_i)
    carried, nothing = g.branch(valid(g, src), [ok])
    goes, refused = g.branch(fits(g, src, dst_i), [carried])
    taken, open_ = g.branch(valid(g, dst), [goes])
    swaps, stuck = g.branch(fits(g, dst, src_i), [taken])
    swapped = g.iput(dst, SLOT_VAR, src_i, [swaps])
    moved = g.iput(src, SLOT_VAR, dst_i, [swapped, open_])
    # Into the hand, it came from MoveFrom; out of it, the swapped-in one
    # came from MoveTo.
    up, not_up = g.branch(op(g, FN_EQ_II, dst_i, HAND), [moved])
    t1 = g.put(HAND_FROM_VAR, src_i, [up])
    down, other = g.branch(op(g, FN_EQ_II, src_i, HAND), [not_up])
    t2 = g.put(HAND_FROM_VAR, dst_i, [down])
    return [t1, t2, other, stuck, refused, nothing, bad, idle]


def _author_slot_keys(ed, pc_out, switch_pressed, in_execs):
    """1-9 raise SlotRequest and Q the next filled bag slot's (see the module docstring). Returns the
    exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    flow = list(in_execs)
    for var, _key, slot in SLOT_KEYS:
        pressed = out(g.call(FN_WAS_PRESSED, self=pc_out, Key=g.get(var)))
        hit, miss = g.branch(pressed, flow)
        flow = [g.put(SLOT_REQUEST_VAR, str(slot), [hit]), miss]

    hit, miss = g.branch(switch_pressed, flow)
    flow = [g.put(NEXT_REQUEST_VAR, "1", [hit]), miss]

    # The next filled bag slot after the one the hand's item came from, round.
    serve, idle = g.branch(op(g, FN_GE_II, g.get(NEXT_REQUEST_VAR), 0), flow)
    flow = g.put(NEXT_REQUEST_VAR, str(NO_REQUEST), [serve])
    flow = g.put(SLOT_PICK_VAR, str(NO_REQUEST), [flow])
    came = g.get(HAND_FROM_VAR)
    bag_from = op(g, FN_AND, op(g, FN_GE_II, came, BAG_FIRST), op(g, FN_LE_II, came, BAG_LAST))
    base = out(g.call(FN_SELECT_II, A=came, B=BAG_LAST, bPickA=bag_from))
    off, body, done = for_loop(g, 1, BAG_SIZE, [flow])
    # ((base - BAG_FIRST + off) mod BAG_SIZE) + BAG_FIRST: the bag slots after base, round.
    step = op(g, FN_ADD_II, op(g, FN_SUB_II, base, BAG_FIRST), off)
    c = op(g, FN_ADD_II, op(g, FN_MOD_II, step, BAG_SIZE), BAG_FIRST)
    look, _ = g.branch(op(g, FN_LESS_II, g.get(SLOT_PICK_VAR), 0), [body])
    there, _ = g.branch(valid(g, slot_at(g, c)), [look])
    g.put(SLOT_PICK_VAR, c, [there])
    found, none = g.branch(op(g, FN_GE_II, g.get(SLOT_PICK_VAR), BAG_FIRST), [done])
    asked = g.put(SLOT_REQUEST_VAR, g.get(SLOT_PICK_VAR), [found])
    ed.add_comment_to_nodes(
        "1-4 bring a weapon slot's item to hand, 5-9 the bag's first five, Q the "
        "next filled bag slot's (NextRequest; slot_moves.py). Each only raises "
        "SlotRequest.",
        g.made[:3])
    return [asked, none, idle]


def _author_slot_serve(ed, in_execs):
    """The request, then the move. Returns the exec tails."""
    g = _G(ed, ITEM_CLASS_PATH)
    tails = _author_slot_request(g, in_execs)
    tails = _author_slot_move(g, tails)
    ed.add_comment_to_nodes(
        "SlotRequest brings a slot's item to hand (the hand's going home first, "
        "or back where it came from); MoveFrom/MoveTo is the HUD's drag, a swap "
        "where both fit (slot_moves.py).", g.made[:3])
    return tails
