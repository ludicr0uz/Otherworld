"""DrawHUD: the GUN TUNING panel on WBP_PauseMenu, from tune_tick's variables.

    NOT TuneOpen   TunePanel collapsed
    TuneOpen       shown: row 0's value is TuneWeapons[TuneWeapon], row i's
                   is TuneValues[TuneWeapon * STAT_COUNT + i - 1] (up to 4
                   decimals, no grouping), the caret on TuneRow, and "saved
                   to ..." while TuneSaved

Only reads; tune_tick.py decides. WBP_PauseMenu itself is shown only while
MenuOpen (menu_screens.author_pause_menu), so this needs no MenuOpen test.
"""

from combat.graph import _at, _connect, _pin, _set
from combat.nodes import FN_ADD_II, FN_ARR_GET, FN_SUB_II
from graphics_menu.dev_guns import _branch, _call, _get, _out
from graphics_menu.tune_consts import (
    STAT_COUNT, TUNE_OPEN_VAR, TUNE_PANEL, TUNE_ROW_COUNT, TUNE_ROW_VAR,
    TUNE_ROWS_BOX, TUNE_SAVED_TEXT, TUNE_SAVED_VAR, TUNE_VALUES_VAR,
    TUNE_WEAPON_VAR, TUNE_WEAPONS_VAR,
)
from graphics_menu.ui_graph import MACRO_FOR_LOOP, mark_rows, part, row_value, set_shown, show_if
from graphics_menu.umg_consts import WBP_PAUSE_MENU

FN_MUL_II = "/Script/Engine.KismetMathLibrary.Multiply_IntInt"
FN_TO_TEXT = "/Script/Engine.KismetTextLibrary.Conv_DoubleToText"


def _item(ed, array_var, index, x, y, made):
    n = _call(ed, FN_ARR_GET, x, y, made, TargetArray=_get(ed, array_var, x - 240, y, made))
    _connect(index, _pin(n, "Index"))
    return _pin(n, "Item", is_input=False)


def _author_stats(ed, box, in_execs, x0, y0, made):
    """Rows 1..STAT_COUNT := the held gun's cells. Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    made.append(loop)
    _at(loop, x0, y0)
    _set(loop, "FirstIndex", 1)
    _set(loop, "LastIndex", STAT_COUNT)
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    base = _call(ed, FN_MUL_II, x0 + 300, y0 + 500, made,
                 A=_get(ed, TUNE_WEAPON_VAR, x0 + 60, y0 + 500, made), B=STAT_COUNT)
    s = _call(ed, FN_SUB_II, x0 + 300, y0 + 640, made, A=i, B=1)
    idx = _call(ed, FN_ADD_II, x0 + 540, y0 + 500, made, A=_out(base), B=_out(s))
    words = _call(ed, FN_TO_TEXT, x0 + 1020, y0 + 500, made,
                  Value=_item(ed, TUNE_VALUES_VAR, _out(idx), x0 + 780, y0 + 500, made),
                  bUseGrouping="false", MaximumFractionalDigits=4)
    row_value(ed, box, i, ("text", _out(words)),
              [_pin(loop, "LoopBody", is_input=False)], x0 + 1300, y0)
    return _pin(loop, "Completed", is_input=False)


def author_tune_panel(ed, x0, y0, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    panel = part(ed, WBP_PAUSE_MENU, TUNE_PANEL, x0, y0 + 800)
    shown, shut = _branch(ed, _get(ed, TUNE_OPEN_VAR, x0, y0 + 300, made), in_execs,
                          x0 + 240, y0, made)
    closed = set_shown(ed, panel, False, [shut], x0 + 500, y0 + 600)
    flow = set_shown(ed, panel, True, [shown], x0 + 500, y0)

    box = part(ed, WBP_PAUSE_MENU, TUNE_ROWS_BOX, x0 + 500, y0 + 400)
    gun = _item(ed, TUNE_WEAPONS_VAR, _get(ed, TUNE_WEAPON_VAR, x0 + 760, y0 + 440, made),
                x0 + 1000, y0 + 300, made)
    flow, failed = row_value(ed, box, 0, gun, [flow], x0 + 1000, y0)
    flow = _author_stats(ed, box, [flow, failed], x0 + 2200, y0, made)
    flow = mark_rows(ed, box, TUNE_ROW_COUNT, _get(ed, TUNE_ROW_VAR, x0 + 3800, y0 + 300, made),
                     [flow], x0 + 4000, y0)
    saved = part(ed, WBP_PAUSE_MENU, TUNE_SAVED_TEXT, x0 + 5200, y0 + 300)
    tails = show_if(ed, saved, _get(ed, TUNE_SAVED_VAR, x0 + 5200, y0 + 500, made), [flow],
                    x0 + 5500, y0)
    return [closed, *tails]
