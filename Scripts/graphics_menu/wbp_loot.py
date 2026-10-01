"""WBP_HUD's loot window and its prompt (see loot_consts for the keys).

  centre, under the reticle   LootPrompt "[TAB] search the body", while a body
                              is in reach and the window is shut
  right edge, centred         LootPanel: a title, LOOT_ROWS WBP_MenuRows (the
                              caret and the item's icon; rows past the body's
                              contents collapsed), NOTHING on a body that
                              carries nothing, BAG FULL while the bag has no
                              room, the keys' hint, and LootClose "[TAB]
                              close", the button a click shuts the window by

Both start collapsed; loot_draw.py shows them and writes the rows each frame.
"""

import unreal

from combat.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.loot_consts import (
    LOOT_CLOSE, LOOT_CLOSE_TEXT, LOOT_EMPTY, LOOT_EMPTY_TEXT, LOOT_FULL, LOOT_FULL_TEXT, LOOT_HINT_FONT,
    LOOT_HINT_TEXT, LOOT_PANEL,
    LOOT_PANEL_W, LOOT_PROMPT, LOOT_PROMPT_FONT, LOOT_PROMPT_TEXT, LOOT_PROMPT_Y,
    LOOT_RIGHT, LOOT_ROWS, LOOT_ROWS_BOX, LOOT_TITLE_FONT, LOOT_TITLE_TEXT,
)
from graphics_menu.umg_consts import (
    COL_DEBUFF, COL_GOLD, COL_HINT, COL_ROW, COL_TITLE, ROW_COLOR_VAR, ROW_FONT,
    ROW_GAP, ROW_TEXT_VAR, ROW_WIDTH_VAR, WBP_MENU_ROW,
)


def author_loot_widgets(bp, body):
    prompt = U.text(bp, body, LOOT_PROMPT, LOOT_PROMPT_TEXT, LOOT_PROMPT_FONT, COL_GOLD,
                    variable=True)
    U.at(prompt, (0.5, 0.5), (0.5, 0.0), (0.0, LOOT_PROMPT_Y))
    U.hide(prompt)

    outer, stack = U.panel(bp, body, LOOT_PANEL, "T_UI_Panel", min_w=LOOT_PANEL_W,
                           variable=True)
    U.at(outer, (1.0, 0.5), (1.0, 0.5), (-LOOT_RIGHT, 0.0))
    title = U.text(bp, stack, "LootTitle", LOOT_TITLE_TEXT, LOOT_TITLE_FONT, COL_TITLE,
                   bold=True)
    U.pad(title, bottom=14.0)
    rows = U.add(bp, unreal.VerticalBox, LOOT_ROWS_BOX, stack, variable=True)
    row_class = BEL.generated_class(_must_load(WBP_MENU_ROW))
    for i in range(LOOT_ROWS):
        row = U.add(bp, row_class, f"{LOOT_ROWS_BOX}{i}", rows)
        # No label and no value: the item's icon, beside the caret.
        row.set_editor_property(ROW_TEXT_VAR, "")
        row.set_editor_property(ROW_WIDTH_VAR, 0.0)
        row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
        U.pad(row, bottom=ROW_GAP)
    empty = U.text(bp, stack, LOOT_EMPTY, LOOT_EMPTY_TEXT, ROW_FONT, COL_HINT,
                   variable=True)
    U.pad(empty, bottom=ROW_GAP)
    U.hide(empty)
    full = U.text(bp, stack, LOOT_FULL, LOOT_FULL_TEXT, LOOT_HINT_FONT, COL_DEBUFF,
                  variable=True)
    U.pad(full, top=2.0)
    U.hide(full)
    hint = U.text(bp, stack, "LootHint", LOOT_HINT_TEXT, LOOT_HINT_FONT, COL_HINT)
    U.pad(hint, top=6.0)
    # The close button. A variable: the HUD tests the cursor against it.
    close = U.text(bp, stack, LOOT_CLOSE, LOOT_CLOSE_TEXT, ROW_FONT, COL_ROW,
                   variable=True)
    U.pad(close, top=8.0)
    U.hide(outer)
