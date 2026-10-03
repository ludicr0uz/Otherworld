"""The settings page's input half: rebinding capture, the arrow-key nudges,
BACK, and the save written after every change.
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, else_, out, then
from graphics_menu.cursor import author_row_cursor
from graphics_menu.cursor_consts import CURSOR_ACCEPT_VAR, WHEEL_LESS, WHEEL_MORE
from graphics_menu.difficulty import emit_difficulty_nudge
from graphics_menu.menu_nav import (
    NAV_LEFT, NAV_RIGHT, _emit_accept, _emit_row_nav, or_wheel)
from graphics_menu.ui_graph import part
from graphics_menu.umg_consts import SETTINGS_ROWS_BOX, WBP_MAIN_MENU
from graphics_menu.settings_rows import (
    BACK_ROW, FIRST_BIND_ROW, PAGE_TITLE, SETTINGS_CLASS_PATH, SETTINGS_SLOT,
    SETTINGS_USER_INDEX, SLIDERS)
from uebp.nodes.actor import FN_GET_OWNING_PC, FN_WAS_PRESSED
from uebp.nodes.array import FN_ARR_SET
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_CLAMP, FN_EQ_II, FN_GE_II, FN_LESS_II, FN_OR, FN_SELECT_FF,
    FN_SUB_II)
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_WRITE_SAVE
from graphics_menu import hud_vars as MV
from combat import settings_vars as SV


def _emit_save(ed, settings_out, in_exec):
    """Write BP_Settings back to its slot. Called after every single change.

    On the change and not on leaving the page: a game quit from the settings
    screen still has to remember what was set, and there is no other moment
    this HUD is guaranteed to see.
    """
    n = _node(ed, FN_WRITE_SAVE)
    _connect(settings_out, _pin(n, "SaveGameObject"))
    _set(n, "SlotName", SETTINGS_SLOT)
    _set(n, "UserIndex", SETTINGS_USER_INDEX)
    _connect(in_exec, _pin(n, "execute"))
    return then(n), n


def _author_capture(ed, settings_out, in_execs, made):
    """The input half of the settings page: capture first, then everything else.

    THE ORDER OF THESE TWO ARMS IS LOAD-BEARING. The capture poll is authored
    and branched on BEFORE the row is activated, because Enter is what arms a
    capture -- and Enter is still "just pressed" for the rest of that frame. A
    capture poll that ran after the activation would see it and instantly bind
    the accept key to whatever row the caret was on, which is a settings screen
    that eats itself the first time it is used. Branching on Capturing puts
    them in different frames as well as in different arms, and both of those
    have to be true.
    """
    def keep(n):
        made.append(n)
        return n

    pc = keep(_node(ed, FN_GET_OWNING_PC))
    pc_out = out(pc)

    armed = keep(ed.add_get_member_variable_node(MV.Capturing))
    listening = keep(ed.add_branch_node())
    _connect(out(armed, MV.Capturing), _pin(listening, "Condition"))
    for e in in_execs:
        _connect(e, _pin(listening, "execute"))

    # --- armed: the next key in KEY_POOL that goes down becomes the bind ------
    pool = keep(ed.add_get_member_variable_node(MV.KeyPool))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(loop)
    _connect(out(pool, MV.KeyPool), _loose_pin(loop, "Array"))
    _connect(then(listening), _loose_pin(loop, "Exec"))
    candidate = _loose_pin(loop, "ArrayElement", is_input=False)

    hit = keep(_node(ed, FN_WAS_PRESSED))
    _connect(pc_out, _pin(hit, "self"))
    _connect(candidate, _pin(hit, "Key"))
    took = keep(ed.add_branch_node())
    _connect(out(hit), _pin(took, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(took, "execute"))

    # Binds[MenuRow - FIRST_BIND_ROW]: the sliders sit above the binds, so the
    # subtraction is the whole of that mapping.
    row = keep(ed.add_get_member_variable_node(MV.MenuRow))
    slot = keep(_node(ed, FN_SUB_II))
    _connect(out(row, MV.MenuRow), _pin(slot, "A"))
    _set(slot, "B", FIRST_BIND_ROW)
    binds = keep(ed.add_get_member_variable_node(SV.Binds, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(binds, "self"))
    write = keep(_node(ed, FN_ARR_SET))
    _connect(out(binds, SV.Binds), _loose_pin(write, "TargetArray"))
    _connect(out(slot), _pin(write, "Index"))
    _connect(candidate, _loose_pin(write, "Item"))
    _connect(then(took), _pin(write, "execute"))
    done = keep(ed.add_set_member_variable_node(MV.Capturing))
    _set(done, MV.Capturing, "false")
    _connect(then(write), _pin(done, "execute"))
    _, writer = _emit_save(ed, settings_out, then(done))
    made.append(writer)

    # --- not armed: move the caret, nudge the sensitivity, take the row -------
    # The mouse first: the row under the cursor takes the caret, and a click
    # on it is Enter. Not while a capture is armed -- that click is the bind.
    hovered = author_row_cursor(
        ed, part(ed, WBP_MAIN_MENU, SETTINGS_ROWS_BOX), BACK_ROW + 1,
        [else_(listening)], row_var="MenuRow",
        click=(CURSOR_ACCEPT_VAR, "true"))
    moved, nav = _emit_row_nav(ed, pc_out, BACK_ROW, hovered)
    made += nav

    left = keep(_node(ed, FN_WAS_PRESSED))
    _connect(pc_out, _pin(left, "self"))
    _set(left, "Key", NAV_LEFT)
    right = keep(_node(ed, FN_WAS_PRESSED))
    _connect(pc_out, _pin(right, "self"))
    _set(right, "Key", NAV_RIGHT)
    # The wheel is Left/Right too, and a click on a row with no bind (a
    # slider, the difficulty) is Right: one step up, or the next difficulty.
    left_out = or_wheel(ed, pc_out, out(left), WHEEL_LESS, made)
    right_out = or_wheel(ed, pc_out, out(right), WHEEL_MORE, made)
    valued = keep(_node(ed, FN_LESS_II))
    _connect(out(keep(ed.add_get_member_variable_node(MV.MenuRow)), MV.MenuRow), _pin(valued, "A"))
    _set(valued, "B", FIRST_BIND_ROW)
    stepped = keep(_node(ed, FN_AND))
    _connect(out(keep(ed.add_get_member_variable_node(CURSOR_ACCEPT_VAR)), CURSOR_ACCEPT_VAR),
             _pin(stepped, "A"))
    _connect(out(valued), _pin(stepped, "B"))
    more = keep(_node(ed, FN_OR))
    _connect(right_out, _pin(more, "A"))
    _connect(out(stepped), _pin(more, "B"))
    right_out = out(more)
    either = keep(_node(ed, FN_OR))
    _connect(left_out, _pin(either, "A"))
    _connect(right_out, _pin(either, "B"))
    either_out = out(either)

    # One nudge block per slider, in series: each one's "not me" arm and its
    # saved tail both carry on into the next, and the last pair into accept.
    flow = moved
    for i, slider in enumerate(SLIDERS):
        flow = _emit_nudge(ed, slider, i, settings_out, either_out, right_out, flow, made)
    stored, passed = emit_difficulty_nudge(ed, settings_out, either_out, right_out, flow, made)
    saved, writer = _emit_save(ed, settings_out, stored)
    made.append(writer)
    flow = (saved, passed)

    go = _emit_accept(ed, pc_out, flow, made)

    # BACK, or arm a capture. Enter means nothing on a slider row -- the arrows
    # are its control, and arming a capture there would bind a key to a row
    # that has none -- so only rows from FIRST_BIND_ROW down arm one.
    leaving = keep(_node(ed, FN_EQ_II))
    _connect(out(keep(ed.add_get_member_variable_node(MV.MenuRow)), MV.MenuRow), _pin(leaving, "A"))
    _set(leaving, "B", BACK_ROW)
    back = keep(ed.add_branch_node())
    _connect(out(leaving), _pin(back, "Condition"))
    _connect(then(go), _pin(back, "execute"))

    to_title = keep(ed.add_set_member_variable_node(MV.MenuPage))
    _set(to_title, MV.MenuPage, PAGE_TITLE)
    _connect(then(back), _pin(to_title, "execute"))
    home = keep(ed.add_set_member_variable_node(MV.MenuRow))
    _set(home, MV.MenuRow, 0)
    _connect(then(to_title), _pin(home, "execute"))

    bindable = keep(_node(ed, FN_GE_II))
    _connect(out(keep(ed.add_get_member_variable_node(MV.MenuRow)), MV.MenuRow), _pin(bindable, "A"))
    _set(bindable, "B", FIRST_BIND_ROW)
    arming = keep(ed.add_branch_node())
    _connect(out(bindable), _pin(arming, "Condition"))
    _connect(else_(back), _pin(arming, "execute"))
    arm = keep(ed.add_set_member_variable_node(MV.Capturing))
    _set(arm, MV.Capturing, "true")
    _connect(then(arming), _pin(arm, "execute"))


def _emit_nudge(ed, slider, row, settings_out, either_out, right_out, in_execs, made):
    """Left/Right on ``row``: step ``slider.var`` on BP_Settings and save it.

    One write with a signed step rather than two arms with the same two writes
    in them: the pair would drift, and the clamp would end up on only one of
    them. Returns the exec pins to carry on from -- the saved tail and the
    "not this row" arm.
    """
    def keep(n):
        made.append(n)
        return n

    here = keep(_node(ed, FN_EQ_II))
    _connect(out(keep(ed.add_get_member_variable_node(MV.MenuRow)), MV.MenuRow), _pin(here, "A"))
    _set(here, "B", row)
    adjusting = keep(_node(ed, FN_AND))
    _connect(either_out, _pin(adjusting, "A"))
    _connect(out(here), _pin(adjusting, "B"))
    nudging = keep(ed.add_branch_node())
    _connect(out(adjusting), _pin(nudging, "Condition"))
    for e in in_execs:
        _connect(e, _pin(nudging, "execute"))

    delta = keep(_node(ed, FN_SELECT_FF))
    _set(delta, "A", slider.step)
    _set(delta, "B", -slider.step)
    _connect(right_out, _loose_pin(delta, "bPickA"))
    now = keep(ed.add_get_member_variable_node(slider.var, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(now, "self"))
    total = keep(_node(ed, FN_ADD_FF))
    _connect(out(now, slider.var), _pin(total, "A"))
    _connect(out(delta), _pin(total, "B"))
    held = keep(_node(ed, FN_CLAMP))
    _connect(out(total), _loose_pin(held, "Value"))
    _set(held, "Min", slider.lo)
    _set(held, "Max", slider.hi)
    store = keep(ed.add_set_member_variable_node(slider.var, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(store, "self"))
    _connect(out(held), _pin(store, slider.var))
    _connect(then(nudging), _pin(store, "execute"))
    saved, writer = _emit_save(ed, settings_out, then(store))
    made.append(writer)
    return (saved, else_(nudging))
