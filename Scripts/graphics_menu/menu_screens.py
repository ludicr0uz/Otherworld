"""DrawHUD: which screen is up, and the three menus' live parts.

  author_main_menu   GameStarted false: WBP_MainMenu over a hidden HUD, the
                     title or settings page by MenuPage, Up/Down/Enter on it

Each also says whether the mouse cursor shows, and what a click on it does
(cursor.py): always on the title and death screens; alive, with the M panel
or the loot window open.
  author_death_menu  PlayerDead: WBP_DeathMenu instead of the HUD, the score,
                     and [R] restarting the level
  author_alive       neither: the HUD's Body shown, the death menu hidden
  author_pause_menu  MenuOpen: WBP_PauseMenu, the caret on Quality, debug ON/OFF

Everything here is polled and written in DrawHUD rather than on Tick: the
title and death screens are a paused world, Tick does not run in one, and
DrawHUD is called by the renderer every frame regardless. APlayerController
sets bTickEvenWhenPaused, so WasInputKeyJustPressed still answers.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from graphics_menu.cursor import (
    ROW, author_cursor_mode, author_hold_fire, author_row_cursor, author_widget_click)
from graphics_menu.cursor_consts import (
    CURSOR_ACCEPT_VAR, CURSOR_ROW_VAR, PAUSE_CLICK_VAR)
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.menu_nav import _emit_accept, _emit_row_nav
from graphics_menu.settings_page import _author_settings_page
from graphics_menu.settings_rows import PAGE_SETTINGS, PAGE_TITLE
from graphics_menu.ui_graph import (
    mark_rows, member, part, row_at, screen, set_shown, set_text,
)
from graphics_menu.umg_consts import (
    DEATH_HINT_LINE, DEATH_SCORE, DEATH_SCORE_PREFIX, DEBUG_OFF, DEBUG_ON,
    GAME_STARTED_VAR, HUD_BODY,
    MENU_ROWS, PAUSE_DEBUG_ROW, PAUSE_ROW_LABELS, PAUSE_ROWS, RESTART_KEY, ROW_VALUE,
    SETTINGS_PANEL,
    TITLE_PANEL, TITLE_ROWS, WBP_DEATH_MENU, WBP_HUD, WBP_MAIN_MENU, WBP_MENU_ROW,
    WBP_PAUSE_MENU,
)

GAME_MODE_CLASS_PATH = ("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
                        ".BP_ThirdPersonGameMode_C")
KILL_COUNT_VAR = "NpcKillCount"

FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_OPEN_LEVEL = "/Script/Engine.GameplayStatics.OpenLevel"
FN_LEVEL_NAME = "/Script/Engine.GameplayStatics.GetCurrentLevelName"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"


def _hide_all_but_menu(ed, execs, x0, y0):
    """The title screens stand alone: no HUD, death menu or panel under them."""
    flow = set_shown(ed, screen(ed, WBP_MAIN_MENU, x0, y0 + 240), True, execs, x0 + 260, y0)
    flow = set_shown(ed, part(ed, WBP_HUD, HUD_BODY, x0 + 260, y0 + 240), False, [flow],
                     x0 + 760, y0)
    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU, x0 + 760, y0 + 240), False, [flow],
                     x0 + 1020, y0)
    return set_shown(ed, screen(ed, WBP_PAUSE_MENU, x0 + 1020, y0 + 240), False, [flow],
                     x0 + 1280, y0)


def _show_page(ed, title, execs, x0, y0):
    """The title panel or the settings panel, never both."""
    first = set_shown(ed, part(ed, WBP_MAIN_MENU, TITLE_PANEL, x0, y0 + 240), title,
                      execs, x0 + 500, y0)
    return set_shown(ed, part(ed, WBP_MAIN_MENU, SETTINGS_PANEL, x0 + 500, y0 + 240),
                     not title, [first], x0 + 1000, y0)


def author_main_menu(ed, x0, y0, in_execs):
    """The menu the game opens on, and the one thing that leaves it.

    Returns ``(exec_pin_when_already_started,)`` -- the path the rest of the
    HUD hangs off. Two rows, NEW GAME and SETTINGS, chosen with the keyboard
    or by a click on the row under the cursor.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    started = keep(_at(ed.add_get_member_variable_node(GAME_STARTED_VAR), x0, y0 + 240))
    playing = keep(_at(ed.add_branch_node(), x0 + 260, y0))
    _connect(_pin(started, GAME_STARTED_VAR, is_input=False), _pin(playing, "Condition"))
    for e in in_execs:
        _connect(e, _pin(playing, "execute"))
    flow = _hide_all_but_menu(ed, author_cursor_mode(
        ed, True, [BEL.find_else_pin(playing)], x0 + 520, y0 - 1400), x0 + 520, y0)

    # Which page the menu is showing: the title page's two rows, or the
    # settings page's -- a different panel, rows and keys.
    page = keep(_at(ed.add_get_member_variable_node("MenuPage"), x0 + 1800, y0 + 400))
    on_title = keep(_at(_node(ed, FN_EQ_II), x0 + 2040, y0 + 400))
    _connect(_pin(page, "MenuPage", is_input=False), _pin(on_title, "A"))
    _set(on_title, "B", PAGE_TITLE)
    which = keep(_at(ed.add_branch_node(), x0 + 2300, y0))
    _connect(_pin(on_title, "ReturnValue", is_input=False), _pin(which, "Condition"))
    _connect(flow, _pin(which, "execute"))

    _author_settings_page(ed, x0, y0 + 9000, _show_page(
        ed, False, [BEL.find_else_pin(which)], x0 + 2560, y0 + 1200))

    flow = _show_page(ed, True, [BEL.find_then_pin(which)], x0 + 2560, y0)
    # The row under the cursor takes the caret, and a click on it is Enter.
    hovered = author_row_cursor(
        ed, part(ed, WBP_MAIN_MENU, TITLE_ROWS, x0 + 3800, y0 - 1000), len(MENU_ROWS),
        [flow], x0 + 4060, y0 - 1400, row_var="MenuRow",
        click=(CURSOR_ACCEPT_VAR, "true"))
    row = keep(_at(ed.add_get_member_variable_node("MenuRow"), x0 + 3800, y0 + 600))
    flow = mark_rows(ed, part(ed, WBP_MAIN_MENU, TITLE_ROWS, x0 + 3800, y0 + 400),
                     len(MENU_ROWS), _pin(row, "MenuRow", is_input=False), hovered,
                     x0 + 4060, y0)

    # --- choosing a row -------------------------------------------------------
    pc = keep(_at(_node(ed, FN_GET_OWNING_PC), x0 + 5960, y0 + 400))
    pc_out = _pin(pc, "ReturnValue", is_input=False)
    moved, nav_nodes = _emit_row_nav(ed, pc_out, len(MENU_ROWS) - 1, flow,
                                     x0 + 6200, y0 + 1200)
    made += nav_nodes
    go = _emit_accept(ed, pc_out, x0 + 7700, y0 + 400, moved, made)

    # NEW GAME or SETTINGS, off the same MenuRow the caret is lit from.
    new_game = keep(_at(_node(ed, FN_EQ_II), x0 + 7960, y0 + 400))
    _connect(_pin(keep(_at(ed.add_get_member_variable_node("MenuRow"),
                           x0 + 7700, y0 + 400)), "MenuRow", is_input=False),
             _pin(new_game, "A"))
    _set(new_game, "B", 0)
    chosen = keep(_at(ed.add_branch_node(), x0 + 8220, y0))
    _connect(_pin(new_game, "ReturnValue", is_input=False), _pin(chosen, "Condition"))
    _connect(BEL.find_then_pin(go), _pin(chosen, "execute"))

    mark = keep(_at(ed.add_set_member_variable_node(GAME_STARTED_VAR), x0 + 8480, y0))
    _set(mark, GAME_STARTED_VAR, "true")
    _connect(BEL.find_then_pin(chosen), _pin(mark, "execute"))
    # Unpause LAST. Setting GameStarted first means the very next frame shows
    # the HUD rather than the menu, so the world never runs behind a title.
    resume = keep(_at(_node(ed, FN_SET_PAUSED), x0 + 8740, y0))
    _set(resume, "bPaused", "false")
    _connect(BEL.find_then_pin(mark), _pin(resume, "execute"))

    # ...or the other row: open the settings page, caret at its top.
    to_settings = keep(_at(ed.add_set_member_variable_node("MenuPage"), x0 + 8480, y0 + 600))
    _set(to_settings, "MenuPage", PAGE_SETTINGS)
    _connect(BEL.find_else_pin(chosen), _pin(to_settings, "execute"))
    reset_row = keep(_at(ed.add_set_member_variable_node("MenuRow"), x0 + 8740, y0 + 600))
    _set(reset_row, "MenuRow", 0)
    _connect(BEL.find_then_pin(to_settings), _pin(reset_row, "execute"))

    ed.add_comment_to_nodes(
        f"The main menu: WBP_MainMenu over a hidden HUD while {GAME_STARTED_VAR} "
        f"is false, which BeginPlay leaves it with while it pauses the world. "
        f"The caret is lit on MenuRow's row; Enter, Space or a click on it "
        f"takes it.",
        made)
    return (set_shown(ed, screen(ed, WBP_MAIN_MENU, x0 + 260, y0 - 400), False,
                      [BEL.find_then_pin(playing)], x0 + 520, y0 - 400),)


