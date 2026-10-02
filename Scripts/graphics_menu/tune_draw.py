"""DrawHUD: a tuning tab's panel on WBP_PauseMenu (any TuneTab, tune_tab.py),
from the tab's variables. For the guns:

    NOT (MenuOpen AND TuneOpen)   TunePanel collapsed
    else           shown: row 0's value is TuneWeapons[TuneWeapon], row i's
                   is TuneValues[TuneWeapon * STAT_COUNT + i - 1] (up to
                   the tab's fraction_digits decimals, no grouping), the
                   caret on TuneRow -- on BACK when it is past the list, or
                   on the save row of a tab that has one --
                   and "saved to ..." while TuneSaved. A scrolling tab's
                   list is scrolled to the caret's row

Reads, with one exception: BACK. Its Enter and its click lower TuneOpen here
(cursor.author_back_row says why it is not Tick's); everything else
tune_tick.py and its siblings decide. The M panel's own rows are hidden while
a tab is up (menu_screens.author_pause_menu).
"""

from combat.graph import BEL, _at, _connect, _pin, _set
from combat.nodes import FN_ADD_II, FN_AND, FN_ARR_GET, FN_MIN_II, FN_SUB_II
from graphics_menu.cursor import (
    FN_GE_II, author_back_row, author_button_row, author_row_cursor, author_widget_click)
from graphics_menu.dev_guns import _branch, _call, _get, _out
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu.ui_graph import (
    FN_CHILD_AT, FN_EQ_II, FN_SELECT_FLOAT, FN_SET_OPACITY, MACRO_FOR_LOOP, mark_rows, member,
    part, row_value, set_shown, show_if)
from graphics_menu.umg_consts import ROW_CARET, WBP_MENU_ROW, WBP_PAUSE_MENU

FN_MUL_II = "/Script/Engine.KismetMathLibrary.Multiply_IntInt"
FN_TO_TEXT = "/Script/Engine.KismetTextLibrary.Conv_DoubleToText"
FN_SCROLL_TO = "/Script/UMG.ScrollBox.ScrollWidgetIntoView"


def _item(ed, array_var, index, x, y, made):
    n = _call(ed, FN_ARR_GET, x, y, made, TargetArray=_get(ed, array_var, x - 240, y, made))
    _connect(index, _pin(n, "Index"))
    return _pin(n, "Item", is_input=False)


