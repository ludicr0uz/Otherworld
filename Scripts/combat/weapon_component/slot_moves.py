"""The slots' keys and moves on the weapon component's Tick (slot_tuning has
the codes). Each only changes items' Slots; slot_sync.py, after them, places
them and the equip follows.

    keys (with the switch block's place in Tick):
        1 2 3 4         SlotRequest = primary / secondary / pistol / melee
        5 6 7 8 9       SlotRequest = the bag's first five slots
        Q               SlotRequest = the next filled weapon slot after the
                        one the hand's item came from
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

from combat.nodes import (
    FN_ADD_II, FN_AND, FN_EQ_II, FN_LESS_II, FN_MOD_II, FN_OR, FN_SELECT_II, FN_SUB_II,
    FN_WAS_PRESSED,
)
from combat.slot_tuning import (
    BAG_LAST, HAND, HAND_FROM_VAR, MELEE_SLOT, MOVE_DST_VAR, MOVE_FROM_VAR, MOVE_SRC_VAR,
    MOVE_TO_VAR, NO_REQUEST, PRIMARY, SLOT_COUNT, SLOT_KEYS, SLOT_PICK_VAR,
    SLOT_REQUEST_VAR, SLOT_VAR, SLOT_WANT_VAR,
)
from combat.weapon_component.common import _G
from combat.weapon_component.slot_nodes import (
    FN_GE_II, FN_LE_II, FN_NE_II, fits, for_loop,
    not_, op, slot_at, valid,
)
from uebp.graph import out

WEAPON_SLOT_COUNT = MELEE_SLOT - PRIMARY + 1


def _author_find_home(g, item, freed, execs, x0, y0):
    """SlotPick := the first slot from PRIMARY on that ``item`` fits and
    that is empty or is ``freed`` (an int pin), else NO_REQUEST.
    Returns Completed."""
    flow = g.put(SLOT_PICK_VAR, str(NO_REQUEST), execs, x0, y0)
    s, body, done = for_loop(g, PRIMARY, BAG_LAST, [flow], x0 + 260, y0)
    searching = op(g, FN_LESS_II, g.get(SLOT_PICK_VAR, x0 + 260, y0 + 500), 0,
                   x0 + 520, y0 + 500)
    look, _ = g.branch(searching, [body], x0 + 520, y0)
    free = op(g, FN_OR, op(g, FN_EQ_II, s, freed, x0 + 780, y0 + 300),
              not_(g, valid(g, slot_at(g, s, x0 + 780, y0 + 600), x0 + 1040, y0 + 600),
                   x0 + 1300, y0 + 600), x0 + 1560, y0 + 300)
    home = op(g, FN_AND, fits(g, item, s, x0 + 780, y0 + 900), free, x0 + 1820, y0 + 300)
    yes, _ = g.branch(home, [look], x0 + 1820, y0)
    g.put(SLOT_PICK_VAR, s, [yes], x0 + 2080, y0)
    return done


def _author_slot_request(g, in_execs, x0, y0):
    """Serve SlotRequest (see the module docstring). Returns the exec tails."""
    asked = op(g, FN_AND, op(g, FN_GE_II, g.get(SLOT_REQUEST_VAR, x0 - 240, y0 + 300), PRIMARY,
                              x0, y0 + 300),
               op(g, FN_LESS_II, g.get(SLOT_REQUEST_VAR, x0 - 240, y0 + 440), SLOT_COUNT,
                  x0, y0 + 440), x0 + 240, y0 + 300)
    serve, idle = g.branch(asked, in_execs, x0 + 500, y0)
    flow = g.put(SLOT_WANT_VAR, g.get(SLOT_REQUEST_VAR, x0 + 520, y0 + 300), [serve],
                 x0 + 760, y0)
    flow = g.put(SLOT_REQUEST_VAR, str(NO_REQUEST), [flow], x0 + 1020, y0)
    want = g.get(SLOT_WANT_VAR, x0 + 1020, y0 + 300)
    target = slot_at(g, want, x0 + 1280, y0 + 300)
    hand = slot_at(g, HAND, x0 + 1280, y0 + 500)
    filled, empty = g.branch(valid(g, target, x0 + 1540, y0 + 300), [flow], x0 + 1540, y0)

    # A filled slot: the hand's item goes home, then the asked one comes up.
    holding, bare = g.branch(valid(g, hand, x0 + 1800, y0 + 300), [filled], x0 + 1800, y0)
    searched = _author_find_home(g, hand, want, [holding], x0 + 2060, y0 - 1400)
    found = op(g, FN_GE_II, g.get(SLOT_PICK_VAR, x0 + 4400, y0 + 300), PRIMARY,
               x0 + 4660, y0 + 300)
    homed, no_home = g.branch(found, [searched], x0 + 4660, y0)
    stowed = g.iput(hand, SLOT_VAR, g.get(SLOT_PICK_VAR, x0 + 4660, y0 + 500), [homed],
                    x0 + 4920, y0)
    took = g.iput(target, SLOT_VAR, str(HAND), [stowed, bare], x0 + 5180, y0)
    took = g.put(HAND_FROM_VAR, want, [took], x0 + 5440, y0)

    # An empty slot: the hand's item goes back if that is where it came from.
    holding2, bare2 = g.branch(valid(g, hand, x0 + 1800, y0 + 1300), [empty],
                               x0 + 1800, y0 + 1000)
    came = op(g, FN_AND, op(g, FN_EQ_II, g.get(HAND_FROM_VAR, x0 + 1800, y0 + 1500), want,
                            x0 + 2060, y0 + 1500),
              fits(g, hand, want, x0 + 2060, y0 + 1700), x0 + 3500, y0 + 1500)
    back, stay = g.branch(came, [holding2], x0 + 3760, y0 + 1000)
    put_back = g.iput(hand, SLOT_VAR, want, [back], x0 + 4020, y0 + 1000)
    return [took, no_home, put_back, stay, bare2, idle]


def _author_slot_move(g, in_execs, x0, y0):
    """Serve MoveFrom -> MoveTo (see the module docstring). Returns the exec
    tails."""
    asked = op(g, FN_GE_II, g.get(MOVE_FROM_VAR, x0 - 240, y0 + 300), 0, x0, y0 + 300)
    serve, idle = g.branch(asked, in_execs, x0 + 260, y0)
    flow = g.put(MOVE_SRC_VAR, g.get(MOVE_FROM_VAR, x0 + 280, y0 + 300), [serve], x0 + 520, y0)
    flow = g.put(MOVE_DST_VAR, g.get(MOVE_TO_VAR, x0 + 540, y0 + 300), [flow], x0 + 780, y0)
    flow = g.put(MOVE_FROM_VAR, str(NO_REQUEST), [flow], x0 + 1040, y0)
    flow = g.put(MOVE_TO_VAR, str(NO_REQUEST), [flow], x0 + 1300, y0)
    src_i = g.get(MOVE_SRC_VAR, x0 + 1300, y0 + 300)
    dst_i = g.get(MOVE_DST_VAR, x0 + 1300, y0 + 440)
    sane = op(g, FN_AND,
              op(g, FN_AND, op(g, FN_GE_II, dst_i, 0, x0 + 1560, y0 + 300),
                 op(g, FN_LESS_II, dst_i, SLOT_COUNT, x0 + 1560, y0 + 440), x0 + 1820, y0 + 300),
              op(g, FN_AND, op(g, FN_LESS_II, src_i, SLOT_COUNT, x0 + 1560, y0 + 580),
                 op(g, FN_NE_II, src_i, dst_i, x0 + 1560, y0 + 720), x0 + 1820, y0 + 580),
              x0 + 2080, y0 + 300)
    ok, bad = g.branch(sane, [flow], x0 + 2080, y0)
    src = slot_at(g, src_i, x0 + 2340, y0 + 300)
    dst = slot_at(g, dst_i, x0 + 2340, y0 + 500)
    carried, nothing = g.branch(valid(g, src, x0 + 2600, y0 + 300), [ok], x0 + 2600, y0)
    goes, refused = g.branch(fits(g, src, dst_i, x0 + 2600, y0 + 700), [carried],
                             x0 + 4000, y0)
    taken, open_ = g.branch(valid(g, dst, x0 + 4260, y0 + 300), [goes], x0 + 4260, y0)
    swaps, stuck = g.branch(fits(g, dst, src_i, x0 + 4260, y0 + 700), [taken],
                            x0 + 5660, y0)
    swapped = g.iput(dst, SLOT_VAR, src_i, [swaps], x0 + 5920, y0)
    moved = g.iput(src, SLOT_VAR, dst_i, [swapped, open_], x0 + 6180, y0)
    # Into the hand, it came from MoveFrom; out of it, the swapped-in one
    # came from MoveTo.
    up, not_up = g.branch(op(g, FN_EQ_II, dst_i, HAND, x0 + 6180, y0 + 300), [moved], x0 + 6440, y0)
    t1 = g.put(HAND_FROM_VAR, src_i, [up], x0 + 6700, y0)
    down, other = g.branch(op(g, FN_EQ_II, src_i, HAND, x0 + 6440, y0 + 700), [not_up],
                           x0 + 6700, y0 + 400)
    t2 = g.put(HAND_FROM_VAR, dst_i, [down], x0 + 6960, y0 + 400)
    return [t1, t2, other, stuck, refused, nothing, bad, idle]


def _author_slot_keys(ed, pc_out, switch_pressed, in_execs, x0, y0):
    """1-9 and Q raise SlotRequest (see the module docstring). Returns the
    exec tails."""
    g = _G(ed)
    flow = list(in_execs)
    for i, (var, _key, slot) in enumerate(SLOT_KEYS):
        x = x0 + i * 520
        pressed = out(g.call(FN_WAS_PRESSED, x, y0 + 300, self=pc_out,
                             Key=g.get(var, x - 240, y0 + 440)))
        hit, miss = g.branch(pressed, flow, x + 240, y0)
        flow = [g.put(SLOT_REQUEST_VAR, str(slot), [hit], x + 240, y0 - 200), miss]

    x = x0 + len(SLOT_KEYS) * 520
    hit, miss = g.branch(switch_pressed, flow, x, y0)
    flow = g.put(SLOT_PICK_VAR, str(NO_REQUEST), [hit], x + 260, y0)
    came = g.get(HAND_FROM_VAR, x, y0 + 500)
    weapon_from = op(g, FN_AND, op(g, FN_GE_II, came, PRIMARY, x + 260, y0 + 500),
                     op(g, FN_LE_II, came, MELEE_SLOT, x + 260, y0 + 640), x + 520, y0 + 500)
    base = out(g.call(FN_SELECT_II, x + 780, y0 + 500, A=came, B=MELEE_SLOT,
                      bPickA=weapon_from))
    off, body, done = for_loop(g, 1, WEAPON_SLOT_COUNT, [flow], x + 520, y0)
    # ((base - 1 + off) mod 4) + 1: the weapon slots after base, round.
    step = op(g, FN_ADD_II, op(g, FN_SUB_II, base, 1, x + 1040, y0 + 500), off,
              x + 1300, y0 + 500)
    c = op(g, FN_ADD_II, op(g, FN_MOD_II, step, WEAPON_SLOT_COUNT, x + 1560, y0 + 500),
           PRIMARY, x + 1820, y0 + 500)
    look, _ = g.branch(op(g, FN_LESS_II, g.get(SLOT_PICK_VAR, x + 780, y0 + 300), 0,
                          x + 1040, y0 + 300), [body], x + 1040, y0)
    there, _ = g.branch(valid(g, slot_at(g, c, x + 2080, y0 + 500), x + 2340, y0 + 500),
                        [look], x + 2340, y0)
    g.put(SLOT_PICK_VAR, c, [there], x + 2600, y0)
    found, none = g.branch(op(g, FN_GE_II, g.get(SLOT_PICK_VAR, x + 780, y0 - 300), PRIMARY,
                              x + 1040, y0 - 300), [done], x + 1300, y0 - 400)
    asked = g.put(SLOT_REQUEST_VAR, g.get(SLOT_PICK_VAR, x + 1300, y0 - 600), [found],
                  x + 1560, y0 - 400)
    ed.add_comment_to_nodes(
        "1-4 bring a weapon slot's item to hand, 5-9 the bag's first five, Q the "
        "next filled weapon slot (slot_moves.py). Each only raises SlotRequest.",
        g.made[:3])
    return [asked, none, miss]


def _author_slot_serve(ed, in_execs, x0, y0):
    """The request, then the move. Returns the exec tails."""
    g = _G(ed)
    tails = _author_slot_request(g, in_execs, x0, y0)
    tails = _author_slot_move(g, tails, x0, y0 + 3000)
    ed.add_comment_to_nodes(
        "SlotRequest brings a slot's item to hand (the hand's going home first, "
        "or back where it came from); MoveFrom/MoveTo is the HUD's drag, a swap "
        "where both fit (slot_moves.py).", g.made[:3])
    return tails
