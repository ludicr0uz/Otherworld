"""WBP_HUD's I panel (see wear_consts for the keys).

  bottom right, over   WearPanel: a title, one WBP_MenuRow per slot (its label
  the backpack         the slot's name, its value what is worn there), the
  (wbp_hud's Kit)      keys' hint, and WearClose "[I] inventory", the line a
                       click shuts the I panel by

  left of the Kit      WearPortrait: the character from the front, a picture
                       rendered from the player's body (item_icons/portrait.py)

Both start collapsed. wear_draw.py shows the panel (always, but under the
menu) and writes the values each frame; hud_inventory.py shows the portrait
with the bag, while the I panel is open.
"""

import unreal

from combat.graph import BEL, _must_load
from graphics_menu import umg_author as U
from graphics_menu.inv_consts import BAG_COLUMNS, KIT_BOTTOM
from graphics_menu.umg_consts import (
    COL_HINT, COL_ROW, COL_TITLE, CORNER_MARGIN, ROW_COLOR_VAR, ROW_FONT, ROW_TEXT_VAR,
    ROW_WIDTH_VAR, SLOT_GAP, SLOT_W, WBP_MENU_ROW,
)
from graphics_menu.wear_consts import (
    WEAR_CLOSE, WEAR_CLOSE_TEXT, WEAR_HINT_FONT, WEAR_HINT_TEXT, WEAR_LABEL_W, WEAR_LABELS,
    WEAR_PANEL, WEAR_PANEL_W, WEAR_PORTRAIT, WEAR_PORTRAIT_GAP, WEAR_PORTRAIT_IMAGE,
    WEAR_PORTRAIT_PAD, WEAR_PORTRAIT_SIZE, WEAR_ROW_GAP, WEAR_ROWS_BOX, WEAR_TITLE_FONT,
    WEAR_TITLE_TEXT,
)
from item_icons.portrait import PORTRAIT_TEXTURE


def author_wear_widgets(bp, parent):
    """The panel, in ``parent`` (a box: wbp_hud places it). Returns its outer."""
    outer, stack = U.panel(bp, parent, WEAR_PANEL, "T_UI_Panel", min_w=WEAR_PANEL_W,
                           variable=True)
    title = U.text(bp, stack, "WearTitle", WEAR_TITLE_TEXT, WEAR_TITLE_FONT, COL_TITLE,
                   bold=True)
    U.pad(title, bottom=14.0)
    rows = U.add(bp, unreal.VerticalBox, WEAR_ROWS_BOX, stack, variable=True)
    row_class = BEL.generated_class(_must_load(WBP_MENU_ROW))
    for i, label in enumerate(WEAR_LABELS):
        row = U.add(bp, row_class, f"{WEAR_ROWS_BOX}{i}", rows)
        row.set_editor_property(ROW_TEXT_VAR, label)
        row.set_editor_property(ROW_WIDTH_VAR, WEAR_LABEL_W)
        row.set_editor_property(ROW_COLOR_VAR, U.slate_colour(COL_ROW))
        U.pad(row, bottom=WEAR_ROW_GAP)
    hint = U.text(bp, stack, "WearHint", WEAR_HINT_TEXT, WEAR_HINT_FONT, COL_HINT)
    U.pad(hint, top=6.0)
    # The close button. A variable: the HUD tests the cursor against it.
    close = U.text(bp, stack, WEAR_CLOSE, WEAR_CLOSE_TEXT, ROW_FONT, COL_ROW,
                   variable=True)
    U.pad(close, top=8.0)
    U.hide(outer)
    return outer


def author_wear_portrait(bp, body):
    """The portrait, on ``body`` (a canvas): bottom right, left of the kit,
    whose width is the bag's grid. Returns its outer."""
    outer, stack = U.panel(bp, body, WEAR_PORTRAIT, "T_UI_Panel", variable=True,
                           padding=(WEAR_PORTRAIT_PAD,) * 4)
    U.image(bp, stack, WEAR_PORTRAIT_IMAGE, PORTRAIT_TEXTURE, size=WEAR_PORTRAIT_SIZE)
    kit_w = BAG_COLUMNS * (SLOT_W + SLOT_GAP)
    U.at(outer, (1.0, 1.0), (1.0, 1.0),
         (-(CORNER_MARGIN + kit_w + WEAR_PORTRAIT_GAP), -KIT_BOTTOM))
    U.hide(outer)
    return outer
