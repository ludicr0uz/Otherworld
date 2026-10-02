"""The mouse cursor over real rows. Needs a window:

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_menu_cursor_window.py

A row is "under the cursor" by its painted geometry, which a -nullrhi run
never has (probe_menu_cursor.py covers what a click raises there). Here the
engine draws the HUD itself, and the probe sweeps the real cursor down each
menu with SetMouseLocation and reads CursorRow and the caret back.

It moves the machine's mouse pointer for a few seconds. It cannot press a
button or turn the wheel. Python reads a widget's cached geometry back as
zeros, so the sweep finds the rows instead of aiming at them.
"""

import unreal

from graphics_menu import cursor_consts as CC
from graphics_menu import umg_consts as C
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.settings_rows import BACK_ROW, PAGE_SETTINGS, PAGE_TITLE

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in ("MenuOpen", C.GAME_STARTED_VAR, "MenuPage",
                                       "MenuRow", GFX_TAB.open_var, GFX_TAB.row_var)]
STEP_PX = 6          # under the thinnest row at any window this is run in
STEP_S = 0.04


def _sweep(p, hud, x_fraction, seen, caret_var=None, carets=None):
    """Walk the cursor down the viewport at ``x_fraction`` of its width,
    appending each new CursorRow to ``seen`` (and, asked, each new value of
    the menu's caret ``caret_var`` to ``carets``)."""
    size = unreal.WidgetLayoutLibrary.get_viewport_size(p.world())
    pc = p.controller()
    for y in range(STEP_PX, int(size.y) - STEP_PX, STEP_PX):
        pc.set_mouse_location(int(size.x * x_fraction), y)
        yield STEP_S
        row = p.get(hud, CC.CURSOR_ROW_VAR)
        if row != CC.NO_ROW and (not seen or seen[-1] != row):
            seen.append(row)
        if caret_var is not None:
            caret = p.get(hud, caret_var)
            if not carets or carets[-1] != caret:
                carets.append(caret)


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    if "-nullrhi" in str(unreal.SystemLibrary.get_command_line()).lower():
        p.check("this probe has a window to draw the menus in (run with --windowed)",
                False, "-nullrhi")
        return
    yield 0.5
    hud, pc = p.hud(), p.controller()

    # --- the M panel: every row is found, in order, and lights its caret ---------
    p.set(hud, "MenuOpen", True)
    yield 0.5
    p.check("the M panel shows the cursor", bool(pc.get_editor_property("show_mouse_cursor")))
    seen = []
    # The panel hangs off the top-left corner (PAUSE_POS, PAUSE_W wide).
    yield from _sweep(p, hud, 0.12, seen)
    p.check("sweeping down the M panel puts the cursor on each row in turn",
            seen == list(range(len(C.PAUSE_ROW_LABELS))), str(seen))
    p.check("...and the panel's caret went with it, down to its last row",
            p.get(hud, C.PAUSE_ROW_VAR) == len(C.PAUSE_ROW_LABELS) - 1,
            str(p.get(hud, C.PAUSE_ROW_VAR)))

    # --- the graphics tab: bottom right, a window of rows over a scrolling list ----
    tab = GFX_TAB
    rows = p.get(hud, "UiPause").get_editor_property(tab.rows_box)
    p.set(hud, tab.open_var, True)
    p.set(hud, tab.row_var, 0)
    yield 0.5
    seen, carets = [], []
    yield from _sweep(p, hud, 0.82, seen, tab.row_var, carets)
    p.check(f"sweeping down the graphics tab finds its first {tab.visible_rows} rows "
            "and no more (the rest are scrolled out of its window), then SAVE DEFAULT "
            "and then BACK take the caret",
            seen == list(range(tab.visible_rows))
            and carets[-2:] == [tab.save_row, tab.back_row],
            f"{seen}, carets {carets} (SAVE DEFAULT is {tab.save_row}, BACK "
            f"{tab.back_row})")
    pc.set_mouse_location(8, 8)
    p.set(hud, tab.row_var, tab.stat_count)
    yield 0.5
    offset = rows.get_scroll_offset()
    seen = []
    yield from _sweep(p, hud, 0.82, seen)
    p.check("with the caret on the last row the list has scrolled to its end, and "
            f"the sweep finds the last {tab.visible_rows} rows",
            offset > 0.0 and seen == list(range(tab.row_count - tab.visible_rows,
                                                tab.row_count)),
            f"offset {offset:.1f}, {seen}")
    p.set(hud, tab.open_var, False)
    p.set(hud, "MenuOpen", False)
    yield 0.3
    p.check("closing the panel hides the cursor",
            not pc.get_editor_property("show_mouse_cursor"))

    # --- the title page: the caret follows the cursor -----------------------------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuPage", PAGE_TITLE)
    p.set(hud, "MenuRow", 0)
    yield 0.5
    seen = []
    yield from _sweep(p, hud, 0.5, seen)
    p.check("sweeping down the title page finds NEW GAME, then SETTINGS",
            seen == list(range(len(C.MENU_ROWS))), str(seen))
    p.check("...and the caret went with it", p.get(hud, "MenuRow") == len(C.MENU_ROWS) - 1,
            str(p.get(hud, "MenuRow")))
    yield 0.3
    p.check("...and stays once the cursor has moved off the rows",
            p.get(hud, "MenuRow") == len(C.MENU_ROWS) - 1, str(p.get(hud, "MenuRow")))

    # --- the settings page ----------------------------------------------------------
    p.set(hud, "MenuPage", PAGE_SETTINGS)
    p.set(hud, "MenuRow", 0)
    yield 0.5
    seen = []
    yield from _sweep(p, hud, 0.5, seen)
    p.check("sweeping down the settings page finds every row down to BACK",
            seen == list(range(BACK_ROW + 1)) and p.get(hud, "MenuRow") == BACK_ROW,
            f"{seen}, caret {p.get(hud, 'MenuRow')}")
    p.set(hud, "MenuPage", PAGE_TITLE)
    p.set(hud, C.GAME_STARTED_VAR, True)
    yield 0.3
    p.check("back in play the cursor is hidden",
            not pc.get_editor_property("show_mouse_cursor"))
