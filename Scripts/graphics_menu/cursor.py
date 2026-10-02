"""The mouse cursor in the menus: the DrawHUD fragments that show it and say
what it is over. cursor_consts.py has the rules in one table.

  author_cursor_read   top of DrawHUD: where the cursor is, whether it moved;
                       last frame's M-panel click lowered
  author_cursor_mode   a screen's wish (shown or not) onto the controller:
                       bShowMouseCursor and the input mode, on a change only
  author_hold_fire     while it shows in a running game: the weapon
                       component's TriggerSpent up, so a click fires nothing
  author_row_cursor    a stack of rows: the one under the cursor -> CursorRow;
                       moved or clicked -> the caret; clicked -> a flag
  author_button_row    a tab's SAVE DEFAULT row: the caret onto it; a click
                       raises its flag
  author_back_row      a tab's BACK row: the caret onto it; a click, or Enter
                       with the caret there, shuts the tab
  author_widget_click  one widget (a hint line): clicked -> a flag

The HUD stays the controller. No widget is hit-testable (umg_consts.SHOWN):
a row is "under the cursor" by its cached geometry, and a click is the left
button polled off the controller like every key. DrawHUD, not Tick, because
the title and death screens are a paused world; the M panel's and the loot
window's keys are Tick's, so a click there only raises what Tick serves
(PauseClick, the tabs' nudge and save flags, LootTakeRequested).

A -nullrhi run never lays a widget out, so no row is ever under anything
there: probes/probe_menu_cursor.py raises the flags a click would.
"""

import unreal

from combat.graph import BEL, _at, _connect, _declare, _loose_pin, _palette, _pin, _set
from combat.nodes import FN_AND, FN_GET_COMP, FN_GET_PLAYER_PAWN, FN_WAS_PRESSED
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.cursor_consts import (
    BACK_KEY, CLICK_KEY, CURSOR_BOOLS, CURSOR_INTS, CURSOR_MOVED_VAR, CURSOR_POS_VAR,
    CURSOR_ROW_VAR, CURSOR_SHOWN_VAR, CURSOR_WANTED_VAR, NO_ROW, PAUSE_CLICK_VAR,
    TRIGGER_SPENT_VAR,
)
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.loot_find import put
from graphics_menu.ui_graph import FN_CHILD_AT, MACRO_FOR_LOOP

FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_MOUSE_POS = "/Script/UMG.WidgetLayoutLibrary.GetMousePositionOnPlatform"
FN_GEOMETRY = "/Script/UMG.Widget.GetCachedGeometry"
FN_UNDER = "/Script/UMG.SlateBlueprintLibrary.IsUnderLocation"
FN_MODE_GAME_UI = "/Script/UMG.WidgetBlueprintLibrary.SetInputMode_GameAndUIEx"
FN_MODE_GAME = "/Script/UMG.WidgetBlueprintLibrary.SetInputMode_GameOnly"
FN_VEC2_NE = "/Script/Engine.KismetMathLibrary.NotEqualExactly_Vector2DVector2D"
FN_XOR = "/Script/Engine.KismetMathLibrary.BooleanXOR"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_LESS_II = "/Script/Engine.KismetMathLibrary.Less_IntInt"
PC_CLASS_PATH = "/Script/Engine.PlayerController"
SHOW_CURSOR_PROP = "bShowMouseCursor"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"

# What a click writes: (HUD variable, a literal) or (HUD variable, ROW) for
# the row that was clicked.
ROW = object()


def declare_cursor_vars(ed):
    """The HUD's cursor variables. Defaults: cursor_defaults()."""
    for name in CURSOR_BOOLS:
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    for name in CURSOR_INTS:
        _declare(ed, name, BEL.get_basic_type_by_name("int"))
    _declare(ed, CURSOR_POS_VAR, BEL.get_struct_type(unreal.Vector2D.static_struct()))


def cursor_defaults():
    """Hidden, unasked for, over nothing, nothing clicked."""
    return {**{b: False for b in CURSOR_BOOLS}, **{i: NO_ROW for i in CURSOR_INTS}}


def _pc(ed, x, y, made):
    return _out(_call(ed, FN_GET_OWNING_PC, x, y, made))


def _clicked(ed, x, y, made):
    return _out(_call(ed, FN_WAS_PRESSED, x, y, made, self=_pc(ed, x - 240, y, made),
                      Key=CLICK_KEY))


