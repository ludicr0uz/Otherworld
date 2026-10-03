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

from combat.graph import BEL, _connect, _pin
from uebp.graph import out
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.gfx_tune_consts import TUNER_COMPONENT
from graphics_menu.loot_find import put
from graphics_menu.menu_nav import pause_row_taken
from graphics_menu.settings_rows import PAGE_SETTINGS
from graphics_menu.umg_consts import (
    GAME_STARTED_VAR, MENU_KEY, QUIT_ACTION, SETTINGS_ACTION, START_ACTION)

FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_QUIT = "/Script/Engine.KismetSystemLibrary.QuitGame"
FN_ACTOR_TICK_PAUSED = "/Script/Engine.Actor.SetTickableWhenPaused"
FN_COMP_TICK_PAUSED = "/Script/Engine.ActorComponent.SetTickableWhenPaused"


def _then(node, in_execs):
    for e in in_execs:
        _connect(e, _pin(node, "execute"))
    return BEL.find_then_pin(node)


def author_title_ticks(ed, in_execs, x0, y0):
    """BeginPlay, on its way to the paused title: the HUD and its tuner tick
    while paused. Returns the then pin."""
    made = []
    hud = _call(ed, FN_ACTOR_TICK_PAUSED, x0, y0, made, bTickableWhenPaused="true")
    tuner = _call(ed, FN_COMP_TICK_PAUSED, x0 + 300, y0, made,
                  self=_get(ed, TUNER_COMPONENT, x0, y0 + 240, made),
                  bTickableWhenPaused="true")
    flow = _then(tuner, [_then(hud, in_execs)])
    ed.add_comment_to_nodes(
        "The title is a paused world and the menu's rows are served on Tick: "
        "the HUD, and the tuner that applies a picked preset, tick while "
        "paused until the game starts.", made)
    return flow


def author_in_play(ed, in_execs, x0, y0):
    """Tick's split on GameStarted. Returns ``(in_play, on_title)``."""
    made = []
    return _branch(ed, _get(ed, GAME_STARTED_VAR, x0, y0 + 240, made), in_execs,
                   x0 + 260, y0, made)


def _author_start(ed, in_execs, x0, y0, made):
    """The first row: resume in play, new game on the title."""
    take, rest = _branch(ed, pause_row_taken(ed, START_ACTION, x0 - 480, y0 + 300, made),
                         in_execs, x0 + 240, y0, made)
    flow = _setter(ed, "MenuOpen", "false", [take], x0 + 500, y0, made)
    resumed, fresh = _branch(ed, _get(ed, GAME_STARTED_VAR, x0 + 500, y0 + 300, made),
                             [flow], x0 + 760, y0, made)
    flow = _setter(ed, GAME_STARTED_VAR, "true", [fresh], x0 + 1020, y0 + 200, made)
    still = _call(ed, FN_ACTOR_TICK_PAUSED, x0 + 1280, y0 + 200, made,
                  bTickableWhenPaused="false")
    # Unpause LAST. GameStarted is already up, so the very next frame draws
    # the HUD rather than the title, and the world never runs behind a menu.
    resume = _call(ed, FN_SET_PAUSED, x0 + 1560, y0 + 200, made, bPaused="false")
    return [_then(resume, [_then(still, [flow])]), resumed, rest]


def _author_settings(ed, in_execs, x0, y0, made):
    """The settings row: its page in the rows' place, caret at its top."""
    take, rest = _branch(ed, pause_row_taken(ed, SETTINGS_ACTION, x0 - 480, y0 + 300,
                                             made), in_execs, x0 + 240, y0, made)
    flow = _setter(ed, "MenuPage", PAGE_SETTINGS, [take], x0 + 500, y0, made)
    return [_setter(ed, "MenuRow", 0, [flow], x0 + 760, y0, made), rest]


def _author_quit(ed, pc_out, in_execs, x0, y0, made):
    """The exit-game row: out to the desktop, saving nothing."""
    take, rest = _branch(ed, pause_row_taken(ed, QUIT_ACTION, x0 - 480, y0 + 300, made),
                         in_execs, x0 + 240, y0, made)
    quit_game = _call(ed, FN_QUIT, x0 + 500, y0, made, SpecificPlayer=pc_out)
    return [_then(quit_game, [take]), rest]


def _author_toggle(ed, pc_out, in_execs, x0, y0, made):
    """M in play flips MenuOpen. Nested, not ANDed with GameStarted, so the
    key is only polled in play."""
    in_play, on_title = _branch(ed, _get(ed, GAME_STARTED_VAR, x0, y0 + 300, made),
                                in_execs, x0 + 240, y0, made)
    pressed = _call(ed, FN_WAS_PRESSED, x0 + 240, y0 + 300, made, self=pc_out,
                    Key=MENU_KEY)
    flip, idle = _branch(ed, out(pressed), [in_play], x0 + 500, y0, made)
    flipped = _call(ed, FN_NOT, x0 + 500, y0 + 300, made,
                    A=_get(ed, "MenuOpen", x0 + 260, y0 + 440, made))
    return [put(ed, "MenuOpen", out(flipped), [flip], x0 + 760, y0, made), idle,
            on_title]


def author_main_rows_tick(ed, pc_out, in_execs, x0, y0):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = _author_start(ed, in_execs, x0, y0, made)
    flow = _author_settings(ed, flow, x0 + 2200, y0, made)
    flow = _author_quit(ed, pc_out, flow, x0 + 3600, y0, made)
    flow = _author_toggle(ed, pc_out, flow, x0 + 4800, y0, made)
    ed.add_comment_to_nodes(
        f"The menu's own rows, and {MENU_KEY}. The first row starts the game "
        f"from the title (unpausing last) and shuts the menu in play; settings "
        f"opens its page in the rows' place; exit game quits to the desktop. "
        f"{MENU_KEY} toggles the menu, in play only. Polled on Tick rather than "
        f"bound as an input action: an FInputActionValue binding would need an "
        f"IA asset and an IMC entry, and neither is authorable from Python.",
        made)
    return flow