def _author_stats(ed, tab, box, in_execs, x0, y0, made):
    """Rows 1..stat_count := the shown subject's cells. Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    made.append(loop)
    _at(loop, x0, y0)
    _set(loop, "FirstIndex", 1)
    _set(loop, "LastIndex", tab.stat_count)
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    base = _call(ed, FN_MUL_II, x0 + 300, y0 + 500, made,
                 A=_get(ed, tab.pick_var, x0 + 60, y0 + 500, made), B=tab.stat_count)
    s = _call(ed, FN_SUB_II, x0 + 300, y0 + 640, made, A=i, B=1)
    idx = _call(ed, FN_ADD_II, x0 + 540, y0 + 500, made, A=_out(base), B=_out(s))
    words = _call(ed, FN_TO_TEXT, x0 + 1020, y0 + 500, made,
                  Value=_item(ed, tab.values_var, _out(idx), x0 + 780, y0 + 500, made),
                  bUseGrouping="false", MaximumFractionalDigits=tab.fraction_digits)
    row_value(ed, box, i, ("text", _out(words)),
              [_pin(loop, "LoopBody", is_input=False)], x0 + 1300, y0)
    return _pin(loop, "Completed", is_input=False)


def _author_under_caret(ed, tab, widget, test, row, in_execs, x0, y0, made):
    """The caret of a row under the list (BACK, the save row), lit while the
    tab's caret ``test`` ``row``: at or past it for BACK, the last stop, and
    on it for the save row. Returns then."""
    on_it = _call(ed, test, x0, y0 + 300, made,
                  A=_get(ed, tab.row_var, x0 - 240, y0 + 300, made), B=row)
    lit = _call(ed, FN_SELECT_FLOAT, x0 + 260, y0 + 300, made, A=1.0, B=0.0,
                bPickA=_out(on_it))
    fade = _call(ed, FN_SET_OPACITY, x0 + 560, y0, made,
                 self=member(ed, widget, WBP_MENU_ROW, ROW_CARET, x0 + 260, y0 + 500),
                 InOpacity=_out(lit))
    for e in in_execs:
        _connect(e, _pin(fade, "execute"))
    return BEL.find_then_pin(fade)


def _author_follow(ed, tab, box, in_execs, x0, y0, made):
    """A scrolling tab: the caret's row brought into the list's window. On
    BACK the list stays where it is (the last row is already in view).
    Returns then."""
    row = _call(ed, FN_MIN_II, x0, y0 + 300, made,
                A=_get(ed, tab.row_var, x0 - 240, y0 + 300, made), B=tab.stat_count)
    child = _call(ed, FN_CHILD_AT, x0 + 260, y0 + 300, made, self=box, Index=_out(row))
    seek = _call(ed, FN_SCROLL_TO, x0 + 560, y0, made, self=box,
                 WidgetToFind=_out(child), AnimateScroll="false")
    for e in in_execs:
        _connect(e, _pin(seek, "execute"))
    return BEL.find_then_pin(seek)


def author_tune_panel(ed, x0, y0, in_execs, tab=GUN_TAB):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    panel = part(ed, WBP_PAUSE_MENU, tab.panel, x0, y0 + 800)
    # MenuOpen too: a tab left open under a shut panel is not on screen, and
    # its rows keep the geometry they last had.
    up = _call(ed, FN_AND, x0, y0 + 300, made,
               A=_get(ed, "MenuOpen", x0 - 240, y0 + 300, made),
               B=_get(ed, tab.open_var, x0 - 240, y0 + 440, made))
    shown, shut = _branch(ed, _out(up), in_execs, x0 + 240, y0, made)
    closed = set_shown(ed, panel, False, [shut], x0 + 500, y0 + 600)
    flow = set_shown(ed, panel, True, [shown], x0 + 500, y0)

    box = part(ed, WBP_PAUSE_MENU, tab.rows_box, x0 + 500, y0 + 400)
    # The mouse: the row under the cursor takes the caret, a click on it is
    # one step up (Right), and a click on the hint line saves (Enter) -- or,
    # in a tab with a save row, a click on that row. A scrolling list's rows
    # count only inside its window.
    hovered = author_row_cursor(ed, box, tab.row_count, [flow], x0 + 500, y0 - 1400,
                                row_var=tab.row_var, click=(tab.nudge_var, 1),
                                within=box if tab.visible_rows else None)
    if tab.save_widget:
        save = part(ed, WBP_PAUSE_MENU, tab.save_widget, x0 + 500, y0 - 2000)
        hovered = author_button_row(ed, save, tab.row_var, tab.save_row,
                                    (tab.save_var, "true"), hovered, x0 + 500, y0 - 2800)
    else:
        hovered = author_widget_click(
            ed, part(ed, WBP_PAUSE_MENU, tab.hint_widget, x0 + 500, y0 - 2000),
            (tab.save_var, "true"), hovered, x0 + 500, y0 - 2400)
    back = part(ed, WBP_PAUSE_MENU, tab.back_widget, x0 + 500, y0 - 3000)
    hovered = author_back_row(ed, back, tab.row_var, tab.back_row, tab.open_var, hovered,
                              x0 + 500, y0 - 4400)
    name = _item(ed, tab.names_var, _get(ed, tab.pick_var, x0 + 760, y0 + 440, made),
                 x0 + 1000, y0 + 300, made)
    flow, failed = row_value(ed, box, 0, name, hovered, x0 + 1000, y0)
    flow = _author_stats(ed, tab, box, [flow, failed], x0 + 2200, y0, made)
    flow = mark_rows(ed, box, tab.row_count, _get(ed, tab.row_var, x0 + 3800, y0 + 300, made),
                     [flow], x0 + 4000, y0)
    flow = _author_under_caret(ed, tab, back, FN_GE_II, tab.back_row, [flow],
                               x0 + 4000, y0 + 1400, made)
    if tab.save_widget:
        flow = _author_under_caret(ed, tab, save, FN_EQ_II, tab.save_row, [flow],
                                   x0 + 4000, y0 + 3400, made)
    if tab.visible_rows:
        flow = _author_follow(ed, tab, box, [flow], x0 + 4000, y0 + 2400, made)
    saved = part(ed, WBP_PAUSE_MENU, tab.saved_text, x0 + 5200, y0 + 300)
    tails = show_if(ed, saved, _get(ed, tab.saved_var, x0 + 5200, y0 + 500, made), [flow],
                    x0 + 5500, y0)
    return [closed, *tails]
