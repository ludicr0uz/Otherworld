"""DrawHUD, with the I panel open: the mouse on the inventory's slots
(inv_consts.py has the names, combat/slot_tuning.py the codes).

    InvOver := the slot code under the cursor (the hand's cell, a weapon
               cell or a bag cell; a worn cell i is WORN_CODE_FIRST + i, and
               moves the caret, WearSel, there), NO_SLOT over none
    left button pressed over a filled slot -> InvDragFrom := InvOver
    left button released with a drag on:
        over the slot it started on (a click): a weapon or bag slot ->
            the weapon component's SlotRequest := it (bring it to hand);
            a worn slot -> WearTakeOffRequested (Tick takes it off)
        over another slot:
            slot to slot -> MoveTo := InvOver, MoveFrom := InvDragFrom
                (the component swaps them where both fit; only a weapon
                fits a weapon slot)
            worn to slot -> TakeOffTo := InvOver, TakeOffSlot := the worn
                slot (taken off into it: the hand or a bag slot)
            slot to worn -> WearRequest := InvDragFrom (worn if a garment,
                into its own slot whichever cell it was dropped on)
            worn to worn -> nothing
        InvDragFrom := NO_SLOT

The HUD only asks, as the I panel's take-off does: the weapon component
serves the request on its own Tick (combat/weapon_component/slot_moves.py),
where what fits where is known. DrawHUD because only it knows where a cell
is (cursor.py); a -nullrhi probe writes the component's variables instead.
"""

from combat.graph import BEL, _at, _connect, _declare, _pin
from combat.nodes import FN_AND, FN_EQ_II, FN_IS_VALID, FN_LESS_II, FN_SUB_II
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import (
    MOVE_FROM_VAR, MOVE_TO_VAR, PRIMARY, SLOT_ITEMS_VAR, SLOT_REQUEST_VAR,
)
from combat.wear_tuning import TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_REQUEST_VAR, WORN_VAR
from graphics_menu.cursor import _clicked, _pc, author_row_cursor
from graphics_menu.cursor_consts import CLICK_KEY, CURSOR_ROW_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.inv_consts import (
    DRAG_BOXES, DRAG_FROM_VAR, INV_OVER_VAR, NO_SLOT, WORN_CODE_FIRST,
)
from graphics_menu.loot_find import put
from graphics_menu.ui_graph import part
from graphics_menu.umg_consts import WBP_HUD
from graphics_menu.wear_consts import WEAR_SEL_VAR, WEAR_SLOTS_BOX, WEAR_TAKE_VAR

FN_RELEASED = "/Script/Engine.PlayerController.WasInputKeyJustReleased"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_ARR_VALID = "/Script/Engine.KismetArrayLibrary.Array_IsValidIndex"

_INTS = (DRAG_FROM_VAR, INV_OVER_VAR)


def declare_inv_vars(ed):
    """The HUD's two drag variables. Defaults: inv_defaults()."""
    for name in _INTS:
        _declare(ed, name, BEL.get_basic_type_by_name("int"))


def inv_defaults():
    return {name: NO_SLOT for name in _INTS}


def _put_on(ed, wc, var, value, in_execs, x, y, made):
    """The weapon component's ``var`` := a pin."""
    n = _at(ed.add_set_member_variable_node(var, WEAPON_COMP_CLASS_PATH), x, y)
    made.append(n)
    _connect(wc, _pin(n, "self"))
    _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return BEL.find_then_pin(n)


