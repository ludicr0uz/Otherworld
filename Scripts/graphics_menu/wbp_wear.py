"""WBP_HUD's I panel (see wear_consts for the keys).

  bottom right, over   WearPanel: WearSlots, one WBP_InventorySlot per worn
  the backpack         slot in two rows of four, each with its garment's
  (wbp_hud's Kit)      silhouette for when it is empty. No words: the I key
                       opens and shuts it.

  left of the Kit      WearPortrait: the character from the front, a picture
                       rendered from the player's body (item_icons/portrait.py).
                       It starts on the bare one; wear_portrait.py puts up the
                       picture of what is worn

Both start collapsed. wear_draw.py shows the panel (always, but under the
menu) and fills the slots each frame; hud_inventory.py shows the portrait
while the I panel is open.
"""

import unreal

from graphics_menu import umg_author as U
from graphics_menu.inv_consts import BAG_COLUMNS, KIT_BOTTOM
from graphics_menu.umg_consts import CORNER_MARGIN, SLOT_GAP, SLOT_W
from graphics_menu.wbp_parts import slot_grid
from graphics_menu.wear_consts import (
    WEAR_COLUMNS, WEAR_GHOSTS, WEAR_PANEL, WEAR_PORTRAIT, WEAR_PORTRAIT_GAP, WEAR_PORTRAIT_IMAGE,
    WEAR_PORTRAIT_PAD, WEAR_PORTRAIT_SIZE, WEAR_ROWS, WEAR_SLOTS_BOX,
)
from item_icons.items import icon_name
from item_icons.portrait import PORTRAIT_TEXTURE


def author_wear_widgets(bp, parent):
    """The panel, in ``parent`` (a box: wbp_hud places it). Returns it."""
    panel = U.add(bp, unreal.VerticalBox, WEAR_PANEL, parent, variable=True)
    grid = slot_grid(bp, panel, WEAR_SLOTS_BOX, WEAR_ROWS, WEAR_COLUMNS, "Worn",
                     ghosts=[icon_name(d) for d in WEAR_GHOSTS])
    U.pad(grid, h="Right")
    U.hide(panel)
    return panel


def author_wear_portrait(bp, body):
    """The portrait, on ``body`` (a canvas): bottom right, left of the kit,
    whose width is the bag's grid. Returns its outer."""
    outer, stack = U.panel(bp, body, WEAR_PORTRAIT, "T_UI_Panel", variable=True,
                           padding=(WEAR_PORTRAIT_PAD,) * 4)
    # A variable: the HUD sets its brush.
    U.image(bp, stack, WEAR_PORTRAIT_IMAGE, PORTRAIT_TEXTURE, size=WEAR_PORTRAIT_SIZE,
            variable=True)
    kit_w = BAG_COLUMNS * (SLOT_W + SLOT_GAP)
    U.at(outer, (1.0, 1.0), (1.0, 1.0),
         (-(CORNER_MARGIN + kit_w + WEAR_PORTRAIT_GAP), -KIT_BOTTOM))
    U.hide(outer)
    return outer
