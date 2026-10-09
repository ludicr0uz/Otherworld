"""The HUD's inventory: the hand slot and the four weapon slots under it,
bottom centre; the worn garments and the backpack, bottom right; all of
them always shown. An empty weapon slot shows its kind's silhouette. WBP_HUD's
widget names, the HUD's drag variables and the words. Constants only:
wbp_hud (the layout), hud_inventory (the slots' draw) and inv_drag (the
mouse) read one table. The slot codes are combat/slot_tuning.py's.

    in the I panel (WearOpen):
        Up/Down          the caret over the worn rows, then the bag's slots
        Enter            a worn row: take it off; a bag slot: bring it to hand
        drag a slot onto another   move it there (a swap where both fit)
        drag a worn garment onto the hand or a bag slot   take it off into it
        drag a carried garment onto the worn grid          wear it
        click a slot     bring it to hand (a bag or a weapon slot)
        drag anything out of the inventory (released over none of
            INV_AREAS)   set it down on the ground (the component's DropRequest)
    while a drag is on, its item's icon is carried on the cursor (DRAG_ICON)
    and the mouse does not turn the view (inv_carry.py)
"""

from uebp.vars import BOOL, INT, Var
from combat.slot_tuning import (
    BAG_FIRST, BAG_SIZE, HAND, PRIMARY, SLOT_COUNT, WEAPON_SLOT_NAMES,
)
from graphics_menu.wear_consts import WEAR_ROWS, WEAR_SLOTS_BOX

# WBP_HUD's widgets: three grids of WBP_InventorySlot, and their labels.
HAND_BOX = "HandSlot"
WEAPON_BOX = "WeaponSlots"
BAG_BOX = "BagSlots"
BAG_LABELS = "BagLabels"
BAG_PANEL = "BagPanel"              # the bag's labels and grid
KIT = "Kit"                         # bottom right: the worn panel over the bag
BAG_COLUMNS = 5
# (grid, the slot code of its first cell, its cells), in code order.
SLOT_BOXES = ((HAND_BOX, HAND, 1), (WEAPON_BOX, PRIMARY, len(WEAPON_SLOT_NAMES)),
              (BAG_BOX, BAG_FIRST, BAG_SIZE))

# The mouse's cells: the slots' three grids, then the worn grid, whose cell
# i is code WORN_CODE_FIRST + i. The HUD's own codes: the weapon component
# knows 0 .. SLOT_COUNT-1 and is asked for a worn slot by its index.
WORN_CODE_FIRST = SLOT_COUNT
DRAG_BOXES = SLOT_BOXES + ((WEAR_SLOTS_BOX, WORN_CODE_FIRST, WEAR_ROWS),)

# An empty weapon slot's silhouette: the kind of weapon (ui_art/slot_ghosts.py's
# drawn glyph, not an item's icon) that stands in it, translucent. Primary and
# secondary a rifle, then a pistol and a knife.
WEAPON_GHOSTS = ("Rifle", "Rifle", "Pistol", "Knife")
BAG_LABEL_TEXTS = tuple(str(k) for k in range(5, 10))     # over the bag's top row
INV_LABEL_FONT = 10.0
HAND_GAP = 6.0                      # px between the hand slot and the weapon row
KIT_BOTTOM = 44.0                   # the kit's bottom edge, over the watermark

# The HUD's variables. InvDragFrom: the slot a press in the I panel started a
# drag on (NO_SLOT when none). InvOver: the slot under the cursor this frame.
NO_SLOT = -1
DRAG_FROM_VAR = Var("InvDragFrom", INT, NO_SLOT)
INV_OVER_VAR = Var("InvOver", INT, NO_SLOT)
DRAG_TABLE = (DRAG_FROM_VAR, INV_OVER_VAR)       # inv_drag.py declares it
# The look input is held (a drag is on): SetIgnoreLookInput's edge memory.
LOOK_HELD_VAR = Var("InvLookHeld", BOOL, False)
CARRY_TABLE = (LOOK_HELD_VAR,)                  # inv_carry.py declares it
# The dragged item's icon, carried on the cursor: an Image on WBP_HUD's root.
DRAG_ICON = "DragIcon"
# The inventory's area: a drag released over none of these (and so over no
# slot) is a drop on the ground; over one of them but between two slots it
# is called off.
INV_AREAS = (KIT, HAND_BOX, WEAPON_BOX)
# WearSel runs over the worn rows, then the bag: the caret's index of the
# bag's first slot.
BAG_SEL_FIRST = WEAR_ROWS
SEL_ROWS = WEAR_ROWS + BAG_SIZE
# WearSel - this = the bag slot's code.
SEL_TO_CODE = BAG_SEL_FIRST - BAG_FIRST
