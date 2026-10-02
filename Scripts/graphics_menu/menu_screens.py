"""DrawHUD: which screen is up, and the menus' live parts.

  author_title       GameStarted false: the menu stands alone, open, over a
                     hidden HUD and a paused world
  author_death_menu  PlayerDead: WBP_DeathMenu instead of the HUD, the score,
                     and [R] restarting the level
  author_alive       neither: the HUD's Body shown, the death menu hidden
  author_pause_menu  MenuOpen: the menu (WBP_PauseMenu), the same one on the
                     title and in play. Its rows (Up/Down/Enter, the caret,
                     the first row's words, debug ON/OFF) unless the settings
                     page or a tuning tab is open in their place

Each also says whether the mouse cursor shows, and what a click on it does
(cursor.py): always on the title and death screens; alive, with the menu or
the loot window open.

Everything here is polled and written in DrawHUD rather than on Tick: the
title and death screens are a paused world, and DrawHUD is called by the
renderer every frame regardless. APlayerController sets bTickEvenWhenPaused,
so WasInputKeyJustPressed still answers. What a taken row does is Tick's
(menu_main.py), which the HUD keeps running under the paused title.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from graphics_menu.cursor import (
    ROW, author_cursor_mode, author_hold_fire, author_row_cursor, author_widget_click)
from graphics_menu.cursor_consts import CURSOR_ACCEPT_VAR, PAUSE_CLICK_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.loot_find import put
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.wear_consts import WEAR_OPEN_VAR
from graphics_menu.menu_nav import _emit_row_nav
from graphics_menu.settings_page import _author_settings_page
from graphics_menu.settings_rows import PAGE_TITLE
from graphics_menu.tune_tabs import TABS
from graphics_menu.ui_graph import (
    mark_rows, member, part, row_at, screen, set_shown, set_text,
)
from graphics_menu.umg_consts import (
    DEATH_HINT_LINE, DEATH_SCORE, DEATH_SCORE_PREFIX, DEBUG_OFF, DEBUG_ON,
    GAME_STARTED_VAR, HUD_BODY, IN_GAME_ACTIONS, IN_GAME_ONLY,
    PAUSE_ACCEPT_KEY, PAUSE_DEBUG_ROW, PAUSE_PANEL, PAUSE_ROW_ACTIONS,
    PAUSE_ROW_LABELS, PAUSE_ROW_VAR, PAUSE_ROWS, PAUSE_START_ROW, RESTART_KEY,
    RESUME_ROW_LABEL, ROW_LABEL, ROW_VALUE, SETTINGS_PANEL, START_ROW_LABEL,
    WBP_DEATH_MENU, WBP_HUD, WBP_MAIN_MENU, WBP_MENU_ROW, WBP_PAUSE_MENU,
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


def author_title(ed, x0, y0, in_execs):
    """Before the game starts the menu stands alone: nothing of the HUD or
    the death menu under it, and it is open -- MenuOpen is held up, so the
    title needs no drawing of its own and M has nothing to shut.

    Returns ``(title_tail, started_exec)``: the first goes on to the menu
    (author_pause_menu), the second to the rest of the HUD.
    """
    made = []
    started, title = _branch(ed, _get(ed, GAME_STARTED_VAR, x0, y0 + 240, made),
                             in_execs, x0 + 260, y0, made)
    flow = set_shown(ed, part(ed, WBP_HUD, HUD_BODY, x0 + 260, y0 + 440), False,
                     [title], x0 + 760, y0 + 200)
    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU, x0 + 760, y0 + 440), False, [flow],
                     x0 + 1020, y0 + 200)
    flow = _setter(ed, "MenuOpen", "true", [flow], x0 + 1280, y0 + 200, made)
    ed.add_comment_to_nodes(
        f"The title: while {GAME_STARTED_VAR} is false, which BeginPlay leaves "
        f"it with while it pauses the world, the menu is held open over a "
        f"hidden HUD. It is the same menu M brings up in play; its first row "
        f"starts the game.", made)
    return flow, started


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
    flow = set_shown(ed, screen(ed, WBP_MAIN_MENU, x0 + 760, y0 - 240), False,
                     [flow], x0 + 1020, y0 - 240)

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


def _any_tab_open(ed, x, y, made):
    """A tuning tab is open: a bool pin. At most one is (opening one shuts
    the others), and it stands in the panel's place."""
    flags = [_get(ed, tab.open_var, x, y + 140 * i, made) for i, tab in enumerate(TABS)]
    either = flags[0]
    for i, flag in enumerate(flags[1:]):
        either = _out(_call(ed, FN_OR, x + 260 * (i + 1), y + 140 * i, made,
                            A=either, B=flag))
    return either