def _under(ed, widget, x, y, made):
    """``widget``'s painted rectangle holds the cursor."""
    geo = _call(ed, FN_GEOMETRY, x, y, made, self=widget)
    return _out(_call(ed, FN_UNDER, x + 260, y, made, Geometry=_out(geo),
                      AbsoluteCoordinate=_get(ed, CURSOR_POS_VAR, x, y + 140, made)))


def _write(ed, click, in_execs, x, y, made):
    var, value = click
    if value is ROW:
        return put(ed, var, _get(ed, CURSOR_ROW_VAR, x - 240, y + 200, made), in_execs,
                   x, y, made)
    return _setter(ed, var, value, in_execs, x, y, made)


def author_cursor_read(ed, in_execs, x0, y0):
    """Top of DrawHUD (see the module docstring). Returns the exec tail.

    CursorMoved is set before CursorPos: a Set pulls its inputs when it runs,
    so the comparison still sees last frame's position."""
    made = []
    pos = _call(ed, FN_MOUSE_POS, x0, y0, made)
    for e in in_execs:
        _connect(e, _pin(pos, "execute"))
    moved = _call(ed, FN_VEC2_NE, x0 + 300, y0 + 300, made, A=_out(pos),
                  B=_get(ed, CURSOR_POS_VAR, x0 + 60, y0 + 440, made))
    flow = put(ed, CURSOR_MOVED_VAR, _out(moved), [BEL.find_then_pin(pos)], x0 + 560, y0,
               made)
    flow = put(ed, CURSOR_POS_VAR, _out(pos), [flow], x0 + 820, y0, made)
    flow = _setter(ed, PAUSE_CLICK_VAR, NO_ROW, [flow], x0 + 1080, y0, made)
    ed.add_comment_to_nodes(
        "The mouse cursor: where it is (desktop space, as cached geometry is) "
        "and whether it moved since last frame. Last frame's M-panel click is "
        "lowered; Tick has served it.", made)
    return flow


def author_cursor_mode(ed, want, in_execs, x0, y0):
    """The cursor shown (``want`` True, or a bool pin) or hidden, applied only
    when it differs from what the controller has. Returns the exec tails.

    Shown is Game-and-UI: the cursor is free and a click is still a key the
    controller is polled for. Hidden is Game-only, which takes the mouse back
    for the camera -- without it the view stays dead until the next click."""
    made = []
    if want is True:
        flow = _setter(ed, CURSOR_WANTED_VAR, "true", in_execs, x0, y0, made)
    else:
        flow = put(ed, CURSOR_WANTED_VAR, want, in_execs, x0, y0, made)
    changed = _call(ed, FN_XOR, x0 + 260, y0 + 300, made,
                    A=_get(ed, CURSOR_WANTED_VAR, x0, y0 + 300, made),
                    B=_get(ed, CURSOR_SHOWN_VAR, x0, y0 + 440, made))
    switch, same = _branch(ed, _out(changed), [flow], x0 + 520, y0, made)
    flow = put(ed, CURSOR_SHOWN_VAR, _get(ed, CURSOR_WANTED_VAR, x0 + 520, y0 + 300, made),
               [switch], x0 + 780, y0, made)
    pc = _pc(ed, x0 + 780, y0 + 500, made)
    show = _at(ed.add_set_member_variable_node(SHOW_CURSOR_PROP, PC_CLASS_PATH),
               x0 + 1040, y0)
    made.append(show)
    _connect(pc, _pin(show, "self"))
    _connect(_get(ed, CURSOR_WANTED_VAR, x0 + 780, y0 + 300, made),
             _pin(show, SHOW_CURSOR_PROP))
    _connect(flow, _pin(show, "execute"))
    on, off = _branch(ed, _get(ed, CURSOR_WANTED_VAR, x0 + 1040, y0 + 300, made),
                      [BEL.find_then_pin(show)], x0 + 1300, y0, made)
    free = _call(ed, FN_MODE_GAME_UI, x0 + 1560, y0, made, PlayerController=pc,
                 bHideCursorDuringCapture="false")
    _connect(on, _pin(free, "execute"))
    taken = _call(ed, FN_MODE_GAME, x0 + 1560, y0 + 400, made, PlayerController=pc)
    _connect(off, _pin(taken, "execute"))
    ed.add_comment_to_nodes(
        "The mouse cursor, shown while a menu is up. Only on a change: "
        "bShowMouseCursor, and Game-and-UI (cursor free) or Game-only (the "
        "mouse back to the camera).", made)
    return [BEL.find_then_pin(free), BEL.find_then_pin(taken), same]


