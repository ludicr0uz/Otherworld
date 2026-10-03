"""DrawHUD, with the I panel open: the mouse on the inventory's slots
(inv_consts.py has the names, combat/slot_tuning.py the codes).

    InvOver := the slot code under the cursor (the hand's cell, a weapon
               cell or a bag cell), NO_SLOT over none
    left button pressed over a filled slot -> InvDragFrom := InvOver
    left button released with a drag on:
        over the slot it started on (a click): a weapon or bag slot ->
            the weapon component's SlotRequest := it (bring it to hand)
        over another slot -> MoveTo := InvOver, MoveFrom := InvDragFrom
            (the component swaps them where both fit; only a weapon fits
            a weapon slot)
        InvDragFrom := NO_SLOT

The HUD only asks, as the I panel's take-off does: the weapon component
serves the request on its own Tick (combat/weapon_component/slot_moves.py),
where what fits where is known. DrawHUD because only it knows where a cell
is (cursor.py); a -nullrhi probe writes the component's variables instead.
"""

from combat.graph import BEL, _at, _connect, _declare, _pin
from combat.nodes import FN_AND, FN_EQ_II, FN_IS_VALID
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import (
    MOVE_FROM_VAR, MOVE_TO_VAR, PRIMARY, SLOT_ITEMS_VAR, SLOT_REQUEST_VAR,
)
from graphics_menu.cursor import _clicked, _pc, author_row_cursor
from graphics_menu.cursor_consts import CLICK_KEY, CURSOR_ROW_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.inv_consts import DRAG_FROM_VAR, INV_OVER_VAR, NO_SLOT, SLOT_BOXES
from graphics_menu.loot_find import put
from graphics_menu.ui_graph import part
from graphics_menu.umg_consts import WBP_HUD

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
    for box, first, count in SLOT_BOXES:
        flow = author_row_cursor(ed, part(ed, WBP_HUD, box, x, y0 - 400), count, flow, x, y0)
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
    items = _get(ed, SLOT_ITEMS_VAR, x0 + 760, y0 + 500, made, WEAPON_COMP_CLASS_PATH, wc)
    there, past = _branch(ed, _out(_call(ed, FN_ARR_VALID, x0 + 1020, y0 + 500, made,
                                         TargetArray=items, IndexToTest=over)),
                          [hit], x0 + 1020, y0, made)
    item = _call(ed, FN_ARR_GET, x0 + 1280, y0 + 500, made, TargetArray=items, Index=over)
    filled, empty = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 1540, y0 + 500, made,
                                           Object=_pin(item, "Item", is_input=False))),
                            [there], x0 + 1540, y0, made)
    began = put(ed, DRAG_FROM_VAR, over, [filled], x0 + 1800, y0, made)
    return [began, empty, past, miss]


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
    # A click: a weapon or bag slot's item to hand (the hand's own does nothing).
    pick, hand = _branch(ed, _out(_call(ed, FN_GE_II, x0 + 1300, y0 + 300, made, A=over,
                                        B=PRIMARY)), [same], x0 + 1300, y0, made)
    asked = _put_on(ed, wc, SLOT_REQUEST_VAR, over, [pick], x0 + 1560, y0, made)
    # A drop on another slot: the move, MoveTo first.
    flow = _put_on(ed, wc, MOVE_TO_VAR, over, [moved], x0 + 1300, y0 + 600, made)
    flow = _put_on(ed, wc, MOVE_FROM_VAR, start, [flow], x0 + 1560, y0 + 600, made)
    done = _setter(ed, DRAG_FROM_VAR, NO_SLOT, [asked, hand, flow, off], x0 + 1820, y0, made)
    return [done, still]


def author_inv_drag(ed, wc, in_execs, x0, y0):
    """The whole fragment (see the module docstring), on an open I panel.
    ``wc``: the cast weapon component's pin. Returns the exec tails."""
    made = []
    flow = _author_over(ed, in_execs, x0, y0, made)
    flow = _author_press(ed, wc, flow, x0 + 16000, y0, made)
    flow = _author_release(ed, wc, flow, x0 + 18200, y0, made)
    ed.add_comment_to_nodes(
        "The mouse on the inventory's slots with the I panel open: a press on a "
        "filled slot starts a drag; the release on the same slot asks for it "
        "in hand (SlotRequest), on another asks for the move (MoveFrom/MoveTo). "
        "The weapon component decides what fits (inv_drag.py).", made[:4])
    return flow
