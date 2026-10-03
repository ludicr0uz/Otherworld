"""The mouse cursor in the menus: it shows while a menu is up and hides for
play, a click on a menu row is not a shot, and what a click raises is served
as the row's action. Also the M panel as a menu: an open tuning tab stands in
place of the panel's rows, BACK's caret, and the open panel holding the
player still.

A -nullrhi run lays out no widget and has no mouse, so nothing is ever under
the cursor here: the probe raises what a click would (CursorAccept,
PauseClick) and calls the HUD's ReceiveDrawHUD itself, as probe_umg_screens
does. Which row the cursor is over, and the click itself,
need a window and a hand (graphics_menu/CLAUDE.md).
"""

from combat.paths import GAME_MODE_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu import cursor_consts as CC
from graphics_menu import umg_consts as C
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.settings_rows import BACK_ROW, PAGE_SETTINGS, PAGE_TITLE
from graphics_menu.tune_consts import GUN_TAB
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (
    MV.MenuOpen, C.GAME_STARTED_VAR, MV.MenuPage, MV.MenuRow, LOOT_OPEN_VAR,
    CC.CURSOR_ACCEPT_VAR, CC.PAUSE_CLICK_VAR, GUN_TAB.open_var, GUN_TAB.row_var)]
WRITABLE += [(GAME_MODE_BP_PATH, "PlayerDead"),
             (WEAPON_COMP_BP_PATH, CC.TRIGGER_SPENT_VAR)]


def _draw(hud):
    hud.call_method("ReceiveDrawHUD", (1920, 1080))


def _up(widget):
    return "COLLAPSED" not in str(widget.get_visibility()).upper()