def _author_pause_keys(ed, in_execs, x0, y0, made):
    """Up / Down move the panel's caret; Enter takes the row it is on, as a
    click on the row does: PauseClick, which Tick serves. Returns the tails.

    DrawHUD rather than Tick, like the settings page's keys, though the menu
    pauses nothing in play: the row is raised in the same place for the key and the
    mouse, and top-of-frame lowers it once Tick has had its one look."""
    pc_out = _out(_call(ed, FN_GET_OWNING_PC, x0, y0 + 400, made))
    moved, nav_nodes = _emit_row_nav(ed, pc_out, len(PAUSE_ROW_LABELS) - 1, in_execs,
                                     x0 + 240, y0 + 1200, row_var=PAUSE_ROW_VAR)
    made += nav_nodes
    enter = _call(ed, FN_WAS_PRESSED, x0 + 1740, y0 + 400, made, self=pc_out,
                  Key=PAUSE_ACCEPT_KEY)
    take, idle = _branch(ed, _out(enter), moved, x0 + 2000, y0, made)
    taken = put(ed, PAUSE_CLICK_VAR, _get(ed, PAUSE_ROW_VAR, x0 + 2000, y0 + 400, made),
                [take], x0 + 2260, y0, made)
    return [taken, idle]


def _author_row_words(ed, rows, in_execs, x0, y0, made):
    """What the rows say that depends on whether a game is in play: the first
    row is new game on the title and resume in play, and the rows that need
    a game say so on the title. Returns the exec tails."""
    def by_state(index, widget, playing_says, title_says, execs, x):
        row, found, missing = row_at(ed, rows, index, execs, x, y0)
        text = member(ed, row, WBP_MENU_ROW, widget, x + 540, y0 + 300)
        playing, title = _branch(ed, _get(ed, GAME_STARTED_VAR, x + 540, y0 + 500, made),
                                 [found], x + 800, y0, made)
        return [set_text(ed, text, playing_says, [playing], x + 1060, y0),
                set_text(ed, text, title_says, [title], x + 1060, y0 + 300), missing]

    flow = by_state(PAUSE_START_ROW, ROW_LABEL, RESUME_ROW_LABEL, START_ROW_LABEL,
                    in_execs, x0)
    for i, action in enumerate(IN_GAME_ACTIONS):
        flow = by_state(PAUSE_ROW_ACTIONS.index(action), ROW_VALUE, "", IN_GAME_ONLY,
                        flow, x0 + 1500 * (i + 1))
    return flow


