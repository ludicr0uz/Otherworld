"""The mouse cursor in the menus: it shows while a menu is up and hides for
play, a click on a menu row is not a shot, and what a click raises is served
as the row's key.

A -nullrhi run lays out no widget and has no mouse, so nothing is ever under
the cursor here: the probe raises what a click would (CursorAccept,
PauseClick) and calls the HUD's ReceiveDrawHUD itself, as probe_umg_screens
does. Which row the cursor is over, and the click and the wheel themselves,
need a window and a hand (graphics_menu/CLAUDE.md).
"""

from combat.paths import GAME_MODE_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu import cursor_consts as CC
from graphics_menu import umg_consts as C
from graphics_menu.loot_consts import LOOT_OPEN_VAR
from graphics_menu.presets import DEFAULT_PRESET, PRESET_KEYS
from graphics_menu.settings_rows import BACK_ROW, PAGE_SETTINGS, PAGE_TITLE
from graphics_menu.tune_consts import GUN_TAB

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (
    "MenuOpen", C.GAME_STARTED_VAR, "MenuPage", "MenuRow", LOOT_OPEN_VAR,
    CC.CURSOR_ACCEPT_VAR, CC.PAUSE_CLICK_VAR)]
WRITABLE += [(GAME_MODE_BP_PATH, "PlayerDead"),
             (WEAPON_COMP_BP_PATH, CC.TRIGGER_SPENT_VAR)]


def _draw(hud):
    hud.call_method("ReceiveDrawHUD", (1920, 1080))


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

    # --- a click on an M panel row is the row's key, served by Tick -------------
    want = (DEFAULT_PRESET + 2) % len(PRESET_KEYS)
    before = p.get(hud, "Quality")
    p.set(hud, CC.PAUSE_CLICK_VAR, want)
    yield lambda: p.get(hud, "Quality") == want
    p.check(f"a click on preset row {want} picks that preset",
            p.get(hud, "Quality") == want, f"{before} -> {p.get(hud, 'Quality')}")
    tab_row = C.PAUSE_ROW_KEYS.index(GUN_TAB.key)
    p.set(hud, CC.PAUSE_CLICK_VAR, tab_row)
    yield lambda: p.get(hud, GUN_TAB.open_var)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("a click on the gun tuning row opens its tab", p.get(hud, GUN_TAB.open_var))
    p.set(hud, CC.PAUSE_CLICK_VAR, want)
    _draw(hud)
    p.check("the next frame lowers the click, so it is served once",
            p.get(hud, CC.PAUSE_CLICK_VAR) == CC.NO_ROW, str(p.get(hud, CC.PAUSE_CLICK_VAR)))

    # The close button is the last row, and its key is M: Tick shuts the panel.
    p.set(hud, CC.PAUSE_CLICK_VAR, C.PAUSE_ROW_KEYS.index(C.MENU_KEY))
    yield lambda: not p.get(hud, "MenuOpen")
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    p.check("a click on the close row shuts the panel", p.get(hud, "MenuOpen") is False)
    yield 0.1
    p.check("...and it stays shut once the click is lowered",
            p.get(hud, "MenuOpen") is False)
    _draw(hud)
    p.check("closing the panel hides the cursor", _cursor(p, hud) == (False, False),
            str(_cursor(p, hud)))
    yield 0.2
    p.check("...and frees the fire press", p.get(wc, CC.TRIGGER_SPENT_VAR) is False,
            str(p.get(wc, CC.TRIGGER_SPENT_VAR)))

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

    # --- the title and settings pages: a click is the caret row's Enter ---------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuPage", PAGE_TITLE)
    p.set(hud, "MenuRow", 1)
    _draw(hud)
    p.check("the title page shows the cursor, and nothing is accepted unasked",
            _cursor(p, hud) == (True, True) and p.get(hud, "MenuPage") == PAGE_TITLE,
            f"{_cursor(p, hud)}, page {p.get(hud, 'MenuPage')}")
    p.set(hud, CC.CURSOR_ACCEPT_VAR, True)
    _draw(hud)
    p.check("a click on SETTINGS opens the settings page, and is spent",
            p.get(hud, "MenuPage") == PAGE_SETTINGS
            and p.get(hud, CC.CURSOR_ACCEPT_VAR) is False,
            f"page {p.get(hud, 'MenuPage')}, accept {p.get(hud, CC.CURSOR_ACCEPT_VAR)}")
    p.set(hud, "MenuRow", BACK_ROW)
    p.set(hud, CC.CURSOR_ACCEPT_VAR, True)
    _draw(hud)
    p.check("a click on BACK returns to the title page",
            p.get(hud, "MenuPage") == PAGE_TITLE
            and p.get(hud, CC.CURSOR_ACCEPT_VAR) is False,
            f"page {p.get(hud, 'MenuPage')}")
    p.set(hud, "MenuRow", 0)
    p.set(hud, CC.CURSOR_ACCEPT_VAR, True)
    _draw(hud)
    p.check("a click on NEW GAME starts the game", p.get(hud, C.GAME_STARTED_VAR) is True)
    _draw(hud)
    p.check("...and play hides the cursor again", _cursor(p, hud) == (False, False),
            str(_cursor(p, hud)))
