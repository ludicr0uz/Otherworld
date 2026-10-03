"""DrawHUD: a tuning tab's panel on WBP_PauseMenu (any TuneTab, tune_tab.py),
from the tab's variables. For the guns:

    NOT (MenuOpen AND TuneOpen)   TunePanel collapsed
    else           shown: row 0's value is TuneWeapons[TuneWeapon], row i's
                   is TuneValues[TuneWeapon * STAT_COUNT + i - 1] (up to
                   the tab's fraction_digits decimals, no grouping; a dash
                   where the tab's live mask says the stat is not the
                   subject's own), the
                   caret on TuneRow -- on BACK when it is past the list, or
                   on the save row of a tab that has one --
                   and "saved to ..." while TuneSaved. A scrolling tab's
                   list is scrolled to the caret's row, or
                   by the mouse dragging its bar (tune_scroll.py)

Reads, with one exception: BACK. Its Enter and its click lower TuneOpen here
(cursor.author_back_row says why it is not Tick's); everything else
tune_tick.py and its siblings decide. The M panel's own rows are hidden while
a tab is up (menu_screens.author_pause_menu).
"""

from uebp.graph import _connect, _pin, _set, out, then
from graphics_menu.cursor import (
    author_back_row, author_button_row, author_row_cursor, author_widget_click)
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.tune_consts import GUN_TAB, TUNE_DASH
from graphics_menu.tune_scroll import author_scroll_drag
from graphics_menu.ui_graph import mark_rows, member, part, row_value, set_shown, show_if
from graphics_menu.umg_consts import ROW_CARET, WBP_MENU_ROW, WBP_PAUSE_MENU
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_EQ_II, FN_GE_II, FN_MIN_II, FN_MUL_II, FN_SELECT_FF, FN_SELECT_STR,
    FN_SUB_II)
from uebp.nodes.palette import MACRO_FOR_LOOP
from uebp.nodes.system import FN_TEXT_TO_STR, FN_TO_TEXT
from uebp.nodes.umg import FN_CHILD_AT, FN_SCROLL_TO, FN_SET_OPACITY
from graphics_menu import hud_vars as MV


def _item(ed, array_var, index, made):
    n = _call(ed, FN_ARR_GET, made, TargetArray=_get(ed, array_var, made))
    _connect(index, _pin(n, "Index"))
    return out(n, "Item")


