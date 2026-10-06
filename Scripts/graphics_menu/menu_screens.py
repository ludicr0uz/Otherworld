"""DrawHUD: which screen is up, and the menus' live parts.

  author_title       GameStarted false: the menu stands alone, open, over a
                     hidden HUD and a paused world
  author_death_menu  PlayerDead: WBP_DeathMenu instead of the HUD, the score,
                     and, in standalone, [R] restarting the level; as a client
                     of a server the hint says a respawn is coming and no key
                     or click does anything
  author_alive       neither: the HUD's Body shown, the death menu hidden
  author_pause_menu  MenuOpen: the menu (WBP_PauseMenu), the same one on the
                     title and in play. Its rows (Up/Down/Enter, the caret,
                     the rows' words, debug ON/OFF) unless the settings
                     page, a mode page or a tuning tab is open in their place

Each also says whether the mouse cursor shows, and what a click on it does
(cursor.py): always on the title and death screens; alive, with the menu or
the loot window open.

Everything here is polled and written in DrawHUD rather than on Tick: the
title and death screens are a paused world, and DrawHUD is called by the
renderer every frame regardless. APlayerController sets bTickEvenWhenPaused,
so WasInputKeyJustPressed still answers. What a taken row does is Tick's
(menu_main.py), which the HUD keeps running under the paused title.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from graphics_menu.cursor import (
    ROW, author_cursor_mode, author_hold_fire, author_row_cursor, author_widget_click)
from graphics_menu.cursor_consts import CURSOR_ACCEPT_VAR, PAUSE_CLICK_VAR
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.loot_find import put
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.wear_consts import WEAR_OPEN_VAR
from graphics_menu.menu_nav import _emit_row_nav, any_tab_open
from graphics_menu.settings_page import _author_settings_page
from graphics_menu.settings_rows import PAGE_SETTINGS, PAGE_TITLE
from graphics_menu.mode_draw import author_mode_hidden, author_mode_pages, author_mode_words
from graphics_menu.ui_graph import (
    mark_rows, member, part, row_at, screen, set_shown, set_text,
)
from graphics_menu.umg_consts import (
    DEATH_HINT_LINE, DEATH_HINT_SERVER, DEATH_SCORE, DEATH_SCORE_PREFIX, DEBUG_OFF,
    DEBUG_ON, GAME_STARTED_VAR,
    HUD_BODY, IN_GAME_ACTIONS, IN_GAME_ONLY, PAUSE_ACCEPT_KEY, PAUSE_DEBUG_ROW, PAUSE_PANEL,
    PAUSE_ROW_ACTIONS, PAUSE_ROW_LABELS, PAUSE_ROW_VAR, PAUSE_ROWS, RESTART_KEY, ROW_VALUE,
    SETTINGS_PANEL, WBP_DEATH_MENU, WBP_HUD, WBP_MAIN_MENU, WBP_MENU_ROW, WBP_PAUSE_MENU,
)
from uebp.nodes.actor import FN_GET_OWNING_PC, FN_WAS_PRESSED
from uebp.nodes.math import FN_EQ_II, FN_OR
from uebp.nodes.system import (
    FN_CONCAT, FN_INT_TO_STR, FN_IS_STANDALONE, FN_LEVEL_NAME, FN_OPEN_LEVEL)
from net.pause import author_unpause
from net.state_consts import PLAYER_STATE_CLASS_PATH
from graphics_menu import hud_vars as MV

KILL_COUNT_VAR = "NpcKillCount"


def author_title(ed, in_execs):
    """Before the game starts the menu stands alone: nothing of the HUD or
    the death menu under it, and it is open -- MenuOpen is held up, so the
    title needs no drawing of its own and M has nothing to shut.

    Returns ``(title_tail, started_exec)``: the first goes on to the menu
    (author_pause_menu), the second to the rest of the HUD.
    """
    made = []
    started, title = _branch(ed, _get(ed, GAME_STARTED_VAR, made), in_execs, made)
    flow = set_shown(ed, part(ed, WBP_HUD, HUD_BODY), False, [title])
    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU), False, [flow])
    flow = _setter(ed, MV.MenuOpen, "true", [flow], made)
    ed.add_comment_to_nodes(
        f"The title: while {GAME_STARTED_VAR} is false, which BeginPlay leaves "
        f"it with while it pauses the world, the menu is held open over a "
        f"hidden HUD. It is the same menu M brings up in play; its first row "
        f"starts the game.", made)
    return flow, started


def author_death_menu(ed, in_execs, state_out):
    """What is on screen once the player is dead and the game is paused:
    WBP_DeathMenu instead of the HUD, not over it -- a reticle and an
    inventory over a death screen read as a game still being played.

    Restarting is SetGamePaused(false) *then* OpenLevel: a level opened while
    the world is paused comes up paused, with nothing left able to unpause it.

    Restarting is standalone's: there death ends that game (the mode table's
    death row, serversupportsysdesign.md 4.8). As a client of a server the
    same screen is up for the seconds until the server gives the player a
    new body (combat/player_respawn.py): the hint line says so, the restart
    key is not polled, and a click on the line is lowered unserved, so
    nothing is left raised for the HUD the respawned player comes back to.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU), True, author_cursor_mode(ed, True, in_execs))
    flow = set_shown(ed, part(ed, WBP_HUD, HUD_BODY), False, [flow])
    flow = set_shown(ed, screen(ed, WBP_PAUSE_MENU), False, [flow])
    flow = set_shown(ed, screen(ed, WBP_MAIN_MENU), False, [flow])

    # The same counter the corner shows, read again so the final score is the
    # live number rather than a copy taken when the player fell.
    kills = keep(ed.add_get_member_variable_node(KILL_COUNT_VAR, PLAYER_STATE_CLASS_PATH))
    _connect(state_out, _pin(kills, "self"))
    kills_str = keep(_node(ed, FN_INT_TO_STR))
    _connect(out(kills, KILL_COUNT_VAR), _pin(kills_str, "InInt"))
    score_text = keep(_node(ed, FN_CONCAT))
    _set(score_text, "A", DEATH_SCORE_PREFIX)
    _connect(out(kills_str), _pin(score_text, "B"))
    flow = set_text(ed, part(ed, WBP_DEATH_MENU, DEATH_SCORE), out(score_text), [flow])

    # --- whose death is this? -------------------------------------------------
    alone = keep(_node(ed, FN_IS_STANDALONE))
    ends = keep(ed.add_branch_node())
    _connect(out(alone), _pin(ends, "Condition"))
    _connect(flow, _pin(ends, "execute"))
    line = part(ed, WBP_DEATH_MENU, DEATH_HINT_LINE)
    waits = set_text(ed, line, DEATH_HINT_SERVER, [else_(ends)])
    unasked = keep(ed.add_set_member_variable_node(CURSOR_ACCEPT_VAR))
    _set(unasked, CURSOR_ACCEPT_VAR, False)
    _connect(waits, _pin(unasked, "execute"))
    flow = then(ends)

    # --- the restart itself --------------------------------------------------
    pc = keep(_node(ed, FN_GET_OWNING_PC))
    pressed = keep(_node(ed, FN_WAS_PRESSED))
    _connect(out(pc), _pin(pressed, "self"))
    _set(pressed, "Key", RESTART_KEY)
    # ...or a click on the hint line, raised and served like the title's.
    clicked = author_widget_click(
        ed, part(ed, WBP_DEATH_MENU, DEATH_HINT_LINE),
        (CURSOR_ACCEPT_VAR, "true"), [flow])
    asked = keep(ed.add_get_member_variable_node(CURSOR_ACCEPT_VAR))
    either = keep(_node(ed, FN_OR))
    _connect(out(pressed), _pin(either, "A"))
    _connect(out(asked, CURSOR_ACCEPT_VAR), _pin(either, "B"))
    again = keep(ed.add_branch_node())
    _connect(out(either), _pin(again, "Condition"))
    for e in clicked:
        _connect(e, _pin(again, "execute"))
    served = keep(ed.add_set_member_variable_node(CURSOR_ACCEPT_VAR))
    _set(served, CURSOR_ACCEPT_VAR, False)
    _connect(then(again), _pin(served, "execute"))
    unpaused = author_unpause(ed, [then(served)], made)
    # The current map by name, so the menu restarts whatever level is loaded.
    # bRemovePrefixString strips PIE's UEDPIE_0_.
    where = keep(_node(ed, FN_LEVEL_NAME))
    _set(where, "bRemovePrefixString", True)
    _connect(unpaused, _pin(where, "execute"))
    reopen = keep(_node(ed, FN_OPEN_LEVEL))
    _connect(out(where), _pin(reopen, "LevelName"))
    _connect(then(where), _pin(reopen, "execute"))

    ed.add_comment_to_nodes(
        f"The death menu, instead of the HUD while the GameMode's PlayerDead is "
        f"set and the game is paused. [{RESTART_KEY}] or a click on the hint "
        f"line unpauses and reopens the "
        f"current level, which resets the kill count with it -- the counter "
        f"lives on the GameMode, and OpenLevel builds a new one. In standalone only: "
        f"as a client of a server the hint says a respawn is coming, and nothing "
        f"restarts.",
        made)