def author_death_menu(ed, x0, y0, in_execs, mode_out):
    """What is on screen once the player is dead and the game is paused:
    WBP_DeathMenu instead of the HUD, not over it -- a reticle and an
    inventory over a death screen read as a game still being played.

    Restarting is SetGamePaused(false) *then* OpenLevel: a level opened while
    the world is paused comes up paused, with nothing left able to unpause it.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU, x0, y0 + 240), True,
                     author_cursor_mode(ed, True, in_execs, x0, y0 - 1200),
                     x0 + 260, y0)
    flow = set_shown(ed, part(ed, WBP_HUD, HUD_BODY, x0 + 260, y0 + 240), False,
                     [flow], x0 + 760, y0)
    flow = set_shown(ed, screen(ed, WBP_PAUSE_MENU, x0 + 760, y0 + 240), False,
                     [flow], x0 + 1020, y0)

    # The same counter the corner shows, read again so the final score is the
    # live number rather than a copy taken when the player fell.
    kills = keep(_at(ed.add_get_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH),
                     x0 + 1020, y0 + 500))
    _connect(mode_out, _pin(kills, "self"))
    kills_str = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 1260, y0 + 500))
    _connect(_pin(kills, KILL_COUNT_VAR, is_input=False), _pin(kills_str, "InInt"))
    score_text = keep(_at(_node(ed, FN_CONCAT), x0 + 1500, y0 + 500))
    _set(score_text, "A", DEATH_SCORE_PREFIX)
    _connect(_pin(kills_str, "ReturnValue", is_input=False), _pin(score_text, "B"))
    flow = set_text(ed, part(ed, WBP_DEATH_MENU, DEATH_SCORE, x0 + 1500, y0 + 700),
                    _pin(score_text, "ReturnValue", is_input=False), [flow],
                    x0 + 1760, y0)

    # --- the restart itself --------------------------------------------------
    pc = keep(_at(_node(ed, FN_GET_OWNING_PC), x0 + 3040, y0 + 300))
    pressed = keep(_at(_node(ed, FN_WAS_PRESSED), x0 + 3280, y0 + 300))
    _connect(_pin(pc, "ReturnValue", is_input=False), _pin(pressed, "self"))
    _set(pressed, "Key", RESTART_KEY)
    # ...or a click on the hint line, raised and served like the title's.
    clicked = author_widget_click(
        ed, part(ed, WBP_DEATH_MENU, DEATH_HINT_LINE, x0 + 2000, y0 - 600),
        (CURSOR_ACCEPT_VAR, "true"), [flow], x0 + 2000, y0 - 1000)
    asked = keep(_at(ed.add_get_member_variable_node(CURSOR_ACCEPT_VAR),
                     x0 + 3280, y0 + 460))
    either = keep(_at(_node(ed, FN_OR), x0 + 3540, y0 + 300))
    _connect(_pin(pressed, "ReturnValue", is_input=False), _pin(either, "A"))
    _connect(_pin(asked, CURSOR_ACCEPT_VAR, is_input=False), _pin(either, "B"))
    again = keep(_at(ed.add_branch_node(), x0 + 3540, y0))
    _connect(_pin(either, "ReturnValue", is_input=False), _pin(again, "Condition"))
    for e in clicked:
        _connect(e, _pin(again, "execute"))
    served = keep(_at(ed.add_set_member_variable_node(CURSOR_ACCEPT_VAR),
                      x0 + 3800, y0 - 200))
    _set(served, CURSOR_ACCEPT_VAR, "false")
    _connect(BEL.find_then_pin(again), _pin(served, "execute"))
    unpause = keep(_at(_node(ed, FN_SET_PAUSED), x0 + 3800, y0))
    _set(unpause, "bPaused", "false")
    _connect(BEL.find_then_pin(served), _pin(unpause, "execute"))
    # The current map by name, so the menu restarts whatever level is loaded.
    # bRemovePrefixString strips PIE's UEDPIE_0_.
    where = keep(_at(_node(ed, FN_LEVEL_NAME), x0 + 4060, y0))
    _set(where, "bRemovePrefixString", "true")
    _connect(BEL.find_then_pin(unpause), _pin(where, "execute"))
    reopen = keep(_at(_node(ed, FN_OPEN_LEVEL), x0 + 4320, y0))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(reopen, "LevelName"))
    _connect(BEL.find_then_pin(where), _pin(reopen, "execute"))

    ed.add_comment_to_nodes(
        f"The death menu, instead of the HUD while the GameMode's PlayerDead is "
        f"set and the game is paused. [{RESTART_KEY}] or a click on the hint "
        f"line unpauses and reopens the "
        f"current level, which resets the kill count with it -- the counter "
        f"lives on the GameMode, and OpenLevel builds a new one.",
        made)


def author_alive(ed, x0, y0, in_execs):
    """Playing and alive: the death menu down, the HUD's Body up."""
    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU, x0, y0 + 240), False, in_execs,
                     x0 + 260, y0)
    return (set_shown(ed, part(ed, WBP_HUD, HUD_BODY, x0 + 260, y0 + 240), True,
                      [flow], x0 + 760, y0),)