def _author_stats(ed, tab, box, in_execs, made):
    """Rows 1..stat_count := the shown subject's cells. Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    made.append(loop)
    loop
    _set(loop, "FirstIndex", 1)
    _set(loop, "LastIndex", tab.stat_count)
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = out(loop, "Index")
    base = _call(ed, FN_MUL_II, made, A=_get(ed, tab.pick_var, made), B=tab.stat_count)
    s = _call(ed, FN_SUB_II, made, A=i, B=1)
    idx = _call(ed, FN_ADD_II, made, A=out(base), B=out(s))
    words = _call(ed, FN_TO_TEXT, made,
                  Value=_item(ed, tab.values_var, out(idx), made),
                  bUseGrouping="false", MaximumFractionalDigits=tab.fraction_digits)
    value = ("text", out(words))
    if tab.live_var:
        # A String here: the number, or the dash of a stat that is not the
        # subject's own. The dash on B, the pin that holds a literal.
        number = _call(ed, FN_TEXT_TO_STR, made, InText=out(words))
        value = out(_call(ed, FN_SELECT_STR, made, A=out(number),
                           B=TUNE_DASH,
                           bPickA=_item(ed, tab.live_var, out(idx),
                                        made)))
    row_value(ed, box, i, value, [out(loop, "LoopBody")])
    return out(loop, "Completed")


def _author_under_caret(ed, tab, widget, test, row, in_execs, made):
    """The caret of a row under the list (BACK, the save row), lit while the
    tab's caret ``test`` ``row``: at or past it for BACK, the last stop, and
    on it for the save row. Returns then."""
    on_it = _call(ed, test, made, A=_get(ed, tab.row_var, made), B=row)
    lit = _call(ed, FN_SELECT_FF, made, A=1.0, B=0.0, bPickA=out(on_it))
    fade = _call(ed, FN_SET_OPACITY, made,
                 self=member(ed, widget, WBP_MENU_ROW, ROW_CARET),
                 InOpacity=out(lit))
    for e in in_execs:
        _connect(e, _pin(fade, "execute"))
    return then(fade)


def _author_follow(ed, tab, box, in_execs, made):
    """A scrolling tab: the caret's row brought into the list's window. On
    BACK the list stays where it is (the last row is already in view).
    Returns then."""
    row = _call(ed, FN_MIN_II, made, A=_get(ed, tab.row_var, made), B=tab.stat_count)
    child = _call(ed, FN_CHILD_AT, made, self=box, Index=out(row))
    seek = _call(ed, FN_SCROLL_TO, made, self=box, WidgetToFind=out(child), AnimateScroll="false")
    for e in in_execs:
        _connect(e, _pin(seek, "execute"))
    return then(seek)


def author_tune_panel(ed, in_execs, tab=GUN_TAB):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    panel = part(ed, WBP_PAUSE_MENU, tab.panel)
    # MenuOpen too: a tab left open under a shut panel is not on screen, and
    # its rows keep the geometry they last had.
    up = _call(ed, FN_AND, made, A=_get(ed, MV.MenuOpen, made), B=_get(ed, tab.open_var, made))
    shown, shut = _branch(ed, out(up), in_execs, made)
    closed = set_shown(ed, panel, False, [shut])
    flow = set_shown(ed, panel, True, [shown])

    box = part(ed, WBP_PAUSE_MENU, tab.rows_box)
    # The mouse: the row under the cursor takes the caret, a click on it is
    # one step up (Right), and a click on the hint line saves (Enter) -- or,
    # in a tab with a save row, a click on that row. A scrolling list's rows
    # count only inside its window.
    hovered = author_row_cursor(ed, box, tab.row_count, [flow],
                                row_var=tab.row_var, click=(tab.nudge_var, 1),
                                within=box if tab.visible_rows else None)
    if tab.save_widget:
        save = part(ed, WBP_PAUSE_MENU, tab.save_widget)
        hovered = author_button_row(ed, save, tab.row_var, tab.save_row,
                                    (tab.save_var, "true"), hovered)
    else:
        hovered = author_widget_click(
            ed, part(ed, WBP_PAUSE_MENU, tab.hint_widget),
            (tab.save_var, "true"), hovered)
    back = part(ed, WBP_PAUSE_MENU, tab.back_widget)
    hovered = author_back_row(ed, back, tab.row_var, tab.back_row, tab.open_var, hovered)
    if tab.visible_rows:
        # Before the caret is lit and followed: a dragged list brings it along.
        hovered = author_scroll_drag(ed, tab, box, hovered)
    name = _item(ed, tab.names_var, _get(ed, tab.pick_var, made), made)
    flow, failed = row_value(ed, box, 0, name, hovered)
    flow = _author_stats(ed, tab, box, [flow, failed], made)
    flow = mark_rows(ed, box, tab.row_count, _get(ed, tab.row_var, made), [flow])
    flow = _author_under_caret(ed, tab, back, FN_GE_II, tab.back_row, [flow], made)
    if tab.save_widget:
        flow = _author_under_caret(ed, tab, save, FN_EQ_II, tab.save_row, [flow], made)
    if tab.visible_rows:
        flow = _author_follow(ed, tab, box, [flow], made)
    saved = part(ed, WBP_PAUSE_MENU, tab.saved_text)
    tails = show_if(ed, saved, _get(ed, tab.saved_var, made), [flow])
    return [closed, *tails]
