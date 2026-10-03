"""The HUD's inventory: the hand slot and the four weapon slots under it,
bottom centre, always shown; the worn garments and the backpack, bottom
right, the garments always and the backpack while I is open. WBP_HUD's
widget names, the HUD's drag variables and the words. Constants only:
wbp_hud (the layout), hud_inventory (the slots' draw) and inv_drag (the
mouse) read one table. The slot codes are combat/slot_tuning.py's.

    in the I panel (WearOpen):
        Up/Down          the caret over the worn rows, then the bag's slots
        Enter            a worn row: take it off; a bag slot: bring it to hand
        drag a slot onto another   move it there (a swap where both fit)
        click a slot     bring it to hand (a bag or a weapon slot)
"""

from combat.slot_tuning import BAG_FIRST, BAG_SIZE, HAND, PRIMARY, WEAPON_SLOT_NAMES
from graphics_menu.wear_consts import WEAR_ROWS

# WBP_HUD's widgets: three grids of WBP_InventorySlot, and their labels.
HAND_BOX = "HandSlot"
WEAPON_BOX = "WeaponSlots"
BAG_BOX = "BagSlots"
WEAPON_LABELS = "WeaponLabels"
BAG_LABELS = "BagLabels"
BAG_PANEL = "BagPanel"              # the bag's labels and grid: shown with I
KIT = "Kit"                         # bottom right: the worn panel over the bag
BAG_COLUMNS = 5
# (grid, the slot code of its first cell, its cells), in code order.
SLOT_BOXES = ((HAND_BOX, HAND, 1), (WEAPON_BOX, PRIMARY, len(WEAPON_SLOT_NAMES)),
              (BAG_BOX, BAG_FIRST, BAG_SIZE))

WEAPON_LABEL_TEXTS = tuple(f"{i + 1}  {name}" for i, name in enumerate(WEAPON_SLOT_NAMES))
BAG_LABEL_TEXTS = tuple(str(k) for k in range(5, 10))     # over the bag's top row
INV_LABEL_FONT = 10.0
HAND_GAP = 6.0                      # px between the hand slot and the weapon row
KIT_BOTTOM = 44.0                   # the kit's bottom edge, over the watermark
KIT_SCALE = 0.75                    # the worn panel, shrunk to sit over the bag

# The HUD's variables. InvDragFrom: the slot a press in the I panel started a
# drag on (NO_SLOT when none). InvOver: the slot under the cursor this frame.
DRAG_FROM_VAR = "InvDragFrom"
INV_OVER_VAR = "InvOver"
NO_SLOT = -1
# WearSel runs over the worn rows, then the bag: the caret's index of the
# bag's first slot.
BAG_SEL_FIRST = WEAR_ROWS
SEL_ROWS = WEAR_ROWS + BAG_SIZE
# WearSel - this = the bag slot's code.
SEL_TO_CODE = BAG_SEL_FIRST - BAG_FIRST
