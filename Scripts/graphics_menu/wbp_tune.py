"""WBP_PauseMenu's GUN TUNING panel (see tune_consts for the keys).

  right of the M panel   TunePanel: a title, TUNE_ROW_COUNT WBP_MenuRows (the
                         gun, then one per TUNE_STATS entry, each labelled in
                         the designer; the HUD writes the value column and the
                         caret), "saved to ..." after a save, and the keys' hint

Starts collapsed; tune_draw.py shows it while TuneOpen and writes the rows.
"""

import unreal

from combat.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.tune_consts import (
    TUNE_HINT_FONT, TUNE_HINT_TEXT, TUNE_PANEL, TUNE_PANEL_W, TUNE_POS,
    TUNE_ROW_LABEL_W, TUNE_ROW_LABELS, TUNE_ROWS_BOX, TUNE_SAVED_TEXT,
    TUNE_SAVED_WORDS, TUNE_TITLE_FONT, TUNE_TITLE_TEXT,
)
from graphics_menu.umg_consts import (
    COL_CARET, COL_HINT, COL_ROW, COL_TITLE, ROW_COLOR_VAR, ROW_TEXT_VAR,
    ROW_WIDTH_VAR, WBP_MENU_ROW,
)


def author_tune_widgets(bp, root):
    outer, stack = U.panel(bp, root, TUNE_PANEL, "T_UI_Panel", min_w=TUNE_PANEL_W,
                           variable=True)
    U.at(outer, (0.0, 0.0), (0.0, 0.0), TUNE_POS)
    title = U.text(bp, stack, "TuneTitle", TUNE_TITLE_TEXT, TUNE_TITLE_FONT, COL_TITLE,
                   bold=True)
    U.pad(title, bottom=10.0)
    rows = U.add(bp, unreal.VerticalBox, TUNE_ROWS_BOX, stack, variable=True)
    row_class = BEL.generated_class(_must_load(WBP_MENU_ROW))
    for i, label in enumerate(TUNE_ROW_LABELS):
        row = U.add(bp, row_class, f"{TUNE_ROWS_BOX}{i}", rows)
        row.set_editor_property(ROW_TEXT_VAR, label)
        row.set_editor_property(ROW_WIDTH_VAR, TUNE_ROW_LABEL_W)
        row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
        # The gun row stands apart from the stats under it.
        U.pad(row, bottom=8.0 if i == 0 else 0.0)
    saved = U.text(bp, stack, TUNE_SAVED_TEXT, TUNE_SAVED_WORDS, TUNE_HINT_FONT,
                   COL_CARET, variable=True)
    U.pad(saved, top=6.0)
    U.hide(saved)
    hint = U.text(bp, stack, "TuneHint", TUNE_HINT_TEXT, TUNE_HINT_FONT, COL_HINT)
    U.pad(hint, top=6.0)
    U.hide(outer)