def author_alive(ed, in_execs):
    """Playing and alive: the death menu down, the HUD's Body up."""
    flow = set_shown(ed, screen(ed, WBP_DEATH_MENU), False, in_execs)
    return (set_shown(ed, part(ed, WBP_HUD, HUD_BODY), True, [flow]),)


def _author_pause_keys(ed, in_execs, made):
    """Up / Down move the panel's caret; Enter takes the row it is on, as a
    click on the row does: PauseClick, which Tick serves. Returns the tails.

    DrawHUD rather than Tick, like the settings page's keys, though the menu
    pauses nothing in play: the row is raised in the same place for the key and the
    mouse, and top-of-frame lowers it once Tick has had its one look."""
    pc_out = out(_call(ed, FN_GET_OWNING_PC, made))
    moved, nav_nodes = _emit_row_nav(ed, pc_out, len(PAUSE_ROW_LABELS) - 1, in_execs, row_var=PAUSE_ROW_VAR)
    made += nav_nodes
    enter = _call(ed, FN_WAS_PRESSED, made, self=pc_out, Key=PAUSE_ACCEPT_KEY)
    take, idle = _branch(ed, out(enter), moved, made)
    taken = put(ed, PAUSE_CLICK_VAR, _get(ed, PAUSE_ROW_VAR, made), [take], made)
    return [taken, idle]