def _cursor(p, hud):
    pc = p.controller()
    return bool(pc.get_editor_property("show_mouse_cursor")), p.get(hud, CC.CURSOR_SHOWN_VAR)


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield 0.3
    hud, mode = p.hud(), p.game_mode()
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)

    # --- playing: no cursor; the M panel: a cursor, and no shot from a click ----
    # (From a known state: a probe run earlier in the same game may have left
    # the player dead or a menu up.)
    p.set(mode, "PlayerDead", False)
    p.set(hud, C.GAME_STARTED_VAR, True)
    p.set(hud, "MenuOpen", False)
    _draw(hud)
    p.check("in play the cursor is hidden", _cursor(p, hud) == (False, False),
            str(_cursor(p, hud)))
    p.set(hud, "MenuOpen", True)
    _draw(hud)
    p.check("the M panel shows the cursor", _cursor(p, hud) == (True, True),
            str(_cursor(p, hud)))
    p.check("...and holds the weapon's fire press spent, so a click is not a shot",
            p.get(wc, CC.TRIGGER_SPENT_VAR) is True, str(p.get(wc, CC.TRIGGER_SPENT_VAR)))
    # Something else takes the cursor off the controller, as the window's
    # launch capture takes the mouse: in play the mode is given on a change only.
    p.controller().set_editor_property("show_mouse_cursor", False)
    _draw(hud)
    p.check("...and gives the cursor's mode on a change only: taken away behind "
            "its back, it stays away", _cursor(p, hud) == (False, True), str(_cursor(p, hud)))
    p.controller().set_editor_property("show_mouse_cursor", True)

    yield 0.1
    p.check("...and the open panel holds the player still: the controller ignores "
            "move input, so the arrows only work the menu",
            p.controller().is_move_input_ignored())

    # --- a row taken (a click, or Enter on the caret's row) is served by Tick ---
    # The debug row: taken twice, so the saved setting ends as it began.
    debug_row = C.PAUSE_ROW_ACTIONS.index(C.DEBUG_ACTION)
    before = p.get(mode, "DebugMode")
    p.set(hud, CC.PAUSE_CLICK_VAR, debug_row)
    yield lambda: p.get(mode, "DebugMode") != before
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    flipped = p.get(mode, "DebugMode")
    p.set(hud, CC.PAUSE_CLICK_VAR, debug_row)
    yield lambda: p.get(mode, "DebugMode") == before
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("taking the debug row toggles debug mode, and again toggles it back",
            flipped != before and p.get(mode, "DebugMode") == before,
            f"{before} -> {flipped} -> {p.get(mode, 'DebugMode')}")

    ui = p.get(hud, "UiPause")
    own, tab = (ui.get_editor_property(n) for n in (C.PAUSE_PANEL, GUN_TAB.panel))
    p.check("with no tab open the panel shows its own rows",
            _up(own) and not _up(tab), f"{own.get_visibility()}, {tab.get_visibility()}")
    tab_row = C.PAUSE_ROW_ACTIONS.index(GUN_TAB.action)
    p.set(hud, GUN_TAB.row_var, 3)
    p.set(hud, CC.PAUSE_CLICK_VAR, tab_row)
    yield lambda: p.get(hud, GUN_TAB.open_var)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("taking the gun tuning row opens its tab, the caret on its first row",
            p.get(hud, GUN_TAB.open_var) and p.get(hud, GUN_TAB.row_var) == 0,
            f"row {p.get(hud, GUN_TAB.row_var)}")
    _draw(hud)
    back = ui.get_editor_property(GUN_TAB.back_widget)
    p.check("the open tab stands in place of the panel's rows: one menu on screen",
            _up(tab) and not _up(own), f"{own.get_visibility()}, {tab.get_visibility()}")
    p.check("...its BACK row unlit while the caret is in the list",
            back.get_editor_property(C.ROW_CARET).get_render_opacity() == 0.0)
    p.set(hud, GUN_TAB.row_var, GUN_TAB.back_row)
    _draw(hud)
    p.check("...and lit with the caret on it",
            back.get_editor_property(C.ROW_CARET).get_render_opacity() == 1.0)
    # BACK itself is Enter or a click, which a probe has neither of: what it
    # does is lower the tab's open flag.
    p.set(hud, GUN_TAB.open_var, False)
    _draw(hud)
    p.check("back from the tab, the panel's own rows return",
            _up(own) and not _up(tab), f"{own.get_visibility()}, {tab.get_visibility()}")
    p.set(hud, CC.PAUSE_CLICK_VAR, tab_row)
    _draw(hud)
    p.check("the next frame lowers a taken row, so it is served once",
            p.get(hud, CC.PAUSE_CLICK_VAR) == CC.NO_ROW, str(p.get(hud, CC.PAUSE_CLICK_VAR)))

    # The close button is the first row, resume in play: Tick shuts the menu,
    # as M does.
    p.set(hud, CC.PAUSE_CLICK_VAR, C.PAUSE_ROW_ACTIONS.index(C.START_ACTION))
    yield lambda: not p.get(hud, "MenuOpen")
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("a click on the resume row shuts the menu",
            p.get(hud, "MenuOpen") is False and p.get(hud, C.GAME_STARTED_VAR) is True)
    yield 0.1
    p.check("...and it stays shut once the click is lowered",
            p.get(hud, "MenuOpen") is False)
    _draw(hud)
    p.check("closing the panel hides the cursor", _cursor(p, hud) == (False, False),
            str(_cursor(p, hud)))
    yield 0.2
    p.check("...and frees the fire press", p.get(wc, CC.TRIGGER_SPENT_VAR) is False,
            str(p.get(wc, CC.TRIGGER_SPENT_VAR)))
    p.check("...and gives the walk back", not p.controller().is_move_input_ignored())

    # --- the loot window (Tick shuts it again: no body here) --------------------
    p.set(hud, LOOT_OPEN_VAR, True)
    _draw(hud)
    p.check("the loot window shows the cursor", _cursor(p, hud) == (True, True),
            str(_cursor(p, hud)))
    yield lambda: not p.get(hud, LOOT_OPEN_VAR)
    _draw(hud)
    p.check("...and hides it when the window shuts", _cursor(p, hud) == (False, False),
            str(_cursor(p, hud)))

    # --- the death screen -------------------------------------------------------
    p.set(mode, "PlayerDead", True)
    _draw(hud)
    p.check("the death menu shows the cursor", _cursor(p, hud) == (True, True),
            str(_cursor(p, hud)))
    p.set(mode, "PlayerDead", False)
    _draw(hud)

    # --- the title: the same menu, held open; its settings page's clicks ---------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuPage", PAGE_TITLE)
    _draw(hud)
    p.check("the title holds the menu open and shows the cursor",
            p.get(hud, "MenuOpen") is True and _cursor(p, hud) == (True, True)
            and p.get(hud, "MenuPage") == PAGE_TITLE,
            f"open {p.get(hud, 'MenuOpen')}, {_cursor(p, hud)}")
    p.controller().set_editor_property("show_mouse_cursor", False)
    _draw(hud)
    p.check("...and gives the cursor's mode again every frame: taken away behind "
            "its back (a launched game's window takes the mouse), it is back",
            _cursor(p, hud) == (True, True), str(_cursor(p, hud)))
    p.set(hud, CC.PAUSE_CLICK_VAR, C.PAUSE_ROW_ACTIONS.index(C.SETTINGS_ACTION))
    yield lambda: p.get(hud, "MenuPage") == PAGE_SETTINGS
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("the settings row taken opens the settings page, caret on its top row",
            p.get(hud, "MenuPage") == PAGE_SETTINGS and p.get(hud, "MenuRow") == 0,
            f"page {p.get(hud, 'MenuPage')}, row {p.get(hud, 'MenuRow')}")
    p.set(hud, "MenuRow", BACK_ROW)
    p.set(hud, CC.CURSOR_ACCEPT_VAR, True)
    _draw(hud)
    p.check("a click on BACK returns to the menu's rows, and is spent",
            p.get(hud, "MenuPage") == PAGE_TITLE
            and p.get(hud, CC.CURSOR_ACCEPT_VAR) is False,
            f"page {p.get(hud, 'MenuPage')}")
    p.set(hud, CC.PAUSE_CLICK_VAR, C.PAUSE_ROW_ACTIONS.index(C.START_ACTION))
    yield lambda: p.get(hud, C.GAME_STARTED_VAR)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("the new game row taken starts the game and shuts the menu",
            p.get(hud, C.GAME_STARTED_VAR) is True and p.get(hud, "MenuOpen") is False)
    _draw(hud)
    p.check("...and play hides the cursor again", _cursor(p, hud) == (False, False),
            str(_cursor(p, hud)))