def _author_over(ed, in_execs, x0, y0, made):
    """InvOver := the slot code under the cursor. Returns the exec tails."""
    flow = _setter(ed, INV_OVER_VAR, NO_SLOT, in_execs, x0, y0, made)
    flow = [flow]
    x = x0 + 300
    for box, first, count in DRAG_BOXES:
        # A worn cell is the caret's row too.
        flow = author_row_cursor(ed, part(ed, WBP_HUD, box, x, y0 - 400), count, flow, x, y0,
                                 row_var=WEAR_SEL_VAR if box == WEAR_SLOTS_BOX else None)
        x += 4000
        row = _get(ed, CURSOR_ROW_VAR, x, y0 + 300, made)
        hit, miss = _branch(ed, _out(_call(ed, FN_GE_II, x + 240, y0 + 300, made, A=row, B=0)),
                            flow, x + 500, y0, made)
        code = _out(_call(ed, FN_ADD_II, x + 500, y0 + 300, made, A=row, B=first))
        flow = [put(ed, INV_OVER_VAR, code, [hit], x + 760, y0, made), miss]
        x += 1100
    return flow


def _author_press(ed, wc, in_execs, x0, y0, made):
    """A press over a filled slot starts a drag. Returns the exec tails."""
    over = _get(ed, INV_OVER_VAR, x0, y0 + 300, made)
    on_slot = _call(ed, FN_GE_II, x0 + 240, y0 + 300, made, A=over, B=0)
    pressed = _call(ed, FN_AND, x0 + 500, y0 + 300, made, A=_clicked(ed, x0 + 240, y0 + 440,
                                                                       made),
                    B=_out(on_slot))
    hit, miss = _branch(ed, _out(pressed), in_execs, x0 + 760, y0, made)
    # A worn cell: filled if Worn holds a garment there.
    hit, on_worn = _branch(ed, _out(_call(ed, FN_LESS_II, x0 + 760, y0 - 300, made, A=over,
                                          B=WORN_CODE_FIRST)), [hit], x0 + 1020, y0 - 400,
                           made)
    worn = _get(ed, WORN_VAR, x0 + 1020, y0 - 900, made, WEAPON_COMP_CLASS_PATH, wc)
    at = _out(_call(ed, FN_SUB_II, x0 + 1020, y0 - 760, made, A=over, B=WORN_CODE_FIRST))
    known, wild = _branch(ed, _out(_call(ed, FN_ARR_VALID, x0 + 1280, y0 - 900, made,
                                         TargetArray=worn, IndexToTest=at)),
                          [on_worn], x0 + 1280, y0 - 1200, made)
    garment = _call(ed, FN_ARR_GET, x0 + 1540, y0 - 900, made, TargetArray=worn, Index=at)
    dressed, bare = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 1800, y0 - 900, made,
                                           Object=_pin(garment, "Item", is_input=False))),
                            [known], x0 + 1800, y0 - 1200, made)
    items = _get(ed, SLOT_ITEMS_VAR, x0 + 760, y0 + 500, made, WEAPON_COMP_CLASS_PATH, wc)
    there, past = _branch(ed, _out(_call(ed, FN_ARR_VALID, x0 + 1020, y0 + 500, made,
                                         TargetArray=items, IndexToTest=over)),
                          [hit], x0 + 1280, y0, made)
    item = _call(ed, FN_ARR_GET, x0 + 1280, y0 + 500, made, TargetArray=items, Index=over)
    filled, empty = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 1540, y0 + 500, made,
                                           Object=_pin(item, "Item", is_input=False))),
                            [there], x0 + 1540, y0, made)
    began = put(ed, DRAG_FROM_VAR, over, [filled, dressed], x0 + 2060, y0, made)
    return [began, empty, past, miss, wild, bare]


