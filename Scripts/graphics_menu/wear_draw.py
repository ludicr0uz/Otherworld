"""DrawHUD: the worn panel, from wear_tick's variables and the player's Worn.

    the menu shut   the panel, always (bottom right, over the bag): row i's
                    value is the DisplayName of the weapon component's
                    Worn[i], or "-" where nothing is worn (Worn is read only
                    behind IsValidIndex, then IsValid); with the I panel
                    open (WearOpen) the caret on WearSel, else on no row
    the menu open   collapsed

Only reads; wear_tick.py decides. The one thing it writes is the mouse's
(cursor.py), with the I panel open only, because only DrawHUD knows where a
row is: the row under the cursor -> WearSel, and a click on it raises
WearTakeOffRequested, which Tick serves exactly as it serves Enter; a click
on the WearClose line lowers WearOpen, as I does; and the inventory's slots
(inv_drag.py).
"""

import unreal

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin
from combat.nodes import (
    FN_ARR_GET, FN_ARR_VALID, FN_GET_COMP, FN_GET_PLAYER_PAWN, FN_IS_VALID, FN_NOT,
    FN_SELECT_II, MACRO_FOR_LOOP,
)
from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.wear_tuning import WORN_VAR
from graphics_menu.cursor import author_row_cursor, author_widget_click
from graphics_menu.ui_graph import mark_rows, member, part, row_at, set_shown, set_text
from graphics_menu.umg_consts import ROW_VALUE, WBP_HUD, WBP_MENU_ROW
from graphics_menu.wear_consts import (
    WEAR_CLOSE, WEAR_NONE_TEXT, WEAR_OPEN_VAR, WEAR_PANEL, WEAR_ROWS, WEAR_ROWS_BOX,
    WEAR_SEL_VAR, WEAR_TAKE_VAR,
)
from graphics_menu.inv_drag import author_inv_drag

NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"


def _get(ed, var, x, y, owner=None, self_out=None):
    n = _at(ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var), x, y)
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    return _pin(n, var, is_input=False)


def _call(ed, fn, x, y, **inputs):
    n = _at(_node(ed, fn), x, y)
    for name, pin in inputs.items():
        if isinstance(pin, int):
            _pin(n, name).set_pin_value(str(pin))
        else:
            _connect(pin, _loose_pin(n, name))
    return n


def _out(n):
    return _pin(n, "ReturnValue", is_input=False)


def _branch(ed, cond, execs, x, y):
    br = _at(ed.add_branch_node(), x, y)
    _connect(cond, _pin(br, "Condition"))
    for e in execs:
        _connect(e, _pin(br, "execute"))
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _author_rows(ed, worn, box, in_execs, x0, y0):
    """Row i's value := Worn[i].DisplayName, or WEAR_NONE_TEXT. Returns
    Completed."""
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0, y0)
    _pin(loop, "FirstIndex").set_pin_value("0")
    _pin(loop, "LastIndex").set_pin_value(str(WEAR_ROWS - 1))
    for e in in_execs:
        _connect(e, _pin(loop, "execute"))
    i = _pin(loop, "Index", is_input=False)
    row, then, _failed = row_at(ed, box, i, [_pin(loop, "LoopBody", is_input=False)],
                                x0 + 300, y0)
    value = member(ed, row, WBP_MENU_ROW, ROW_VALUE, x0 + 600, y0 + 300)
    there, past = _branch(ed, _out(_call(ed, FN_ARR_VALID, x0 + 600, y0 + 500,
                                         TargetArray=worn, IndexToTest=i)),
                          [then], x0 + 860, y0)
    item = _loose_pin(_call(ed, FN_ARR_GET, x0 + 860, y0 + 500, TargetArray=worn, Index=i),
                      "Item", is_input=False)
    worn_one, bare = _branch(ed, _out(_call(ed, FN_IS_VALID, x0 + 1120, y0 + 500,
                                            Object=item)), [there], x0 + 1120, y0)
    set_text(ed, value, _get(ed, "DisplayName", x0 + 1380, y0 + 300, ITEM_CLASS_PATH, item),
             [worn_one], x0 + 1640, y0)
    set_text(ed, value, WEAR_NONE_TEXT, [bare, past], x0 + 1640, y0 + 400)
    return _pin(loop, "Completed", is_input=False)


def author_wear_panel(ed, x0, y0, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    panel = part(ed, WBP_HUD, WEAR_PANEL, x0, y0 + 1000)
    not_menu = _call(ed, FN_NOT, x0, y0 + 440, A=_get(ed, "MenuOpen", x0 - 240, y0 + 440))
    shown, shut = _branch(ed, _out(not_menu), in_execs, x0 + 480, y0)
    closed = set_shown(ed, panel, False, [shut], x0 + 740, y0 + 700)
    flow = set_shown(ed, panel, True, [shown], x0 + 740, y0)

    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0 + 740, y0 + 440))
    comp = _call(ed, FN_GET_COMP, x0 + 1000, y0 + 440, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 1000, y0)
    _connect(_out(comp), _pin(cast, "Object"))
    _connect(flow, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    worn = _get(ed, WORN_VAR, x0 + 1300, y0 + 300, WEAPON_COMP_CLASS_PATH, wc)

    box = part(ed, WBP_HUD, WEAR_ROWS_BOX, x0 + 1300, y0 + 500)
    flow = _author_rows(ed, worn, box, [BEL.find_then_pin(cast)], x0 + 1560, y0)
    # The mouse only with the panel open: shut, the cursor is hidden and a
    # click is a shot.
    opened, idle = _branch(ed, _get(ed, WEAR_OPEN_VAR, x0 + 3200, y0 + 300), [flow],
                           x0 + 3400, y0)
    # The close button: a click on it lowers WearOpen, as I does.
    flow = author_widget_click(ed, part(ed, WBP_HUD, WEAR_CLOSE, x0 + 3660, y0 - 2100),
                               (WEAR_OPEN_VAR, "false"), [opened], x0 + 4180, y0 - 2600)
    flow = author_row_cursor(ed, box, WEAR_ROWS, flow, x0 + 3660, y0 - 1400,
                             row_var=WEAR_SEL_VAR, click=(WEAR_TAKE_VAR, "true"))
    flow = author_inv_drag(ed, wc, flow, x0 + 3660, y0 + 2000)
    # The caret only with the panel open: WearSel, or a row there is none of.
    caret = _call(ed, FN_SELECT_II, x0 + 5600, y0 + 300,
                  A=_get(ed, WEAR_SEL_VAR, x0 + 5360, y0 + 300), B=-1,
                  bPickA=_get(ed, WEAR_OPEN_VAR, x0 + 5360, y0 + 440))
    done = mark_rows(ed, box, WEAR_ROWS, _out(caret), flow + [idle], x0 + 5900, y0)
    return [closed, done, _pin(cast, "CastFailed", is_input=False)]