def author_pause_menu(ed, x0, y0, in_execs):
    """The menu, while MenuOpen: on the title (author_title holds it open)
    and in play, where M toggles it. The caret is on PauseRow. Its labels are
    WBP_PauseMenu's. Returns the exec tails.

    First, for everything a living player has open: the cursor shows with
    the menu or the loot window, and while it does a click is not a shot.

    One menu on screen: the settings page (WBP_MainMenu's, while MenuPage
    says so) or an open tuning tab (tune_draw.py) stands in the rows' place,
    and its BACK row brings these back. A row is taken with Enter or a click,
    which raises PauseClick for Tick; the rows have no keys of their own."""
    made = []
    get_open = _at(ed.add_get_member_variable_node("MenuOpen"), x0, y0 + 200)
    looting = _at(ed.add_get_member_variable_node(LOOT_OPEN_VAR), x0 - 500, y0 - 900)
    wanted = _at(_node(ed, FN_OR), x0 - 260, y0 - 1000)
    _connect(_pin(_at(ed.add_get_member_variable_node("MenuOpen"), x0 - 500, y0 - 1040),
                  "MenuOpen", is_input=False), _pin(wanted, "A"))
    _connect(_pin(looting, LOOT_OPEN_VAR, is_input=False), _pin(wanted, "B"))
    # ...or the I panel (wear_draw.py).
    wearing = _at(ed.add_get_member_variable_node(WEAR_OPEN_VAR), x0 - 260, y0 - 760)
    wanted_any = _at(_node(ed, FN_OR), x0 - 20, y0 - 1000)
    _connect(_pin(wanted, "ReturnValue", is_input=False), _pin(wanted_any, "A"))
    _connect(_pin(wearing, WEAR_OPEN_VAR, is_input=False), _pin(wanted_any, "B"))
    wanted = wanted_any
    in_execs = author_hold_fire(ed, author_cursor_mode(
        ed, _pin(wanted, "ReturnValue", is_input=False), in_execs, x0, y0 - 1400),
        x0 + 2200, y0 - 1400)
    br = _at(ed.add_branch_node(), x0 + 260, y0)
    _connect(_pin(get_open, "MenuOpen", is_input=False), _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    # WBP_MainMenu goes up and down with the menu: its legal notice is on
    # every page of it, and its settings panel is one of the pages.
    closed = set_shown(ed, screen(ed, WBP_PAUSE_MENU, x0 + 260, y0 + 600), False,
                       [BEL.find_else_pin(br)], x0 + 520, y0 + 600)
    closed = set_shown(ed, screen(ed, WBP_MAIN_MENU, x0 + 260, y0 + 800), False,
                       [closed], x0 + 780, y0 + 600)

    flow = set_shown(ed, screen(ed, WBP_PAUSE_MENU, x0 + 260, y0 + 240), True,
                     [BEL.find_then_pin(br)], x0 + 520, y0)
    flow = set_shown(ed, screen(ed, WBP_MAIN_MENU, x0 + 260, y0 + 400), True,
                     [flow], x0 + 780, y0)
    panel = part(ed, WBP_PAUSE_MENU, PAUSE_PANEL, x0 + 520, y0 + 2400)
    settings = part(ed, WBP_MAIN_MENU, SETTINGS_PANEL, x0 + 520, y0 + 2600)
    on_rows = _call(ed, FN_EQ_II, x0 + 780, y0 + 2900, made,
                    A=_get(ed, "MenuPage", x0 + 520, y0 + 2900, made), B=PAGE_TITLE)
    on_menu, on_settings = _branch(ed, _out(on_rows), [flow], x0 + 1040, y0 + 2000, made)
    _author_settings_page(ed, x0, y0 + 9000, set_shown(
        ed, settings, True, [set_shown(ed, panel, False, [on_settings],
                                       x0 + 1300, y0 + 2600)], x0 + 1560, y0 + 2600))
    flow = set_shown(ed, settings, False, [on_menu], x0 + 1300, y0 + 2000)

    in_tab, in_panel = _branch(ed, _any_tab_open(ed, x0 + 520, y0 + 1600, made), [flow],
                               x0 + 1300, y0 + 1400, made)
    tabbed = set_shown(ed, panel, False, [in_tab], x0 + 1560, y0 + 1800)
    flow = set_shown(ed, panel, True, [in_panel], x0 + 1560, y0 + 1400)

    rows = part(ed, WBP_PAUSE_MENU, PAUSE_ROWS, x0 + 520, y0 + 400)
    hovered = author_row_cursor(ed, rows, len(PAUSE_ROW_LABELS), [flow], x0 + 4400,
                                y0 - 1400, row_var=PAUSE_ROW_VAR,
                                click=(PAUSE_CLICK_VAR, ROW))
    keyed = _author_pause_keys(ed, hovered, x0 + 4400, y0 - 4400, made)
    caret = _at(ed.add_get_member_variable_node(PAUSE_ROW_VAR), x0 + 780, y0 + 600)
    flow = mark_rows(ed, rows, len(PAUSE_ROW_LABELS),
                     _pin(caret, PAUSE_ROW_VAR, is_input=False), keyed, x0 + 1040, y0)
    worded = _author_row_words(ed, rows, [flow], x0 + 2400, y0 - 7000, made)

    # ON or OFF behind one branch: no SelectText, and a bool converted to text
    # reads "true", which is a variable's value and not a setting.
    debug_row, found, missing = row_at(ed, rows, PAUSE_DEBUG_ROW, worded, x0 + 2400, y0)
    value = member(ed, debug_row, WBP_MENU_ROW, ROW_VALUE, x0 + 2940, y0 + 300)
    dbg = _at(ed.add_get_member_variable_node("DebugOn"), x0 + 2940, y0 + 500)
    dbg_br = _at(ed.add_branch_node(), x0 + 3200, y0)
    _connect(_pin(dbg, "DebugOn", is_input=False), _pin(dbg_br, "Condition"))
    _connect(found, _pin(dbg_br, "execute"))
    on = set_text(ed, value, DEBUG_ON, [BEL.find_then_pin(dbg_br)], x0 + 3460, y0)
    off = set_text(ed, value, DEBUG_OFF, [BEL.find_else_pin(dbg_br)], x0 + 3460, y0 + 300)
    ed.add_comment_to_nodes(
        "The menu: the title's, and M's in play. Its rows show unless the "
        "settings page or a tuning tab is open in their place. The caret is "
        "on PauseRow: Up/Down or the cursor move it, Enter or a click takes "
        "the row (PauseClick, served by Tick). The first row reads new game "
        "or resume; debug mode's row says ON or OFF.",
        [get_open, br, caret, dbg, dbg_br])
    return [closed, on, off, missing, tabbed]
