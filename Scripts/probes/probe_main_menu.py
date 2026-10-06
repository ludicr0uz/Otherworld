"""The title is the menu over a paused world, and its rows are served there.

Event Tick does not run in a paused world, and every row of the menu is
served on Tick (menu_main.py). BeginPlay makes the HUD tick while paused on
its way to the title; a probe's game starts with -nomenu, which skips that,
so the probe does by hand what BeginPlay does (pause, GameStarted false, the
HUD tickable while paused) and takes rows by writing PauseClick, as a click
would.

  paused, the HUD not ticking   a taken row is not served: the flag matters
  paused, ticking               the debug row flips debug mode; a tab opens;
                                save and exit does nothing (it needs a game)
  the first row                 the Single Player page in the rows' place;
                                nothing starts yet
  the second row                the Multiplayer page
  the Single Player page's row  GameStarted, the menu shut and back on its
                                rows, the world unpaused, and the HUD's paused
                                tick given up; with the gun table touched (a
                                kept save loaded at BeginPlay), which once
                                ended Tick before the menu's rows
  in play                       the same row shuts the menu and nothing else

Waits are on the wall clock or on a condition: game time stands still here.
"""

import time

import unreal

from combat.game_state import DEBUG_MODE_VAR
from graphics_menu import cursor_consts as CC
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.profile_consts import EXIT_ACTION, EXIT_PENDING_VAR
from graphics_menu.settings_rows import PAGE_TITLE
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (MV.MenuOpen, C.GAME_STARTED_VAR, CC.PAUSE_CLICK_VAR,
                                       GUN_TAB.open_var, GUN_TAB.touched_var,
                                       MV.MenuPage, CC.PAGE_CLICK_VAR)]


def _row(action):
    return C.PAUSE_ROW_ACTIONS.index(action)


def _after(seconds):
    until = time.time() + seconds
    return lambda: time.time() >= until


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield 0.3
    hud, mode, world = p.hud(), p.game_state(), p.world()
    was_debug = p.get(mode, DEBUG_MODE_VAR)

    # --- the title, as BeginPlay leaves it, but for the paused tick -----------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuOpen", True)
    hud.set_tickable_when_paused(False)
    unreal.GameplayStatics.set_game_paused(world, True)
    yield _after(0.3)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(C.DEBUG_ACTION))
    yield _after(0.5)
    p.check("paused with the HUD not ticking, a taken row is not served",
            unreal.GameplayStatics.is_game_paused(world)
            and p.get(mode, DEBUG_MODE_VAR) == was_debug, str(p.get(mode, DEBUG_MODE_VAR)))
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)

    # --- ticking while paused: the rows work on the title ----------------------
    hud.set_tickable_when_paused(True)
    yield _after(0.2)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(C.DEBUG_ACTION))
    yield lambda: p.get(mode, DEBUG_MODE_VAR) != was_debug
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("ticking while paused, the debug row is served on the title",
            p.get(mode, DEBUG_MODE_VAR) != was_debug)
    yield _after(0.2)
    # ...and back, so the saved setting ends as it began. One Tick's worth: the
    # row held for two would flip it twice.
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(C.DEBUG_ACTION))
    yield lambda: p.get(mode, DEBUG_MODE_VAR) == was_debug
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)

    yield _after(0.2)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(GUN_TAB.action))
    yield lambda: p.get(hud, GUN_TAB.open_var)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("...and a tuning tab opens there", p.get(hud, GUN_TAB.open_var) is True)
    p.set(hud, GUN_TAB.open_var, False)

    p.set(hud, CC.PAUSE_CLICK_VAR, _row(EXIT_ACTION))
    yield _after(0.5)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("...but save and exit does nothing: it needs a game in play",
            p.get(hud, EXIT_PENDING_VAR) is False and p.get(hud, "MenuOpen") is True,
            f"pending {p.get(hud, EXIT_PENDING_VAR)}, open {p.get(hud, 'MenuOpen')}")
    p.check("...and the world is still paused under the menu",
            unreal.GameplayStatics.is_game_paused(world))

    # --- the two modes: each row opens its page, in the rows' place -------------
    for action, page in ((C.MULTI_ACTION, MC.MULTI), (C.START_ACTION, MC.SINGLE)):
        p.set(hud, CC.PAUSE_CLICK_VAR, _row(action))
        paged = _after(5.0)
        yield lambda: p.get(hud, MV.MenuPage) == page.page or paged()
        p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
        p.check(f"the {page.title.lower()} row on the title opens its page, and "
                f"starts nothing: still the title, still paused",
                p.get(hud, MV.MenuPage) == page.page and p.get(hud, MV.MenuRow) == 0
                and p.get(hud, C.GAME_STARTED_VAR) is False
                and unreal.GameplayStatics.is_game_paused(world),
                f"page {p.get(hud, MV.MenuPage)}, row {p.get(hud, MV.MenuRow)}, "
                f"started {p.get(hud, C.GAME_STARTED_VAR)}")
        if page is MC.MULTI:
            # BACK (DrawHUD's, which a -nullrhi run does not draw).
            p.set(hud, MV.MenuPage, PAGE_TITLE)
            yield _after(0.2)

    # --- the Single Player page's row starts the game ----------------------------
    # The gun table touched, as a kept GUN SETTINGS save leaves it from BeginPlay.
    p.set(hud, GUN_TAB.touched_var, True)
    yield _after(0.3)
    p.set(hud, CC.PAGE_CLICK_VAR, MC.SINGLE_START_ROW)
    started = _after(5.0)
    yield lambda: p.get(hud, C.GAME_STARTED_VAR) or started()
    p.set(hud, CC.PAGE_CLICK_VAR, CC.NO_ROW)
    p.check("the Single Player page's row starts the game, the gun table touched "
            "(a kept save): the menu shut, back on its rows, and the world unpaused",
            p.get(hud, C.GAME_STARTED_VAR) is True and p.get(hud, "MenuOpen") is False
            and p.get(hud, MV.MenuPage) == PAGE_TITLE
            and not unreal.GameplayStatics.is_game_paused(world),
            f"started {p.get(hud, C.GAME_STARTED_VAR)}, open {p.get(hud, 'MenuOpen')}, "
            f"page {p.get(hud, MV.MenuPage)}, "
            f"paused {unreal.GameplayStatics.is_game_paused(world)}")
    p.check("...and the HUD gives its paused tick up, so the death screen's pause "
            "still stops it", hud.get_tickable_when_paused() is False)

    # --- in play the same row is resume -------------------------------------------
    yield 0.1
    p.set(hud, "MenuOpen", True)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(C.START_ACTION))
    yield lambda: not p.get(hud, "MenuOpen")
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("in play the first row shuts the menu, and the game goes on",
            p.get(hud, "MenuOpen") is False and p.get(hud, C.GAME_STARTED_VAR) is True
            and p.get(hud, MV.MenuPage) == PAGE_TITLE
            and not unreal.GameplayStatics.is_game_paused(world))
    # ...and the second does nothing there: a game in play is already in a mode.
    p.set(hud, "MenuOpen", True)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(C.MULTI_ACTION))
    yield 0.3
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("in play the multiplayer row opens nothing: its page is the title's",
            p.get(hud, MV.MenuPage) == PAGE_TITLE, f"page {p.get(hud, MV.MenuPage)}")
    p.set(hud, "MenuOpen", False)
