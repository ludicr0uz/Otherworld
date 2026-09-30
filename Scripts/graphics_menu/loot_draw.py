"""DrawHUD: the loot window and its prompt, from loot_tick's variables.

    no LootTarget    prompt and panel collapsed
    shut             "[TAB] search the body" under the reticle
    open             the panel: row i shows LootTarget.LootNames[i] (rows past
                     the end collapsed), the caret on LootSel, BAG FULL while
                     LootBagFull

Only reads; loot_tick.py decides. LootNames is read only behind the IsValid
on LootTarget, so an empty reach is not an Accessed None per frame.
"""

from combat.graph import BEL, _at, _connect, _node, _pin
from combat.nodes import FN_ARR_GET, FN_ARR_LEN, FN_IS_VALID, FN_LESS_II, MACRO_FOR_LOOP
from combat.paths import HEALTH_CLASS_PATH
from graphics_menu.loot_consts import (
    LOOT_BAG_FULL_VAR, LOOT_FULL, LOOT_OPEN_VAR, LOOT_PANEL, LOOT_PROMPT, LOOT_ROWS,
    LOOT_ROWS_BOX, LOOT_SEL_VAR, LOOT_TARGET_VAR,
)
from graphics_menu.ui_graph import (
    mark_rows, member, part, row_at, set_shown, set_text, show_if,
)
from graphics_menu.umg_consts import ROW_VALUE, WBP_HUD, WBP_MENU_ROW
from loot.consts import LOOT_NAMES_VAR


def _get(ed, var, x, y, owner=None, self_out=None):
    n = _at(ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var), x, y)
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    return _pin(n, var, is_input=False)


def _call(ed, fn, x, y, **inputs):
    n = _at(_node(ed, fn), x, y)
    for name, pin in inputs.items():
        _connect(pin, _pin(n, name))
    return _pin(n, "ReturnValue", is_input=False)


def _branch(ed, cond, execs, x, y):
    br = _at(ed.add_branch_node(), x, y)
    _connect(cond, _pin(br, "Condition"))
    for e in execs:
        _connect(e, _pin(br, "execute"))
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _author_rows(ed, names, box, in_execs, x0, y0):
    """Row i := names[i], shown, or collapsed past the end. Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0, y0)
    _pin(loop, "FirstIndex").set_pin_value("0")
    _pin(loop, "LastIndex").set_pin_value(str(LOOT_ROWS - 1))
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    row, then, _failed = row_at(ed, box, i, [_pin(loop, "LoopBody", is_input=False)],
                                x0 + 300, y0)
    size = _call(ed, FN_ARR_LEN, x0 + 560, y0 + 440, TargetArray=names)
    within = _call(ed, FN_LESS_II, x0 + 800, y0 + 440, A=i, B=size)
    carried, past = _branch(ed, within, [then], x0 + 860, y0)
    name = _at(_node(ed, FN_ARR_GET), x0 + 860, y0 + 600)
    _connect(names, _pin(name, "TargetArray"))
    _connect(i, _pin(name, "Index"))
    value = member(ed, row, WBP_MENU_ROW, ROW_VALUE, x0 + 1100, y0 + 300)
    flow = set_text(ed, value, _pin(name, "Item", is_input=False), [carried],
                    x0 + 1360, y0)
    set_shown(ed, row, True, [flow], x0 + 1620, y0)
    set_shown(ed, row, False, [past], x0 + 1360, y0 + 400)
    return _pin(loop, "Completed", is_input=False)


def author_loot_window(ed, x0, y0, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    prompt = part(ed, WBP_HUD, LOOT_PROMPT, x0, y0 + 800)
    panel = part(ed, WBP_HUD, LOOT_PANEL, x0, y0 + 1000)
    target = _get(ed, LOOT_TARGET_VAR, x0, y0 + 300)
    near, none = _branch(ed, _call(ed, FN_IS_VALID, x0 + 240, y0 + 300, Object=target),
                         in_execs, x0 + 480, y0)
    flow = set_shown(ed, prompt, False, [none], x0 + 740, y0 + 1400)
    gone = set_shown(ed, panel, False, [flow], x0 + 1000, y0 + 1400)

    shown, shut = _branch(ed, _get(ed, LOOT_OPEN_VAR, x0 + 480, y0 + 440), [near],
                          x0 + 740, y0)
    flow = set_shown(ed, prompt, True, [shut], x0 + 1000, y0 + 700)
    closed = set_shown(ed, panel, False, [flow], x0 + 1260, y0 + 700)

    flow = set_shown(ed, prompt, False, [shown], x0 + 1000, y0)
    flow = set_shown(ed, panel, True, [flow], x0 + 1260, y0)
    names = _get(ed, LOOT_NAMES_VAR, x0 + 1260, y0 + 300, HEALTH_CLASS_PATH,
                 _get(ed, LOOT_TARGET_VAR, x0 + 1020, y0 + 300))
    box = part(ed, WBP_HUD, LOOT_ROWS_BOX, x0 + 1260, y0 + 500)
    flow = _author_rows(ed, names, box, [flow], x0 + 1520, y0)
    flow = mark_rows(ed, box, LOOT_ROWS, _get(ed, LOOT_SEL_VAR, x0 + 3200, y0 + 300),
                     [flow], x0 + 3400, y0)
    full = part(ed, WBP_HUD, LOOT_FULL, x0 + 4600, y0 + 300)
    tails = show_if(ed, full, _get(ed, LOOT_BAG_FULL_VAR, x0 + 4600, y0 + 500), [flow],
                    x0 + 4900, y0)
    return [gone, closed, *tails]
