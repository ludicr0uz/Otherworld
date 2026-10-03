"""DrawHUD: a scrolling tab's scroll bar dragged by the mouse (a TuneTab with
visible_rows: tune_tab.py).

    the left button pressed over the list's box but over none of its rows
                                  ScrollGrab = true (that strip is the bar)
    ScrollGrab:
        the button still down     ScrollAt = how far down the box the cursor
                                  is, 0 at its top and 1 at its bottom
        else                      ScrollGrab = false
      and, either way:
        top = the row ScrollAt puts first in the window, 0..rows - visible
              (the bar's thumb centred on the cursor)
        the list's offset = top * TUNE_ROW_H
        the caret kept in top..top + visible - 1

The bar is a picture: no widget is hit-testable and the HUD is the controller
(cursor.py). The ScrollBox's own bar is beside its rows, not over them, so a
press inside the box that lands on no row is on the bar. Only vertical: the
cursor's X is not read once the bar is held.

The list moves a whole row at a time and the caret comes with it, because
tune_draw's follow brings the caret's row into view every frame: a caret left
outside the window would pull the list straight back.

The mouse only writes ScrollGrab and ScrollAt, and the scroll is served from
them, also on the frame the button comes up: probes/probe_menu_scroll.py
raises ScrollGrab for one frame and drags without a mouse.
"""

from uebp.graph import _connect, _pin, out, then
from graphics_menu.cursor import _clicked, _pc, _under
from graphics_menu.cursor_consts import (
    CLICK_KEY, CURSOR_POS_VAR, CURSOR_ROW_VAR, SCROLL_AT_VAR, SCROLL_GRAB_VAR)
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.loot_find import put
from graphics_menu.tune_consts import TUNE_ROW_H
from uebp.nodes.actor import FN_IS_KEY_DOWN
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_BREAK_V2D, FN_DIV_FF, FN_INT_TO_FLOAT, FN_LESS_II, FN_MAX_II,
    FN_MIN_II, FN_MUL_FF, FN_ROUND, FN_SUB_FF)
from uebp.nodes.umg import FN_ABS_TO_LOCAL, FN_GEOMETRY, FN_LOCAL_SIZE, FN_SET_SCROLL_OFFSET


def hidden_rows(tab):
    """The rows a scrolling tab's window cannot show at once: the furthest
    the list scrolls, in rows."""
    return tab.row_count - tab.visible_rows


def thumb_half(tab):
    """Half the bar's thumb, as a fraction of the bar: the thumb is as much
    of the bar as the window is of the list."""
    return tab.visible_rows / (2.0 * tab.row_count)


def rows_per_window(tab):
    """Rows scrolled per whole window's height the thumb's centre travels: it
    runs from thumb_half to 1 - thumb_half, and that is the whole scroll."""
    return hidden_rows(tab) / (1.0 - 2.0 * thumb_half(tab))


def top_row(tab, at):
    """The row a drag to ``at`` (0..1 down the window) puts first: the graph's
    own sum, for the probe."""
    rows = int(round((at - thumb_half(tab)) * rows_per_window(tab)))
    return max(0, min(rows, hidden_rows(tab)))


def _down_the_box(ed, box, made):
    """How far down ``box`` the cursor is: its local Y over the box's height."""
    geo = _call(ed, FN_GEOMETRY, made, self=box)
    local = _call(ed, FN_ABS_TO_LOCAL, made, Geometry=out(geo),
                  AbsoluteCoordinate=_get(ed, CURSOR_POS_VAR, made))
    size = _call(ed, FN_LOCAL_SIZE, made, Geometry=out(geo))
    y = _call(ed, FN_BREAK_V2D, made, InVec=out(local))
    h = _call(ed, FN_BREAK_V2D, made, InVec=out(size))
    return out(_call(ed, FN_DIV_FF, made, A=out(y, "Y"), B=out(h, "Y")))


def author_scroll_drag(ed, tab, box, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    # The press: inside the box and on no row (tune_draw's row test has just
    # left CursorRow). The click is ANDed with the box first: the button is
    # only ever read with the cursor over something.
    press = _call(ed, FN_AND, made, A=_clicked(ed, made), B=_under(ed, box, made))
    off_rows = _call(ed, FN_LESS_II, made, A=_get(ed, CURSOR_ROW_VAR, made), B=0)
    on_bar = _call(ed, FN_AND, made, A=out(press), B=out(off_rows))
    grab, free = _branch(ed, out(on_bar), in_execs, made)
    flow = [_setter(ed, SCROLL_GRAB_VAR, "true", [grab], made), free]

    held, idle = _branch(ed, _get(ed, SCROLL_GRAB_VAR, made), flow, made)
    down = _call(ed, FN_IS_KEY_DOWN, made, self=_pc(ed, made), Key=CLICK_KEY)
    still, let_go = _branch(ed, out(down), [held], made)
    at = put(ed, SCROLL_AT_VAR, _down_the_box(ed, box, made), [still], made)
    dropped = _setter(ed, SCROLL_GRAB_VAR, "false", [let_go], made)

    half = thumb_half(tab)
    # Plain sums and Min / Max, not a clamp or a range map: the verifier
    # counts those of the HUD's as the sliders' and the clock's.
    past = _call(ed, FN_SUB_FF, made, A=_get(ed, SCROLL_AT_VAR, made), B=half)
    rows = _call(ed, FN_MUL_FF, made, A=out(past), B=rows_per_window(tab))
    over = _call(ed, FN_MIN_II, made, A=out(_call(ed, FN_ROUND, made, A=out(rows))),
                 B=hidden_rows(tab))
    top = _call(ed, FN_MAX_II, made, A=out(over), B=0)
    offset = _call(ed, FN_MUL_FF, made,
                   A=out(_call(ed, FN_INT_TO_FLOAT, made, InInt=out(top))), B=TUNE_ROW_H)
    scroll = _call(ed, FN_SET_SCROLL_OFFSET, made, self=box, NewScrollOffset=out(offset))
    for e in (at, dropped):
        _connect(e, _pin(scroll, "execute"))
    last = _call(ed, FN_ADD_II, made, A=out(top), B=tab.visible_rows - 1)
    under = _call(ed, FN_MIN_II, made, A=_get(ed, tab.row_var, made), B=out(last))
    kept = _call(ed, FN_MAX_II, made, A=out(under), B=out(top))
    moved = put(ed, tab.row_var, out(kept), [then(scroll)], made)
    ed.add_comment_to_nodes(
        "A scrolling list's bar dragged: the left button held from a press "
        "beside the rows scrolls the list to where the cursor is, a whole row "
        "at a time, and keeps the caret in the window.", made)
    return [moved, idle]