def author_hold_fire(ed, in_execs, x0, y0):
    """While the cursor shows over a running game (the M panel, the loot
    window): the weapon component's TriggerSpent, every frame. Its Tick keeps
    a spent press spent while the fire key is down, so a click on a row
    neither fires, slashes nor punches. Returns the exec tails."""
    made = []
    held, free = _branch(ed, _get(ed, CURSOR_WANTED_VAR, x0, y0 + 300, made), in_execs,
                         x0 + 240, y0, made)
    pawn = _call(ed, FN_GET_PLAYER_PAWN, x0 + 240, y0 + 440, made, PlayerIndex=0)
    comp = _call(ed, FN_GET_COMP, x0 + 500, y0 + 440, made, self=_out(pawn))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 760, y0)
    made.append(cast)
    _connect(_out(comp), _pin(cast, "Object"))
    _connect(held, _pin(cast, "execute"))
    spent = _setter(ed, TRIGGER_SPENT_VAR, "true", [BEL.find_then_pin(cast)], x0 + 1040,
                    y0, made, WEAPON_COMP_CLASS_PATH,
                    _loose_pin(cast, "AsBPWeaponComponent", is_input=False))
    ed.add_comment_to_nodes(
        "A click on a menu row is not a shot: the cursor showing keeps the "
        "weapon component's fire press spent.", made)
    return [spent, free, _pin(cast, "CastFailed", is_input=False)]


def author_row_cursor(ed, box, count, in_execs, x0, y0, row_var=None, click=None,
                      limit=None, within=None):
    """Which of ``box``'s first ``count`` rows the cursor is over -> CursorRow.

    ``row_var``: the menu's caret, moved there when the mouse moved or
    clicked. ``click``: what a left click on a row writes (see ROW).
    ``limit``: an int pin; rows from it on are not on screen (the loot window
    collapses them, and a collapsed row keeps its last geometry).
    ``within``: a widget the cursor must be over as well -- a scrolling
    list's window, whose rows keep their geometry when scrolled out of it.
    Returns the exec tails."""
    made = []
    flow = _setter(ed, CURSOR_ROW_VAR, NO_ROW, in_execs, x0, y0, made)
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    made.append(_at(loop, x0 + 260, y0))
    _set(loop, "FirstIndex", 0)
    _set(loop, "LastIndex", count - 1)
    _connect(flow, _pin(loop, "execute"))
    index = _loose_pin(loop, "Index", is_input=False)
    child = _call(ed, FN_CHILD_AT, x0 + 560, y0 + 300, made, self=box)
    _connect(index, _pin(child, "Index"))
    over = _under(ed, _out(child), x0 + 820, y0 + 300, made)
    if limit is not None:
        shown = _call(ed, FN_LESS_II, x0 + 1080, y0 + 500, made, A=index, B=limit)
        over = _out(_call(ed, FN_AND, x0 + 1340, y0 + 300, made, A=over, B=_out(shown)))
    if within is not None:
        over = _out(_call(ed, FN_AND, x0 + 1340, y0 + 700, made, A=over,
                          B=_under(ed, within, x0 + 820, y0 + 700, made)))
    hit, _miss = _branch(ed, over, [_loose_pin(loop, "LoopBody", is_input=False)],
                         x0 + 1600, y0, made)
    put(ed, CURSOR_ROW_VAR, index, [hit], x0 + 1860, y0, made)

    x = x0 + 2200
    on_row = _call(ed, FN_GE_II, x, y0 + 300, made,
                   A=_get(ed, CURSOR_ROW_VAR, x - 240, y0 + 300, made), B=0)
    flow, off = _branch(ed, _out(on_row), [_loose_pin(loop, "Completed", is_input=False)],
                        x + 260, y0, made)
    tails = [off]
    flow = [flow]
    if row_var is not None:
        stirred = _call(ed, FN_OR, x + 520, y0 + 300, made,
                        A=_get(ed, CURSOR_MOVED_VAR, x + 280, y0 + 300, made),
                        B=_clicked(ed, x + 280, y0 + 440, made))
        move, rest = _branch(ed, _out(stirred), flow, x + 780, y0, made)
        flow = [put(ed, row_var, _get(ed, CURSOR_ROW_VAR, x + 800, y0 + 300, made),
                    [move], x + 1040, y0, made), rest]
    if click is not None:
        took, idle = _branch(ed, _clicked(ed, x + 1300, y0 + 440, made), flow, x + 1560,
                             y0, made)
        flow = [_write(ed, click, [took], x + 1820, y0, made), idle]
    return flow + tails