def _author_row_words(ed, rows, in_execs, made):
    """What the rows say that depends on whether a game is in play and in
    which mode (mode_draw.author_mode_words), and the rows that need a game
    say so on the title. Returns the exec tails."""
    def by_state(index, widget, playing_says, title_says, execs):
        row, found, missing = row_at(ed, rows, index, execs)
        text = member(ed, row, WBP_MENU_ROW, widget)
        playing, title = _branch(ed, _get(ed, GAME_STARTED_VAR, made), [found], made)
        return [set_text(ed, text, playing_says, [playing]),
                set_text(ed, text, title_says, [title]), missing]

    flow = author_mode_words(ed, rows, in_execs, made)
    for action in IN_GAME_ACTIONS:
        flow = by_state(PAUSE_ROW_ACTIONS.index(action), ROW_VALUE, "", IN_GAME_ONLY, flow)
    return flow


def author_pause_menu(ed, in_execs):
    """The menu, while MenuOpen: on the title (author_title holds it open)
    and in play, where M toggles it. The caret is on PauseRow. Its labels are
    WBP_PauseMenu's. Returns the exec tails.

    First, for everything a living player has open: the cursor shows with
    the menu or the loot window, and while it does a click is not a shot.

    One menu on screen: the settings page (WBP_MainMenu's, while MenuPage
    says so), a title mode page (mode_draw.py, likewise) or an open tuning
    tab (tune_draw.py) stands in the rows' place,
    and its BACK row brings these back. A row is taken with Enter or a click,
    which raises PauseClick for Tick; the rows have no keys of their own."""
    made = []
    get_open = ed.add_get_member_variable_node(MV.MenuOpen)
    looting = ed.add_get_member_variable_node(LOOT_OPEN_VAR)
    wanted = _node(ed, FN_OR)
    _connect(out(ed.add_get_member_variable_node(MV.MenuOpen), MV.MenuOpen), _pin(wanted, "A"))
    _connect(out(looting, LOOT_OPEN_VAR), _pin(wanted, "B"))
    # ...or the I panel (wear_draw.py).
    wearing = ed.add_get_member_variable_node(WEAR_OPEN_VAR)
    wanted_any = _node(ed, FN_OR)
    _connect(out(wanted), _pin(wanted_any, "A"))
    _connect(out(wearing, WEAR_OPEN_VAR), _pin(wanted_any, "B"))
    wanted = wanted_any
    in_execs = author_hold_fire(ed, author_cursor_mode(ed, out(wanted), in_execs))
    br = ed.add_branch_node()
    _connect(out(get_open, MV.MenuOpen), _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    # WBP_MainMenu goes up and down with the menu: its legal notice is on
    # every page of it, and its settings panel is one of the pages.
    closed = set_shown(ed, screen(ed, WBP_PAUSE_MENU), False, [else_(br)])
    closed = set_shown(ed, screen(ed, WBP_MAIN_MENU), False, [closed])

    flow = set_shown(ed, screen(ed, WBP_PAUSE_MENU), True, [then(br)])
    flow = set_shown(ed, screen(ed, WBP_MAIN_MENU), True, [flow])
    panel = part(ed, WBP_PAUSE_MENU, PAUSE_PANEL)
    settings = part(ed, WBP_MAIN_MENU, SETTINGS_PANEL)
    on_rows = _call(ed, FN_EQ_II, made, A=_get(ed, MV.MenuPage, made), B=PAGE_TITLE)
    on_menu, paged = _branch(ed, out(on_rows), [flow], made)
    paged = set_shown(ed, panel, False, [paged])
    on_page = _call(ed, FN_EQ_II, made, A=_get(ed, MV.MenuPage, made), B=PAGE_SETTINGS)
    on_settings, on_mode = _branch(ed, out(on_page), [paged], made)
    _author_settings_page(ed, set_shown(ed, settings, True, [on_settings]))
    # ...or one of the title's mode pages (mode_draw.py).
    author_mode_pages(ed, [set_shown(ed, settings, False, [on_mode])])
    flow = author_mode_hidden(ed, [set_shown(ed, settings, False, [on_menu])])

    in_tab, in_panel = _branch(ed, any_tab_open(ed, made), [flow], made)
    tabbed = set_shown(ed, panel, False, [in_tab])
    flow = set_shown(ed, panel, True, [in_panel])

    rows = part(ed, WBP_PAUSE_MENU, PAUSE_ROWS)
    hovered = author_row_cursor(ed, rows, len(PAUSE_ROW_LABELS), [flow], row_var=PAUSE_ROW_VAR,
                                click=(PAUSE_CLICK_VAR, ROW))
    keyed = _author_pause_keys(ed, hovered, made)
    caret = ed.add_get_member_variable_node(PAUSE_ROW_VAR)
    flow = mark_rows(ed, rows, len(PAUSE_ROW_LABELS), out(caret, PAUSE_ROW_VAR), keyed)
    worded = _author_row_words(ed, rows, [flow], made)

    # ON or OFF behind one branch: no SelectText, and a bool converted to text
    # reads "true", which is a variable's value and not a setting.
    debug_row, found, missing = row_at(ed, rows, PAUSE_DEBUG_ROW, worded)
    value = member(ed, debug_row, WBP_MENU_ROW, ROW_VALUE)
    dbg = ed.add_get_member_variable_node(MV.DebugOn)
    dbg_br = ed.add_branch_node()
    _connect(out(dbg, MV.DebugOn), _pin(dbg_br, "Condition"))
    _connect(found, _pin(dbg_br, "execute"))
    on = set_text(ed, value, DEBUG_ON, [then(dbg_br)])
    off = set_text(ed, value, DEBUG_OFF, [else_(dbg_br)])
    ed.add_comment_to_nodes(
        "The menu: the title's, and M's in play. Its rows show unless the "
        "settings page or a tuning tab is open in their place. The caret is "
        "on PauseRow: Up/Down or the cursor move it, Enter or a click takes "
        "the row (PauseClick, served by Tick). The first row reads single "
        "player or resume; debug mode's row "
        "says ON or OFF.",
        [get_open, br, caret, dbg, dbg_br])
    return [closed, on, off, missing, tabbed]
