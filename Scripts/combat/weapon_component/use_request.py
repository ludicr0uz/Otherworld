"""A right click on a slot in the I panel: use that slot's item
(graphics_menu/inv_drag.py asks AskUseSlot; slot_tuning.py has the codes).

    every Tick, with authority, first in the slot serve (slot_moves.py), so
    what it raises is served this same Tick:
    UseRequest a slot code (0 .. SLOT_COUNT-1):
        UseWant := UseRequest, UseRequest := NO_REQUEST
        item := SlotItems[UseWant]; valid ->
            a garment (ClothingSlot >= 0)   WearRequest := UseWant: worn,
                into its own slot, one already worn there taking the slot
                it left (wear_drag.py serves it, next Tick)
            a weapon (WeaponKind >= 0):
                in a weapon slot already      SlotRequest := UseWant (to hand)
                in the hand or the bag        UseFree := the first free weapon
                    slot it fits, UseFit := the first it fits at all (for a
                    long gun the primary); MoveFrom := UseWant, MoveTo :=
                    UseFree, or UseFit when none is free: the move swaps
                    what was there into the slot the weapon left
            anything else (food, the matches, wood, the stick)
                                              SlotRequest := UseWant (to hand,
                                              for the fire key to use it)

It only raises the requests the Tick already serves, so nothing about a
wear, a move or a slot request changed, and the record is marked where
they are.
"""

from combat.slot_tuning import (
    MELEE_SLOT, NO_REQUEST, PRIMARY, SLOT_COUNT, SLOT_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR,
    USE_FIT_VAR, USE_FREE_VAR, USE_REQUEST_VAR, USE_WANT_VAR, WEAPON_KIND_VAR,
)
from combat.wear_tuning import CLOTHING_SLOT_VAR, WEAR_REQUEST_VAR
from combat.weapon_component.slot_nodes import fits, for_loop, not_, op, slot_at, valid
from uebp.graph import out
from uebp.nodes.math import FN_AND, FN_GE_II, FN_LESS_II, FN_LE_II, FN_SELECT_II


def _author_weapon_slot(g, item, want, execs):
    """UseFree / UseFit over the weapon slots (see the module docstring),
    then the move. Returns the exec tails."""
    flow = g.put(USE_FREE_VAR, str(NO_REQUEST), execs)
    flow = g.put(USE_FIT_VAR, str(NO_REQUEST), [flow])
    s, body, done = for_loop(g, PRIMARY, MELEE_SLOT, [flow])
    ok, _ = g.branch(fits(g, item, s), [body])
    first, _ = g.branch(op(g, FN_LESS_II, g.get(USE_FIT_VAR), 0), [ok])
    noted = g.put(USE_FIT_VAR, s, [first])
    free = op(g, FN_AND, op(g, FN_LESS_II, g.get(USE_FREE_VAR), 0),
              not_(g, valid(g, slot_at(g, s))))
    room, _ = g.branch(free, [noted])
    g.put(USE_FREE_VAR, s, [room])
    pick = out(g.call(FN_SELECT_II, A=g.get(USE_FREE_VAR), B=g.get(USE_FIT_VAR),
                      bPickA=op(g, FN_GE_II, g.get(USE_FREE_VAR), 0)))
    found, none = g.branch(op(g, FN_GE_II, pick, PRIMARY), [done])
    flow = g.put(MOVE_TO_VAR, pick, [found])
    flow = g.put(MOVE_FROM_VAR, want, [flow])
    return [flow, none]


def _author_use_request(g, in_execs):
    """Serve UseRequest (see the module docstring). Returns the exec tails."""
    asked = op(g, FN_AND, op(g, FN_GE_II, g.get(USE_REQUEST_VAR), 0),
               op(g, FN_LESS_II, g.get(USE_REQUEST_VAR), SLOT_COUNT))
    serve, idle = g.branch(asked, in_execs)
    flow = g.put(USE_WANT_VAR, g.get(USE_REQUEST_VAR), [serve])
    flow = g.put(USE_REQUEST_VAR, str(NO_REQUEST), [flow])
    want = g.get(USE_WANT_VAR)
    item = slot_at(g, want)
    there, nothing = g.branch(valid(g, item), [flow])
    garment, other = g.branch(op(g, FN_GE_II, g.iget(item, CLOTHING_SLOT_VAR), 0), [there])
    worn = g.put(WEAR_REQUEST_VAR, want, [garment])
    weapon, plain = g.branch(op(g, FN_GE_II, g.iget(item, WEAPON_KIND_VAR), 0), [other])
    in_slot = op(g, FN_AND, op(g, FN_GE_II, want, PRIMARY), op(g, FN_LE_II, want, MELEE_SLOT))
    equipped, loose = g.branch(in_slot, [weapon])
    to_hand = g.put(SLOT_REQUEST_VAR, want, [equipped, plain])
    tails = _author_weapon_slot(g, item, want, [loose])
    g.ed.add_comment_to_nodes(
        f"{USE_REQUEST_VAR}, served with authority: the I panel's right click on a slot. "
        "A garment is worn (WearRequest); a weapon in the hand or the bag goes to a free "
        "weapon slot it fits, else swaps with the first it fits (MoveFrom/To); a weapon "
        "slot's item and anything else come to hand (SlotRequest) (use_request.py).",
        g.made[:3])
    return tails + [worn, to_hand, nothing, idle]