def author_back_row(ed, back, row_var, back_row, open_var, in_execs, x0, y0):
    """A menu's BACK row, a WBP_MenuRow outside its list. The cursor over it
    (moved or clicked) puts the caret there: ``row_var`` := ``back_row``. A
    click on it, or Enter with the caret on it, lowers ``open_var``.
    Returns the exec tails.

    DrawHUD's, though the rest of a tab's keys are Tick's: the M panel's own
    Enter is polled in DrawHUD, before this in the same frame and only while
    no tab is open, so the Enter that shuts a tab cannot also take the row
    the panel's caret was left on."""
    made = []
    over = _under(ed, back, x0, y0 + 500, made)
    stirred = _call(ed, FN_OR, x0 + 560, y0 + 760, made,
                    A=_get(ed, CURSOR_MOVED_VAR, x0 + 300, y0 + 760, made),
                    B=_clicked(ed, x0 + 300, y0 + 900, made))
    aimed = _call(ed, FN_AND, x0 + 820, y0 + 500, made, A=over, B=_out(stirred))
    move, rest = _branch(ed, _out(aimed), in_execs, x0 + 1080, y0, made)
    flow = [_setter(ed, row_var, back_row, [move], x0 + 1340, y0, made), rest]

    x = x0 + 1700
    on_it = _call(ed, FN_AND, x, y0 + 300, made, A=_clicked(ed, x - 260, y0 + 300, made),
                  B=over)
    caret = _call(ed, FN_GE_II, x, y0 + 500, made,
                  A=_get(ed, row_var, x - 240, y0 + 500, made), B=back_row)
    entered = _call(ed, FN_AND, x + 260, y0 + 500, made, A=_out(caret),
                    B=_out(_call(ed, FN_WAS_PRESSED, x, y0 + 700, made,
                                 self=_pc(ed, x - 240, y0 + 700, made), Key=BACK_KEY)))
    leave = _call(ed, FN_OR, x + 520, y0 + 300, made, A=_out(on_it), B=_out(entered))
    took, idle = _branch(ed, _out(leave), flow, x + 780, y0, made)
    return [_setter(ed, open_var, "false", [took], x + 1040, y0, made), idle]


def author_button_row(ed, button, row_var, row, click, in_execs, x0, y0):
    """A button that is a WBP_MenuRow outside its menu's list (a tab's SAVE
    DEFAULT). The cursor over it (moved or clicked) puts the caret there:
    ``row_var`` := ``row``. A click on it writes ``click`` (a variable and a
    literal); Enter with the caret on it is the menu's own keys'.
    Returns the exec tails."""
    made = []
    over = _under(ed, button, x0, y0 + 500, made)
    stirred = _call(ed, FN_OR, x0 + 560, y0 + 760, made,
                    A=_get(ed, CURSOR_MOVED_VAR, x0 + 300, y0 + 760, made),
                    B=_clicked(ed, x0 + 300, y0 + 900, made))
    aimed = _call(ed, FN_AND, x0 + 820, y0 + 500, made, A=over, B=_out(stirred))
    move, rest = _branch(ed, _out(aimed), in_execs, x0 + 1080, y0, made)
    flow = [_setter(ed, row_var, row, [move], x0 + 1340, y0, made), rest]
    on_it = _call(ed, FN_AND, x0 + 1700, y0 + 300, made,
                  A=_clicked(ed, x0 + 1440, y0 + 300, made), B=over)
    took, idle = _branch(ed, _out(on_it), flow, x0 + 1960, y0, made)
    return [_write(ed, click, [took], x0 + 2220, y0, made), idle]


def author_widget_click(ed, widget, click, in_execs, x0, y0):
    """A left click with the cursor over ``widget`` writes ``click`` (a
    variable and a literal). Returns the exec tails."""
    made = []
    on_it = _call(ed, FN_AND, x0 + 560, y0 + 300, made,
                  A=_clicked(ed, x0 + 300, y0 + 300, made),
                  B=_under(ed, widget, x0, y0 + 500, made))
    took, idle = _branch(ed, _out(on_it), in_execs, x0 + 820, y0, made)
    return [_write(ed, click, [took], x0 + 1080, y0, made), idle]
