"""DrawHUD, with the I panel open: the mouse on the inventory's slots
(inv_consts.py has the names, combat/slot_tuning.py the codes).

    InvOver := the slot code under the cursor (the hand's cell, a weapon
               cell or a bag cell; a worn cell i is WORN_CODE_FIRST + i, and
               moves the caret, WearSel, there), NO_SLOT over none
    left button pressed over a filled slot -> InvDragFrom := InvOver
    left button released with a drag on:
        over the slot it started on (a click): a weapon or bag slot ->
            the weapon component's AskSlot(it) (bring it to hand);
            a worn slot -> WearTakeOffRequested (Tick takes it off)
        over another slot:
            slot to slot -> AskMove(InvDragFrom, InvOver)
                (the component swaps them where both fit; only a weapon
                fits a weapon slot)
            worn to slot -> AskTakeOff(the worn slot, InvOver) (taken off
                into it: the hand or a bag slot)
            slot to worn -> AskWear(InvDragFrom) (worn if a garment,
                into its own slot whichever cell it was dropped on)
            worn to worn -> nothing
        over no slot:
            outside the inventory (none of INV_AREAS under the cursor) ->
                AskDrop(InvDragFrom) (set down on the ground: a slot's
                item, or a worn garment, whose code the component reads as
                SLOT_COUNT + its worn slot)
            between two slots -> nothing
        InvDragFrom := NO_SLOT

While the drag is on, inv_carry.py draws the item's icon on the cursor and
holds the view still.

The HUD only asks, as the I panel's take-off does, by calling the weapon
component's events (ask.py, combat/weapon_component/asks.py): the component
serves the request on its own Tick (slot_moves.py), where what fits where is
known. DrawHUD because only it knows where a cell is (cursor.py); a -nullrhi
probe writes the component's request variables instead.
"""

from uebp.vars import declare, defaults
from graphics_menu.inv_consts import DRAG_TABLE
from uebp.graph import out
from combat.ask_consts import ASK_DROP, ASK_MOVE, ASK_SLOT, ASK_TAKE_OFF, ASK_WEAR
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import PRIMARY, SLOT_ITEMS_VAR
from combat.wear_tuning import WORN_VAR
from graphics_menu.ask import ask
from graphics_menu.cursor import _clicked, _pc, _under, author_row_cursor
from graphics_menu.cursor_consts import CLICK_KEY, CURSOR_ROW_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.inv_consts import (
    DRAG_BOXES, DRAG_FROM_VAR, INV_AREAS, INV_OVER_VAR, NO_SLOT, WORN_CODE_FIRST,
)
from graphics_menu.loot_find import put
from graphics_menu.ui_graph import part
from graphics_menu.umg_consts import WBP_HUD
from graphics_menu.wear_consts import WEAR_SEL_VAR, WEAR_SLOTS_BOX, WEAR_TAKE_VAR
from uebp.nodes.actor import FN_RELEASED
from uebp.nodes.array import FN_ARR_GET, FN_ARR_VALID
from uebp.nodes.math import FN_ADD_II, FN_AND, FN_EQ_II, FN_GE_II, FN_LESS_II, FN_OR, FN_SUB_II
from uebp.nodes.system import FN_IS_VALID


def declare_inv_vars(ed):
    """The HUD's two drag variables. Defaults: inv_defaults()."""
    declare(ed, DRAG_TABLE)


def inv_defaults():
    return defaults(DRAG_TABLE)


def _author_over(ed, in_execs, made):
    """InvOver := the slot code under the cursor. Returns the exec tails."""
    flow = _setter(ed, INV_OVER_VAR, NO_SLOT, in_execs, made)
    flow = [flow]
    for box, first, count in DRAG_BOXES:
        # A worn cell is the caret's row too.
        flow = author_row_cursor(ed, part(ed, WBP_HUD, box), count, flow,
                                 row_var=WEAR_SEL_VAR if box == WEAR_SLOTS_BOX else None)
        row = _get(ed, CURSOR_ROW_VAR, made)
        hit, miss = _branch(ed, out(_call(ed, FN_GE_II, made, A=row, B=0)), flow, made)
        code = out(_call(ed, FN_ADD_II, made, A=row, B=first))
        flow = [put(ed, INV_OVER_VAR, code, [hit], made), miss]
    return flow