def author_pause_menu(ed, x0, y0, in_execs):
    """The M panel, while MenuOpen: the caret on the Quality row, and whether
    debug mode is on. Its labels are WBP_PauseMenu's. Returns the exec tails.

    First, for everything a living player has open: the cursor shows with
    the panel or the loot window, and while it does a click is not a shot.
    A click on a panel row is the row's key, served by Tick (PauseClick)."""
    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0, y0 + 200)
    looting = _at(ed.add_get_member_variable_node(LOOT_OPEN_VAR), x0 - 500, y0 - 900)
    wanted = _at(_node(ed, FN_OR), x0 - 260, y0 - 1000)
    _connect(_pin(_at(ed.add_get_member_variable_node("MenuOpen"), x0 - 500, y0 - 1040),
                  "MenuOpen", is_input=False), _pin(wanted, "A"))
    _connect(_pin(looting, LOOT_OPEN_VAR, is_input=False), _pin(wanted, "B"))
    in_execs = author_hold_fire(ed, author_cursor_mode(
        ed, _pin(wanted, "ReturnValue", is_input=False), in_execs, x0, y0 - 1400),
        x0 + 2200, y0 - 1400)
    br = _at(ed.add_branch_node(), x0 + 260, y0)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    closed = set_shown(ed, screen(ed, WBP_PAUSE_MENU, x0 + 260, y0 + 600), False,
                       [BEL.find_else_pin(br)], x0 + 520, y0 + 600)

    flow = set_shown(ed, screen(ed, WBP_PAUSE_MENU, x0 + 260, y0 + 240), True,
                     [BEL.find_then_pin(br)], x0 + 520, y0)
    rows = part(ed, WBP_PAUSE_MENU, PAUSE_ROWS, x0 + 520, y0 + 400)
    hovered = author_row_cursor(ed, rows, len(PAUSE_ROW_LABELS), [flow], x0 + 4400,
                                y0 - 1400, click=(PAUSE_CLICK_VAR, ROW))
    quality = _at(ed.add_get_member_variable_node("Quality"), x0 + 780, y0 + 600)
    under = _at(ed.add_get_member_variable_node(CURSOR_ROW_VAR), x0 + 780, y0 + 740)
    flow = mark_rows(ed, rows, len(PAUSE_ROW_LABELS),
                     _pin(quality, "Quality", is_input=False), hovered, x0 + 1040, y0,
                     also=_pin(under, CURSOR_ROW_VAR, is_input=False))

    # ON or OFF behind one branch: no SelectText, and a bool converted to text
    # reads "true", which is a variable's value and not a setting.
    debug_row, found, missing = row_at(ed, rows, PAUSE_DEBUG_ROW, [flow], x0 + 2400, y0)
    value = member(ed, debug_row, WBP_MENU_ROW, ROW_VALUE, x0 + 2940, y0 + 300)
    dbg = _at(ed.add_get_member_variable_node("DebugOn"), x0 + 2940, y0 + 500)
    dbg_br = _at(ed.add_branch_node(), x0 + 3200, y0)
    _connect(_pin(dbg, "DebugOn", is_input=False), _pin(dbg_br, "Condition"))
    _connect(found, _pin(dbg_br, "execute"))
    on = set_text(ed, value, DEBUG_ON, [BEL.find_then_pin(dbg_br)], x0 + 3460, y0)
    off = set_text(ed, value, DEBUG_OFF, [BEL.find_else_pin(dbg_br)], x0 + 3460, y0 + 300)
    ed.add_comment_to_nodes(
        "The Game Settings panel (M). The caret sits on the Quality row, so it "
        "follows the preset, and on the row under the cursor; debug mode's "
        "row says ON or OFF.",
        [get_open, br, quality, dbg, dbg_br])
    return [closed, on, off, missing]
