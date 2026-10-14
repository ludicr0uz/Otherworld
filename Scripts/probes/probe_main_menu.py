"""The menu's rows are served on Tick, whether the world is paused or not.

Every row of the menu is served on Tick (menu_main.py), and Event Tick does
not run in a paused world. The real title is a level of its own and is not
paused (Scripts/title); this probe holds a title up by hand on its level under
-nomenu (GameStarted false) and pauses the world itself, to show the HUD's
tick flag is what serves a row under a pause, and takes rows by writing
PauseClick, as a click would.

  paused, the HUD not ticking   a taken row is not served: the flag matters
  paused, ticking               the debug settings row opens its tab; a tab opens;
                                save and exit does nothing (it needs a game)
  the first row                 the Single Player page in the rows' place;
                                nothing starts yet
  the second row                the Multiplayer page
  the Single Player page's row  not taken here: it opens the play level
                                (probe_title_figure.py takes it from the real
                                title). A game in play is made by hand, as
                                -nomenu makes one
  in play                       the first row shuts the menu and nothing else

Waits are on the wall clock or on a condition: game time stands still here.
"""

SYSTEMS = ('menu',)

import time

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from combat.ask_consts import EXIT_PENDING_VAR
from combat.paths import WEAPON_COMP_CLASS_PATH
from graphics_menu.settings_rows import PAGE_TITLE
from graphics_menu.debug_tune_consts import DEBUG_TAB
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (MV.MenuOpen, C.GAME_STARTED_VAR, CC.PAUSE_CLICK_VAR,
                                       GUN_TAB.open_var, GUN_TAB.touched_var, DEBUG_TAB.open_var,
                                       MV.MenuPage, CC.PAGE_CLICK_VAR)]


def _row(action):
    return C.PAUSE_ROW_ACTIONS.index(action)


def _after(seconds):
    until = time.time() + seconds
    return lambda: time.time() >= until


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield 0.3
    hud, world = p.hud(), p.world()
    p.set(hud, DEBUG_TAB.open_var, False)

    # --- the title, as BeginPlay leaves it, but for the paused tick -----------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuOpen", True)
    hud.set_tickable_when_paused(False)
    unreal.GameplayStatics.set_game_paused(world, True)
    yield _after(0.3)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(DEBUG_TAB.action))
    yield _after(0.5)
    p.check("paused with the HUD not ticking, a taken row is not served",
            unreal.GameplayStatics.is_game_paused(world)
            and not p.get(hud, DEBUG_TAB.open_var), str(p.get(hud, DEBUG_TAB.open_var)))
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)

    # --- ticking while paused: the rows work on the title ----------------------
    hud.set_tickable_when_paused(True)
    yield _after(0.2)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(DEBUG_TAB.action))
    yield lambda: p.get(hud, DEBUG_TAB.open_var)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("ticking while paused, the debug settings row is served on the title",
            p.get(hud, DEBUG_TAB.open_var))
    p.set(hud, DEBUG_TAB.open_var, False)

    yield _after(0.2)
    p.set(hud, CC.PAUSE_CLICK_VAR, _row(GUN_TAB.action))
    yield lambda: p.get(hud, GUN_TAB.open_var)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("...and a tuning tab opens there", p.get(hud, GUN_TAB.open_var) is True)
    p.set(hud, GUN_TAB.open_var, False)

    # The last row is exit game here (QuitGame: taking it would end this run;
    # the verifier holds it to the title). The rows above served no exit.
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    p.check("...and no save and exit is running on the title",
            p.get(wc, EXIT_PENDING_VAR) is False and p.get(hud, "MenuOpen") is True,
            f"pending {p.get(wc, EXIT_PENDING_VAR)}, open {p.get(hud, 'MenuOpen')}")
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

    # --- the Single Player page's row opens the play level, so it is not taken
    # here (probe_title_figure.py takes it, from the real title). A game in
    # play is made by hand instead, as -nomenu makes one.
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.set(hud, MV.MenuPage, PAGE_TITLE)
    p.set(hud, "MenuOpen", False)
    p.set(hud, C.GAME_STARTED_VAR, True)
    unreal.GameplayStatics.set_game_paused(world, False)
    yield _after(0.3)
    p.check("a game in play (GameStarted, as -nomenu sets it): the menu shut, on its "
            "rows, the world unpaused",
            p.get(hud, C.GAME_STARTED_VAR) is True and p.get(hud, "MenuOpen") is False
            and p.get(hud, MV.MenuPage) == PAGE_TITLE
            and not unreal.GameplayStatics.is_game_paused(world),
            f"started {p.get(hud, C.GAME_STARTED_VAR)}, open {p.get(hud, 'MenuOpen')}, "
            f"page {p.get(hud, MV.MenuPage)}, "
            f"paused {unreal.GameplayStatics.is_game_paused(world)}")

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