def _author_release(ed, wc, in_execs, x0, y0, made):
    """A release ends the drag: a click asks for the slot, a drop for the
    move. Returns the exec tails."""
    released = _call(ed, FN_RELEASED, x0, y0 + 440, made, self=_pc(ed, x0 - 240, y0 + 440, made),
                     Key=CLICK_KEY)
    dragging = _call(ed, FN_GE_II, x0, y0 + 300, made,
                     A=_get(ed, DRAG_FROM_VAR, x0 - 240, y0 + 300, made), B=0)
    ended = _call(ed, FN_AND, x0 + 260, y0 + 300, made, A=_out(released), B=_out(dragging))
    end, still = _branch(ed, _out(ended), in_execs, x0 + 520, y0, made)
    over = _get(ed, INV_OVER_VAR, x0 + 520, y0 + 300, made)
    start = _get(ed, DRAG_FROM_VAR, x0 + 520, y0 + 440, made)
    on_slot, off = _branch(ed, _out(_call(ed, FN_GE_II, x0 + 780, y0 + 300, made, A=over,
                                          B=0)), [end], x0 + 780, y0, made)
    same, moved = _branch(ed, _out(_call(ed, FN_EQ_II, x0 + 1040, y0 + 300, made, A=over,
                                         B=start)), [on_slot], x0 + 1040, y0, made)
    def worn_cell(code, execs, x, y):
        """Branch: ``code`` is a worn cell's, or a slot's."""
        return _branch(ed, _out(_call(ed, FN_GE_II, x, y + 300, made, A=code,
                                      B=WORN_CODE_FIRST)), execs, x, y, made)

    # A click: a worn garment comes off (Tick's take-off, the caret being on
    # it since the press); a weapon or bag slot's item comes to hand (the
    # hand's own does nothing).
    off_ask, on_inv = worn_cell(over, [same], x0 + 1300, y0 - 600)
    took = _setter(ed, WEAR_TAKE_VAR, "true", [off_ask], x0 + 1560, y0 - 600, made)
    pick, hand = _branch(ed, _out(_call(ed, FN_GE_II, x0 + 1300, y0 + 300, made, A=over,
                                        B=PRIMARY)), [on_inv], x0 + 1560, y0, made)
    asked = _put_on(ed, wc, SLOT_REQUEST_VAR, over, [pick], x0 + 1820, y0, made)
    # A drop on another cell. A worn garment onto a slot: taken off into it.
    from_worn, from_inv = worn_cell(start, [moved], x0 + 1300, y0 + 600)
    stays, lands = worn_cell(over, [from_worn], x0 + 1560, y0 + 1200)
    flow = _put_on(ed, wc, TAKE_OFF_TO_VAR, over, [lands], x0 + 1820, y0 + 1200, made)
    slot = _out(_call(ed, FN_SUB_II, x0 + 1820, y0 + 1500, made, A=start, B=WORN_CODE_FIRST))
    taken = _put_on(ed, wc, TAKE_OFF_VAR, slot, [flow], x0 + 2080, y0 + 1200, made)
    # A slot's item onto the worn grid: worn. Onto a slot: the move, MoveTo first.
    wear, move = worn_cell(over, [from_inv], x0 + 1560, y0 + 600)
    wearing = _put_on(ed, wc, WEAR_REQUEST_VAR, start, [wear], x0 + 1820, y0 + 900, made)
    flow = _put_on(ed, wc, MOVE_TO_VAR, over, [move], x0 + 1820, y0 + 600, made)
    flow = _put_on(ed, wc, MOVE_FROM_VAR, start, [flow], x0 + 2080, y0 + 600, made)
    done = _setter(ed, DRAG_FROM_VAR, NO_SLOT,
                   [took, asked, hand, taken, stays, wearing, flow, off], x0 + 2340, y0, made)
    return [done, still]


def author_inv_drag(ed, wc, in_execs, x0, y0):
    """The whole fragment (see the module docstring), on an open I panel.
    ``wc``: the cast weapon component's pin. Returns the exec tails."""
    made = []
    flow = _author_over(ed, in_execs, x0, y0, made)
    flow = _author_press(ed, wc, flow, x0 + 21200, y0, made)
    flow = _author_release(ed, wc, flow, x0 + 23800, y0, made)
    ed.add_comment_to_nodes(
        "The mouse on the inventory's slots with the I panel open: a press on a "
        "filled slot starts a drag; the release on the same slot asks for it "
        "in hand (SlotRequest) or, worn, off (WearTakeOffRequested); on another "
        "asks for the move (MoveFrom/MoveTo), the take-off into it (TakeOffTo, "
        "TakeOffSlot) or the wear (WearRequest). The weapon component decides "
        "what fits (inv_drag.py).", made[:4])
    return flow
