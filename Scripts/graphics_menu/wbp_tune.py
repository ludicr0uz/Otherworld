"""WBP_PauseMenu's tuning panels, one per TuneTab (tune_tab.py): GUN, MONSTER
and WORLD TUNING, in the same spot (only one is open at a time).

  right of the M panel   the tab's panel: a title, row_count WBP_MenuRows (the
                         subject, then one per stat, each labelled in
                         the designer; the HUD writes the value column and the
                         caret), "saved to ..." after a save, and the keys' hint

Starts collapsed; tune_draw.py shows it while the tab is open and writes the rows.
"""

import unreal

from combat.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.monster_tune_consts import MONSTER_TAB
from graphics_menu.tune_consts import (
    GUN_TAB, TUNE_HINT_FONT, TUNE_PANEL_W, TUNE_POS, TUNE_ROW_LABEL_W, TUNE_TITLE_FONT,
)
from graphics_menu.umg_consts import (
    COL_CARET, COL_HINT, COL_ROW, COL_TITLE, ROW_COLOR_VAR, ROW_TEXT_VAR,
    ROW_WIDTH_VAR, WBP_MENU_ROW,
)
from graphics_menu.world_tune_consts import WORLD_TAB


def author_tune_widgets(bp, root):
    for tab in (GUN_TAB, MONSTER_TAB, WORLD_TAB):
        _author_tab(bp, root, tab)


def _author_tab(bp, root, tab):
    outer, stack = U.panel(bp, root, tab.panel, "T_UI_Panel", min_w=TUNE_PANEL_W,
                           variable=True)
    U.at(outer, (0.0, 0.0), (0.0, 0.0), TUNE_POS)
    title = U.text(bp, stack, tab.title_widget, tab.title_text, TUNE_TITLE_FONT, COL_TITLE,
                   bold=True)
    U.pad(title, bottom=10.0)
    rows = U.add(bp, unreal.VerticalBox, tab.rows_box, stack, variable=True)
    row_class = BEL.generated_class(_must_load(WBP_MENU_ROW))
    for i, label in enumerate(tab.row_labels):
        row = U.add(bp, row_class, f"{tab.rows_box}{i}", rows)
        row.set_editor_property(ROW_TEXT_VAR, label)
        row.set_editor_property(ROW_WIDTH_VAR, TUNE_ROW_LABEL_W)
        row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
        # The subject row stands apart from the stats under it.
        U.pad(row, bottom=8.0 if i == 0 else 0.0)
    saved = U.text(bp, stack, tab.saved_text, tab.saved_words, TUNE_HINT_FONT,
                   COL_CARET, variable=True)
    U.pad(saved, top=6.0)
    U.hide(saved)
    # A variable: a click on the hint line saves (tune_draw.py).
    hint = U.text(bp, stack, tab.hint_widget, tab.hint_text, TUNE_HINT_FONT, COL_HINT,
                  variable=True)
    U.pad(hint, top=6.0)
    U.hide(outer)
