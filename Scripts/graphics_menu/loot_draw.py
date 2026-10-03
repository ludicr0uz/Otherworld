"""DrawHUD: the loot window and its prompt, from loot_tick's variables.

    no LootTarget    prompt and panel collapsed
    shut             "[TAB] search the body" under the reticle
    open             the panel: row i shows the icon LootTarget.LootIcons[i]
                     tinted LootTints[i], as the inventory draws the item
                     (rows past the end collapsed), the caret on LootSel,
                     NOTHING on a body that carries nothing, BAG FULL while
                     LootBagFull

Only reads; loot_tick.py decides. The body's arrays are read only behind the
IsValid on LootTarget, so an empty reach is not an Accessed None per frame.

The one thing it writes is the mouse's (cursor.py), because only DrawHUD
knows where a row is: the row under the cursor -> LootSel, and a click on it
raises LootTakeRequested, which Tick serves exactly as it serves Enter; a
click on the LootClose line lowers LootOpen, as Tab does.
"""

from combat.graph import BEL, _connect, _node, _pin, _set
from combat.nodes import FN_ARR_GET, FN_ARR_LEN, FN_IS_VALID, FN_LESS_II, MACRO_FOR_LOOP
from combat.paths import HEALTH_CLASS_PATH
from graphics_menu.cursor import author_row_cursor, author_widget_click
from graphics_menu.loot_consts import (
    LOOT_BAG_FULL_VAR, LOOT_CLOSE, LOOT_EMPTY, LOOT_FULL, LOOT_OPEN_VAR, LOOT_PANEL, LOOT_PROMPT,
    LOOT_ROWS, LOOT_ROWS_BOX, LOOT_SEL_VAR, LOOT_TAKE_VAR, LOOT_TARGET_VAR,
)
from graphics_menu.ui_graph import mark_rows, member, part, row_at, set_shown, show_if
from graphics_menu.umg_consts import ROW_ICON, WBP_HUD, WBP_MENU_ROW
from loot.consts import LOOT_ICONS_VAR, LOOT_TINTS_VAR

FN_SET_BRUSH = "/Script/UMG.Image.SetBrushFromTexture"
FN_SET_TINT = "/Script/UMG.Image.SetColorAndOpacity"


def _get(ed, var, owner=None, self_out=None):
    n = (ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var))
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    return _pin(n, var, is_input=False)


def _call(ed, fn, **inputs):
    n = _node(ed, fn)
    for name, pin in inputs.items():
        _connect(pin, _pin(n, name))
    return _pin(n, "ReturnValue", is_input=False)


def _branch(ed, cond, execs):
    br = ed.add_branch_node()
    _connect(cond, _pin(br, "Condition"))
    for e in execs:
        _connect(e, _pin(br, "execute"))
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _item(ed, array, index):
    n = _node(ed, FN_ARR_GET)
    _connect(array, _pin(n, "TargetArray"))
    _connect(index, _pin(n, "Index"))
    return _pin(n, "Item", is_input=False)


def _author_rows(ed, icons, tints, box, in_execs):
    """Row i := icons[i] tinted tints[i], shown, or collapsed past the end.
    Returns Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    loop
    _pin(loop, "FirstIndex").set_pin_value("0")
    _pin(loop, "LastIndex").set_pin_value(str(LOOT_ROWS - 1))
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    row, then, _failed = row_at(ed, box, i, [_pin(loop, "LoopBody", is_input=False)])
    size = _call(ed, FN_ARR_LEN, TargetArray=icons)
    within = _call(ed, FN_LESS_II, A=i, B=size)
    carried, past = _branch(ed, within, [then])
    icon = member(ed, row, WBP_MENU_ROW, ROW_ICON)
    brush = _node(ed, FN_SET_BRUSH)
    _connect(icon, _pin(brush, "self"))
    _connect(_item(ed, icons, i), _pin(brush, "Texture"))
    _connect(carried, _pin(brush, "execute"))
    tint = _node(ed, FN_SET_TINT)
    _connect(icon, _pin(tint, "self"))
    _connect(_item(ed, tints, i), _pin(tint, "InColorAndOpacity"))
    _connect(BEL.find_then_pin(brush), _pin(tint, "execute"))
    flow = set_shown(ed, icon, True, [BEL.find_then_pin(tint)])
    set_shown(ed, row, True, [flow])
    set_shown(ed, row, False, [past])
    return _pin(loop, "Completed", is_input=False)


def author_loot_window(ed, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    prompt = part(ed, WBP_HUD, LOOT_PROMPT)
    panel = part(ed, WBP_HUD, LOOT_PANEL)
    target = _get(ed, LOOT_TARGET_VAR)
    near, none = _branch(ed, _call(ed, FN_IS_VALID, Object=target), in_execs)
    flow = set_shown(ed, prompt, False, [none])
    gone = set_shown(ed, panel, False, [flow])

    shown, shut = _branch(ed, _get(ed, LOOT_OPEN_VAR), [near])
    flow = set_shown(ed, prompt, True, [shut])
    closed = set_shown(ed, panel, False, [flow])

    flow = set_shown(ed, prompt, False, [shown])
    flow = set_shown(ed, panel, True, [flow])
    body = _get(ed, LOOT_TARGET_VAR)
    icons = _get(ed, LOOT_ICONS_VAR, HEALTH_CLASS_PATH, body)
    tints = _get(ed, LOOT_TINTS_VAR, HEALTH_CLASS_PATH, body)
    box = part(ed, WBP_HUD, LOOT_ROWS_BOX)
    # The close button: a click on it lowers LootOpen, and Tick stands the
    # player up off that edge exactly as it does after Tab.
    shut = author_widget_click(ed, part(ed, WBP_HUD, LOOT_CLOSE), (LOOT_OPEN_VAR, "false"), [flow])
    hovered = author_row_cursor(
        ed, box, LOOT_ROWS, shut, row_var=LOOT_SEL_VAR,
        click=(LOOT_TAKE_VAR, "true"),
        limit=_call(ed, FN_ARR_LEN, TargetArray=icons))
    flow = _author_rows(ed, icons, tints, box, hovered)
    flow = mark_rows(ed, box, LOOT_ROWS, _get(ed, LOOT_SEL_VAR), [flow])
    bare = _node(ed, FN_LESS_II)
    _connect(_call(ed, FN_ARR_LEN, TargetArray=icons), _pin(bare, "A"))
    _set(bare, "B", 1)
    said = show_if(ed, part(ed, WBP_HUD, LOOT_EMPTY),
                   _pin(bare, "ReturnValue", is_input=False), [flow])
    full = part(ed, WBP_HUD, LOOT_FULL)
    tails = show_if(ed, full, _get(ed, LOOT_BAG_FULL_VAR), list(said))
    return [gone, closed, *tails]
