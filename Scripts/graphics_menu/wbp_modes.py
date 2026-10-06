"""WBP_PauseMenu's two mode pages (mode_consts.py): Single Player and
Multiplayer, each a panel where the menu's own is (PAUSE_POS), one of them
open at a time in the rows' place.

    the page's title
    BACK                 a row of its own over the list: the page's top row
    the page's rows      WBP_MenuRows, labelled here; the HUD writes the
                         Single Player row's words and the address
    the status line      Multiplayer only: connecting, or why a join failed
    the keys' hint

Start collapsed; mode_draw.py shows the one MenuPage names.
"""

import unreal

from uebp.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.mode_consts import MULTI, MULTI_HINT, MULTI_STATUS, PAGES
from graphics_menu.settings_rows import BACK_LABEL
from graphics_menu.umg_consts import (
    COL_CARET, COL_HINT, COL_ROW, COL_TITLE, PAUSE_HINT, PAUSE_HINT_FONT, PAUSE_POS,
    PAUSE_ROW_LABEL_W, PAUSE_TITLE_FONT, PAUSE_W, ROW_COLOR_VAR, ROW_GAP, ROW_TEXT_VAR,
    ROW_WIDTH_VAR, WBP_MENU_ROW,
)


def _row(bp, parent, name, label, variable=False):
    row = U.add(bp, BEL.generated_class(_must_load(WBP_MENU_ROW)), name, parent,
                variable=variable)
    row.set_editor_property(ROW_TEXT_VAR, label)
    row.set_editor_property(ROW_WIDTH_VAR, float(PAUSE_ROW_LABEL_W))
    row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
    U.pad(row, bottom=ROW_GAP)
    return row


def _author_page(bp, root, page):
    outer, stack = U.panel(bp, root, page.panel, "T_UI_Panel", min_w=PAUSE_W, variable=True)
    U.at(outer, (0.0, 0.0), (0.0, 0.0), PAUSE_POS)
    title = U.text(bp, stack, f"{page.panel}Title", page.title, PAUSE_TITLE_FONT, COL_TITLE,
                   bold=True)
    U.pad(title, bottom=18.0)
    _row(bp, stack, page.back, BACK_LABEL, variable=True)
    rows = U.add(bp, unreal.VerticalBox, page.rows_box, stack, variable=True)
    for i, label in enumerate(page.labels):
        _row(bp, rows, f"{page.rows_box}{i}", label)
    if page is MULTI:
        status = U.text(bp, stack, MULTI_STATUS, "", PAUSE_HINT_FONT, COL_CARET, variable=True)
        U.pad(status, top=2.0, bottom=6.0)
    hint = U.text(bp, stack, f"{page.panel}Hint", MULTI_HINT if page is MULTI else PAUSE_HINT,
                  PAUSE_HINT_FONT, COL_HINT)
    U.pad(hint, top=6.0)
    U.hide(outer)


def author_mode_pages(bp, root):
    for page in PAGES:
        _author_page(bp, root, page)
