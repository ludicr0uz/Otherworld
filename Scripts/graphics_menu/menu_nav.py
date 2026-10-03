"""Keyboard navigation shared by the menu's pages: Up/Down move the caret, an
accept key takes the row. The menu's own rows and its settings page both use
it (the rows with Enter alone, polled in menu_screens.py).

Also what a key poll gains from the mouse (cursor_consts.py): a click raised
as CursorAccept, the wheel as Left/Right (or_wheel); and how Tick learns
that a row of the M panel was taken (pause_row_taken).
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
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


def _emit_row_nav(ed, pc_out, last_row, in_exec, row_var="MenuRow"):
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
    for key, step, limit, bound in ((NAV_UP, FN_SUB_II, FN_MAX_II, 0),
                                    (NAV_DOWN, FN_ADD_II, FN_MIN_II, last_row)):
        was = keep(_node(ed, FN_WAS_PRESSED))
        _connect(pc_out, _pin(was, "self"))
        _set(was, "Key", key)
        br = keep(ed.add_branch_node())
        _connect(out(was), _pin(br, "Condition"))
        for e in flow:
            _connect(e, _pin(br, "execute"))

        row = keep(ed.add_get_member_variable_node(row_var))
        moved = keep(_node(ed, step))
        _connect(out(row, row_var), _pin(moved, "A"))
        _set(moved, "B", 1)
        held = keep(_node(ed, limit))
        _connect(out(moved), _pin(held, "A"))
        _set(held, "B", bound)
        put = keep(ed.add_set_member_variable_node(row_var))
        _connect(out(held), _pin(put, row_var))
        _connect(then(br), _pin(put, "execute"))
        flow = (then(put), else_(br))
    return flow, made


def _emit_accept(ed, pc_out, in_exec, made):
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
    for key in START_KEYS:
        was = keep(_node(ed, FN_WAS_PRESSED))
        _connect(pc_out, _pin(was, "self"))
        _set(was, "Key", key)
        got = out(was)
        if any_key is None:
            any_key = got
        else:
            either = keep(_node(ed, FN_OR))
            _connect(any_key, _pin(either, "A"))
            _connect(got, _pin(either, "B"))
            any_key = out(either)
    click = keep(ed.add_get_member_variable_node(CURSOR_ACCEPT_VAR))
    either = keep(_node(ed, FN_OR))
    _connect(any_key, _pin(either, "A"))
    _connect(out(click, CURSOR_ACCEPT_VAR), _pin(either, "B"))
    go = keep(ed.add_branch_node())
    _connect(out(either), _pin(go, "Condition"))
    for e in in_exec:
        _connect(e, _pin(go, "execute"))
    served = keep(ed.add_set_member_variable_node(CURSOR_ACCEPT_VAR))
    _set(served, CURSOR_ACCEPT_VAR, "false")
    _connect(then(go), _pin(served, "execute"))
    return served


def or_wheel(ed, pc_out, pressed, wheel_key, made):
    """``pressed`` (a bool pin) OR the wheel turned ``wheel_key``'s way."""
    wheel = _node(ed, FN_WAS_PRESSED)
    _connect(pc_out, _pin(wheel, "self"))
    _set(wheel, "Key", wheel_key)
    either = _node(ed, FN_OR)
    _connect(pressed, _pin(either, "A"))
    _connect(out(wheel), _pin(either, "B"))
    made += [wheel, either]
    return out(either)


def pause_row_taken(ed, action, made):
    """The M panel's row for ``action`` was taken (Enter on it, or a click):
    a bool pin. PauseClick is the row's index for the one Tick after DrawHUD
    raised it, and only an open panel's rows can be taken, so this needs no
    MenuOpen test. The rows have no keys of their own."""
    clicked = ed.add_get_member_variable_node(PAUSE_CLICK_VAR)
    this_row = _node(ed, FN_EQ_II)
    _connect(out(clicked, PAUSE_CLICK_VAR), _pin(this_row, "A"))
    _set(this_row, "B", PAUSE_ROW_ACTIONS.index(action))
    made += [clicked, this_row]
    return out(this_row)
