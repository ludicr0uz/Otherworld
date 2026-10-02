"""Keyboard navigation shared by the menu's pages: Up/Down move the caret, an
accept key takes the row. The menu's own rows and its settings page both use
it (the rows with Enter alone, polled in menu_screens.py).

Also what a key poll gains from the mouse (cursor_consts.py): a click raised
as CursorAccept, the wheel as Left/Right (or_wheel); and how Tick learns
that a row of the M panel was taken (pause_row_taken).
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from graphics_menu.cursor_consts import CURSOR_ACCEPT_VAR, PAUSE_CLICK_VAR
from graphics_menu.umg_consts import PAUSE_ROW_ACTIONS

FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_MIN_II = "/Script/Engine.KismetMathLibrary.Min"
FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"

# Enter and Space accept. The left mouse button is not a third key here: a
# click accepts only over a row, which cursor.py raises as CursorAccept.
START_KEYS = ("Enter", "SpaceBar")

# Navigation. Deliberately NOT rebindable and deliberately not in KEY_POOL: a
# menu whose own keys can be bound away is a menu that can be locked shut, and
# the only way out would be deleting the save file.
NAV_UP = "Up"
NAV_DOWN = "Down"
NAV_LEFT = "Left"
NAV_RIGHT = "Right"


def _emit_row_nav(ed, pc_out, last_row, in_exec, x0, y0, row_var="MenuRow"):
    """Up and Down move ``row_var`` (the settings page's MenuRow, or the
    menu's PauseRow), clamped at both ends rather than wrapped.

    Two branches in series rather than one Select: MenuRow is read fresh by
    each, so pressing both in a frame nets to no movement instead of to
    whichever arm the Select happened to pick.

    Returns ``(exec_pins, nodes)`` -- a pair of pins, because an exec *input*
    takes any number of links and so neither arm of a Branch needs joining
    before the next block. That is the same flat-chain shape the weapon
    component's Tick uses, and it is why there is no Sequence node anywhere
    in this HUD.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    flow = tuple(in_exec) if isinstance(in_exec, (list, tuple)) else (in_exec,)
    for i, (key, step, limit, bound) in enumerate(
            ((NAV_UP, FN_SUB_II, FN_MAX_II, 0),
             (NAV_DOWN, FN_ADD_II, FN_MIN_II, last_row))):
        py = y0 + i * 420
        was = keep(_at(_node(ed, FN_WAS_PRESSED), x0, py + 260))
        _connect(pc_out, _pin(was, "self"))
        _set(was, "Key", key)
        br = keep(_at(ed.add_branch_node(), x0 + 260, py))
        _connect(_pin(was, "ReturnValue", is_input=False), _pin(br, "Condition"))
        for e in flow:
            _connect(e, _pin(br, "execute"))

        row = keep(_at(ed.add_get_member_variable_node(row_var), x0 + 260, py + 400))
        moved = keep(_at(_node(ed, step), x0 + 520, py + 400))
        _connect(_pin(row, row_var, is_input=False), _pin(moved, "A"))
        _set(moved, "B", 1)
        held = keep(_at(_node(ed, limit), x0 + 780, py + 400))
        _connect(_pin(moved, "ReturnValue", is_input=False), _pin(held, "A"))
        _set(held, "B", bound)
        put = keep(_at(ed.add_set_member_variable_node(row_var), x0 + 1040, py))
        _connect(_pin(held, "ReturnValue", is_input=False), _pin(put, row_var))
        _connect(BEL.find_then_pin(br), _pin(put, "execute"))
        flow = (BEL.find_then_pin(put), BEL.find_else_pin(br))
    return flow, made


def _emit_accept(ed, pc_out, x0, y0, in_exec, made):
    """The exec that runs on the frame an accept key is pressed, or a row is
    clicked. Returns the node whose then pin that is.

    START_KEYS are OR'd rather than chosen between: Enter is the conventional
    one and Space is what a hand is already near, and with a caret on the panel
    both mean "this row". CursorAccept is the click (cursor.py puts the caret
    on the clicked row first); it is lowered here, as it is served.
    """
    def keep(n):
        made.append(n)
        return n

    any_key = None
    for i, key in enumerate(START_KEYS):
        was = keep(_at(_node(ed, FN_WAS_PRESSED), x0, y0 + i * 140))
        _connect(pc_out, _pin(was, "self"))
        _set(was, "Key", key)
        got = _pin(was, "ReturnValue", is_input=False)
        if any_key is None:
            any_key = got
        else:
            either = keep(_at(_node(ed, FN_OR), x0 + 260, y0 + i * 140))
            _connect(any_key, _pin(either, "A"))
            _connect(got, _pin(either, "B"))
            any_key = _pin(either, "ReturnValue", is_input=False)
    click = keep(_at(ed.add_get_member_variable_node(CURSOR_ACCEPT_VAR),
                     x0, y0 + len(START_KEYS) * 140))
    either = keep(_at(_node(ed, FN_OR), x0 + 260, y0 + len(START_KEYS) * 140))
    _connect(any_key, _pin(either, "A"))
    _connect(_pin(click, CURSOR_ACCEPT_VAR, is_input=False), _pin(either, "B"))
    go = keep(_at(ed.add_branch_node(), x0 + 520, y0 - 200))
    _connect(_pin(either, "ReturnValue", is_input=False), _pin(go, "Condition"))
    for e in in_exec:
        _connect(e, _pin(go, "execute"))
    served = keep(_at(ed.add_set_member_variable_node(CURSOR_ACCEPT_VAR),
                      x0 + 520, y0 - 400))
    _set(served, CURSOR_ACCEPT_VAR, "false")
    _connect(BEL.find_then_pin(go), _pin(served, "execute"))
    return served


def or_wheel(ed, pc_out, pressed, wheel_key, x, y, made):
    """``pressed`` (a bool pin) OR the wheel turned ``wheel_key``'s way."""
    wheel = _at(_node(ed, FN_WAS_PRESSED), x, y)
    _connect(pc_out, _pin(wheel, "self"))
    _set(wheel, "Key", wheel_key)
    either = _at(_node(ed, FN_OR), x + 260, y)
    _connect(pressed, _pin(either, "A"))
    _connect(_pin(wheel, "ReturnValue", is_input=False), _pin(either, "B"))
    made += [wheel, either]
    return _pin(either, "ReturnValue", is_input=False)


def pause_row_taken(ed, action, x, y, made):
    """The M panel's row for ``action`` was taken (Enter on it, or a click):
    a bool pin. PauseClick is the row's index for the one Tick after DrawHUD
    raised it, and only an open panel's rows can be taken, so this needs no
    MenuOpen test. The rows have no keys of their own."""
    clicked = _at(ed.add_get_member_variable_node(PAUSE_CLICK_VAR), x, y)
    this_row = _at(_node(ed, FN_EQ_II), x + 240, y)
    _connect(_pin(clicked, PAUSE_CLICK_VAR, is_input=False), _pin(this_row, "A"))
    _set(this_row, "B", PAUSE_ROW_ACTIONS.index(action))
    made += [clicked, this_row]
    return _pin(this_row, "ReturnValue", is_input=False)
