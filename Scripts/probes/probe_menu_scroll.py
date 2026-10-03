"""A scrolling tab's scroll bar, dragged (graphics_menu/tune_scroll.py), and
the wheel, which no menu reads.

A -nullrhi run has no mouse and lays out no widget, so the probe raises what
a press on the bar would (ScrollGrab, with ScrollAt for where the cursor is)
and calls the HUD's ReceiveDrawHUD itself, as probe_menu_cursor does. No
button is down, so the drag is served for that one frame and let go. The
press itself, and the bar under a real cursor, need a window and a hand
(graphics_menu/CLAUDE.md).
"""

from graphics_menu import cursor_consts as CC
from graphics_menu import hud_vars as MV
from graphics_menu import umg_consts as C
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.tune_consts import TUNE_ROW_H
from graphics_menu.tune_scroll import hidden_rows, top_row

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TABS = (GFX_TAB, MONSTER_TAB)
WRITABLE = [(HUD_BP_PATH, v) for v in (
    MV.MenuOpen, C.GAME_STARTED_VAR, CC.SCROLL_GRAB_VAR, CC.SCROLL_AT_VAR,
    *(v for t in TABS for v in (t.open_var, t.row_var)))]


def _draw(hud):
    hud.call_method("ReceiveDrawHUD", (1920, 1080))


def _drag(p, hud, at):
    p.set(hud, CC.SCROLL_AT_VAR, at)
    p.set(hud, CC.SCROLL_GRAB_VAR, True)
    _draw(hud)


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield 0.3
    hud = p.hud()
    p.set(hud, C.GAME_STARTED_VAR, True)
    p.set(hud, "MenuOpen", True)
    for tab in TABS:
        rows = p.get(hud, "UiPause").get_editor_property(tab.rows_box)
        last = hidden_rows(tab)
        p.set(hud, tab.open_var, True)
        p.set(hud, tab.row_var, 0)
        _draw(hud)
        p.check(f"{tab.panel}: opened, its list is at the top and nothing is dragged",
                rows.get_scroll_offset() == 0.0 and not p.get(hud, CC.SCROLL_GRAB_VAR),
                f"offset {rows.get_scroll_offset():.1f}")

        _drag(p, hud, 1.0)
        offset, caret = rows.get_scroll_offset(), p.get(hud, tab.row_var)
        p.check(f"{tab.panel}: the bar dragged to the bottom scrolls the list to its "
                f"end ({last} rows) and brings the caret into the window",
                abs(offset - last * TUNE_ROW_H) < 1e-3 and caret == last,
                f"offset {offset:.1f} (a row is {TUNE_ROW_H}), caret {caret}")
        p.check(f"{tab.panel}: with no button down the bar is let go",
                not p.get(hud, CC.SCROLL_GRAB_VAR))
        _draw(hud)
        yield 0.2
        p.check(f"{tab.panel}: let go, the list stays where it was dragged to",
                abs(rows.get_scroll_offset() - offset) < 1e-3
                and p.get(hud, tab.row_var) == caret,
                f"offset {rows.get_scroll_offset():.1f}, caret {p.get(hud, tab.row_var)}")

        _drag(p, hud, 0.5)
        mid = top_row(tab, 0.5)
        p.check(f"{tab.panel}: dragged to the middle, row {mid} is first, and the caret "
                "(below the window) is its last row",
                abs(rows.get_scroll_offset() - mid * TUNE_ROW_H) < 1e-3
                and 0 < mid < last
                and p.get(hud, tab.row_var) == min(last, mid + tab.visible_rows - 1),
                f"offset {rows.get_scroll_offset():.1f}, caret {p.get(hud, tab.row_var)}")

        p.set(hud, tab.row_var, tab.back_row)
        _drag(p, hud, 0.0)
        p.check(f"{tab.panel}: dragged to the top from BACK, the list is at its start "
                "and the caret on the window's last row",
                rows.get_scroll_offset() == 0.0
                and p.get(hud, tab.row_var) == tab.visible_rows - 1,
                f"offset {rows.get_scroll_offset():.1f}, caret {p.get(hud, tab.row_var)}")
        p.set(hud, tab.open_var, False)
        _draw(hud)
    p.set(hud, "MenuOpen", False)
    _draw(hud)
