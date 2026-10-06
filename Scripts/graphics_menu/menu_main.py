"""The menu's own rows and its key, on Tick: starting or resuming the game,
the settings page, leaving for the desktop, and M.

    BeginPlay, on the title   the HUD and its tuner tick while paused
    every Tick (the title's too):
        new game / resume taken   MenuOpen = false; on the title also
                                  GameStarted = true, the HUD stops ticking
                                  while paused, and the world unpauses
        settings taken            MenuPage = the settings page, caret on top
        exit game taken           QuitGame
        M, in play                MenuOpen flips
        Escape, in play           on the menu's own rows: MenuOpen = false

The menu is one menu: the game opens on it, paused, and M brings the same
one up in play (menu_screens.py draws it and raises PauseClick). Its rows are
served on Tick, and Event Tick does not run in a paused world, so BeginPlay
makes this actor tick while paused for as long as the title stands. Only the
title: under the death screen, the other paused one, Tick stays stopped as
it always was. The tuner component ticks while paused too, so a preset
picked on the title is applied there.

M is polled only in play: the title's menu has nothing under it to go back
to. What needs a game in play (save and exit, the loot window, the cheat) is
kept off the title by author_in_play, which splits Tick's chain.
"""

from uebp.graph import _connect, _pin, out, then
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.gfx_tune_consts import TUNER_COMPONENT
from graphics_menu.loot_find import put
from graphics_menu.menu_nav import any_tab_open, escape_pressed, pause_row_taken
from graphics_menu.settings_rows import PAGE_SETTINGS, PAGE_TITLE
from graphics_menu.umg_consts import (
    GAME_STARTED_VAR, MENU_KEY, QUIT_ACTION, SETTINGS_ACTION, START_ACTION)
from uebp.nodes.actor import FN_ACTOR_TICK_PAUSED, FN_COMP_TICK_PAUSED, FN_WAS_PRESSED
from uebp.nodes.math import FN_AND, FN_EQ_II, FN_NOT, FN_OR
from uebp.nodes.system import FN_QUIT
from net.pause import author_unpause
from graphics_menu import hud_vars as MV


def _then(node, in_execs):
    for e in in_execs:
        _connect(e, _pin(node, "execute"))
    return then(node)


def author_title_ticks(ed, in_execs):
    """BeginPlay, on its way to the paused title: the HUD and its tuner tick
    while paused. Returns the then pin."""
    made = []
    hud = _call(ed, FN_ACTOR_TICK_PAUSED, made, bTickableWhenPaused="true")
    tuner = _call(ed, FN_COMP_TICK_PAUSED, made,
                  self=_get(ed, TUNER_COMPONENT, made),
                  bTickableWhenPaused="true")
    flow = _then(tuner, [_then(hud, in_execs)])
    ed.add_comment_to_nodes(
        "The title is a paused world and the menu's rows are served on Tick: "
        "the HUD, and the tuner that applies a picked preset, tick while "
        "paused until the game starts.", made)
    return flow


def author_in_play(ed, in_execs):
    """Tick's split on GameStarted. Returns ``(in_play, on_title)``."""
    made = []
    return _branch(ed, _get(ed, GAME_STARTED_VAR, made), in_execs, made)


def _author_start(ed, in_execs, made):
    """The first row: resume in play, new game on the title."""
    take, rest = _branch(ed, pause_row_taken(ed, START_ACTION, made), in_execs, made)
    flow = _setter(ed, MV.MenuOpen, "false", [take], made)
    resumed, fresh = _branch(ed, _get(ed, GAME_STARTED_VAR, made), [flow], made)
    flow = _setter(ed, GAME_STARTED_VAR, "true", [fresh], made)
    still = _call(ed, FN_ACTOR_TICK_PAUSED, made, bTickableWhenPaused="false")
    # Unpause LAST. GameStarted is already up, so the very next frame draws
    # the HUD rather than the title, and the world never runs behind a menu.
    return [author_unpause(ed, [_then(still, [flow])], made), resumed, rest]


def _author_settings(ed, in_execs, made):
    """The settings row: its page in the rows' place, caret at its top."""
    take, rest = _branch(ed, pause_row_taken(ed, SETTINGS_ACTION, made), in_execs, made)
    flow = _setter(ed, MV.MenuPage, PAGE_SETTINGS, [take], made)
    return [_setter(ed, MV.MenuRow, 0, [flow], made), rest]


def _author_quit(ed, pc_out, in_execs, made):
    """The exit-game row: out to the desktop, saving nothing."""
    take, rest = _branch(ed, pause_row_taken(ed, QUIT_ACTION, made), in_execs, made)
    quit_game = _call(ed, FN_QUIT, made, SpecificPlayer=pc_out)
    return [_then(quit_game, [take]), rest]


def _author_toggle(ed, pc_out, in_execs, made):
    """M in play flips MenuOpen. Nested, not ANDed with GameStarted, so the
    key is only polled in play."""
    in_play, on_title = _branch(ed, _get(ed, GAME_STARTED_VAR, made), in_execs, made)
    pressed = _call(ed, FN_WAS_PRESSED, made, self=pc_out, Key=MENU_KEY)
    flip, idle = _branch(ed, out(pressed), [in_play], made)
    flipped = _call(ed, FN_NOT, made, A=_get(ed, MV.MenuOpen, made))
    return _author_escape(ed, pc_out, [put(ed, MV.MenuOpen, out(flipped), [flip], made), idle],
                          made) + [on_title]


def _author_escape(ed, pc_out, in_execs, made):
    """Escape in play, on the menu's own rows, shuts the menu: BACK from the
    top. With the controls page or a tab up it is theirs (DrawHUD lowers the
    page or the tab later in the same frame, so this must not also take the
    menu down: hence the test on what is up now)."""
    pressed, rest = _branch(ed, escape_pressed(ed, pc_out, made), in_execs, made)
    on_rows = _call(ed, FN_EQ_II, made, A=_get(ed, MV.MenuPage, made), B=PAGE_TITLE)
    paged = _call(ed, FN_OR, made, A=out(_call(ed, FN_NOT, made, A=out(on_rows))),
                  B=any_tab_open(ed, made))
    top = _call(ed, FN_AND, made, A=_get(ed, MV.MenuOpen, made),
                B=out(_call(ed, FN_NOT, made, A=out(paged))))
    shut, kept = _branch(ed, out(top), [pressed], made)
    return [_setter(ed, MV.MenuOpen, "false", [shut], made), kept, rest]


def author_main_rows_tick(ed, pc_out, in_execs):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = _author_start(ed, in_execs, made)
    flow = _author_settings(ed, flow, made)
    flow = _author_quit(ed, pc_out, flow, made)
    flow = _author_toggle(ed, pc_out, flow, made)
    ed.add_comment_to_nodes(
        f"The menu's own rows, and {MENU_KEY}. The first row starts the game "
        f"from the title (unpausing last) and shuts the menu in play; settings "
        f"opens its page in the rows' place; exit game quits to the desktop. "
        f"{MENU_KEY} toggles the menu, in play only, and Escape on its own rows "
        f"shuts it. Polled on Tick rather than "
        f"bound as an input action: an FInputActionValue binding would need an "
        f"IA asset and an IMC entry, and neither is authorable from Python.",
        made)
    return flow