def _author_press(ed, wc, in_execs, made):
    """A press over a filled slot starts a drag. Returns the exec tails."""
    over = _get(ed, INV_OVER_VAR, made)
    on_slot = _call(ed, FN_GE_II, made, A=over, B=0)
    pressed = _call(ed, FN_AND, made, A=_clicked(ed, made), B=out(on_slot))
    hit, miss = _branch(ed, out(pressed), in_execs, made)
    # A worn cell: filled if Worn holds a garment there.
    hit, on_worn = _branch(ed, out(_call(ed, FN_LESS_II, made, A=over,
                                          B=WORN_CODE_FIRST)), [hit],
                           made)
    worn = _get(ed, WORN_VAR, made, WEAPON_COMP_CLASS_PATH, wc)
    at = out(_call(ed, FN_SUB_II, made, A=over, B=WORN_CODE_FIRST))
    known, wild = _branch(ed, out(_call(ed, FN_ARR_VALID, made,
                                         TargetArray=worn, IndexToTest=at)),
                          [on_worn], made)
    garment = _call(ed, FN_ARR_GET, made, TargetArray=worn, Index=at)
    dressed, bare = _branch(ed, out(_call(ed, FN_IS_VALID, made,
                                           Object=out(garment, "Item"))),
                            [known], made)
    items = _get(ed, SLOT_ITEMS_VAR, made, WEAPON_COMP_CLASS_PATH, wc)
    there, past = _branch(ed, out(_call(ed, FN_ARR_VALID, made,
                                         TargetArray=items, IndexToTest=over)),
                          [hit], made)
    item = _call(ed, FN_ARR_GET, made, TargetArray=items, Index=over)
    filled, empty = _branch(ed, out(_call(ed, FN_IS_VALID, made,
                                           Object=out(item, "Item"))),
                            [there], made)
    began = put(ed, DRAG_FROM_VAR, over, [filled, dressed], made)
    return [began, empty, past, miss, wild, bare]


def _author_release(ed, wc, in_execs, made):
    """A release ends the drag: a click asks for the slot, a drop for the
    move. Returns the exec tails."""
    released = _call(ed, FN_RELEASED, made, self=_pc(ed, made), Key=CLICK_KEY)
    dragging = _call(ed, FN_GE_II, made, A=_get(ed, DRAG_FROM_VAR, made), B=0)
    ended = _call(ed, FN_AND, made, A=out(released), B=out(dragging))
    end, still = _branch(ed, out(ended), in_execs, made)
    over = _get(ed, INV_OVER_VAR, made)
    start = _get(ed, DRAG_FROM_VAR, made)
    on_slot, off = _branch(ed, out(_call(ed, FN_GE_II, made, A=over, B=0)), [end], made)
    same, moved = _branch(ed, out(_call(ed, FN_EQ_II, made, A=over, B=start)), [on_slot], made)
    def worn_cell(code, execs):
        """Branch: ``code`` is a worn cell's, or a slot's."""
        return _branch(ed, out(_call(ed, FN_GE_II, made, A=code, B=WORN_CODE_FIRST)), execs, made)

    # A click: a worn garment comes off (Tick's take-off, the caret being on
    # it since the press); a weapon or bag slot's item comes to hand (the
    # hand's own does nothing).
    off_ask, on_inv = worn_cell(over, [same])
    took = _setter(ed, WEAR_TAKE_VAR, "true", [off_ask], made)
    pick, hand = _branch(ed, out(_call(ed, FN_GE_II, made, A=over, B=PRIMARY)), [on_inv], made)
    asked = ask(ed, wc, ASK_SLOT, [pick], made, Slot=over)
    # A drop on another cell. A worn garment onto a slot: taken off into it.
    from_worn, from_inv = worn_cell(start, [moved])
    stays, lands = worn_cell(over, [from_worn])
    slot = out(_call(ed, FN_SUB_II, made, A=start, B=WORN_CODE_FIRST))
    taken = ask(ed, wc, ASK_TAKE_OFF, [lands], made, Slot=slot, To=over)
    # A slot's item onto the worn grid: worn. Onto a slot: the move.
    wear, move = worn_cell(over, [from_inv])
    wearing = ask(ed, wc, ASK_WEAR, [wear], made, From=start)
    flow = ask(ed, wc, ASK_MOVE, [move], made, From=start, To=over)
    # Over no slot: outside the inventory it is set down on the ground. The
    # HUD's code for a worn cell is the component's (SLOT_COUNT + the slot).
    inside = _under(ed, part(ed, WBP_HUD, INV_AREAS[0]), made)
    for area in INV_AREAS[1:]:
        inside = out(_call(ed, FN_OR, made, A=inside,
                           B=_under(ed, part(ed, WBP_HUD, area), made)))
    kept, away = _branch(ed, inside, [off], made)
    dropped = ask(ed, wc, ASK_DROP, [away], made, From=start)
    done = _setter(ed, DRAG_FROM_VAR, NO_SLOT,
                   [took, asked, hand, taken, stays, wearing, flow, kept, dropped], made)
    return [done, still]


def author_inv_drag(ed, wc, in_execs):
    """The whole fragment (see the module docstring), on an open I panel.
    ``wc``: the cast weapon component's pin. Returns the exec tails."""
    made = []
    flow = _author_over(ed, in_execs, made)
    flow = _author_press(ed, wc, flow, made)
    flow = _author_release(ed, wc, flow, made)
    ed.add_comment_to_nodes(
        "The mouse on the inventory's slots with the I panel open: a press on a "
        "filled slot starts a drag; the release on the same slot asks for it "
        "in hand (AskSlot) or, worn, off (WearTakeOffRequested); on another "
        "asks for the move (AskMove), the take-off into it (AskTakeOff) or the "
        "wear (AskWear); outside the inventory, for the "
        "item set down on the ground (AskDrop). The weapon component decides "
        "what fits (inv_drag.py).", made[:4])
    return flow
