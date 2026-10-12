"""The I panel: what the player wears, and the backpack under it. Its key,
the HUD's variables, WBP_HUD's widget names and words. Constants only, so
wbp_wear (the layout), wear_tick and wear_draw (the graph) and wear_checks
read one table. The worn slots and the backpack are always shown (bottom
right): one inventory slot per garment, its icon in it, or the garment's
silhouette while nothing is worn there. I opens the panel: the keys and the
mouse work it (inv_consts.py has the backpack's half).

    [I]                 open the panel (I again closes it); the walk is
                        held while it is open, as under the menu
    Up / Down           move the caret over the worn slots, then the bag
    Enter, or a click   a worn slot: take that garment off, into the bag
    drag                a worn garment onto the hand or a bag slot takes it
                        off into it; a carried one onto the worn grid wears it

While it is open the character's portrait stands left of it: the picture of
the player in what they wear (wear_portrait.py picks it).

A fixed key, like Tab: not a gameplay bind. Up/Down/Enter are the menu's
navigation keys; with the loot window open they are the loot window's, and
with the menu open the menu's.
"""

from combat.wear_tuning import WEAR_SLOTS
from graphics_menu.umg_consts import UI_ART_DIR
from item_icons.portrait import PORTRAITS
from uebp.vars import BOOL, INT, Var, array, lazy, obj

WEAR_KEY = "I"
WEAR_UP, WEAR_DOWN = "Up", "Down"       # menu_nav.NAV_UP / NAV_DOWN
WEAR_TAKE_KEY = "Enter"

# The HUD's variables. The keys only raise WearOpen / WearTakeOffRequested,
# so a probe can open the panel and take a garment off without a keyboard.
WEAR_OPEN_VAR = Var("WearOpen", BOOL, False)
WEAR_SEL_VAR = Var("WearSel", INT, 0)
WEAR_TAKE_VAR = Var("WearTakeOffRequested", BOOL, False)
WEAR_STILL_VAR = Var("WearStill", BOOL, False)


def _portraits():
    from uebp.graph import _must_load
    return [_must_load(f"{UI_ART_DIR}/{p.texture}") for p in PORTRAITS]


# The portrait's pictures, by index (item_icons/portrait.py: a bit per garment
# drawn on the body), the index of what is worn now, and the one on show.
WEAR_PORTRAITS_VAR = Var("WearPortraits", array(obj("/Script/Engine.Texture2D")),
                         lazy(_portraits))
WEAR_PORTRAIT_INDEX_VAR = Var("WearPortraitIndex", INT, 0)
WEAR_PORTRAIT_SHOWN_VAR = Var("WearPortraitShown", INT, 0)
# In the order wear_tick.py has always declared them.
TABLE = (WEAR_SEL_VAR, WEAR_OPEN_VAR, WEAR_TAKE_VAR, WEAR_STILL_VAR,
         WEAR_PORTRAITS_VAR, WEAR_PORTRAIT_INDEX_VAR, WEAR_PORTRAIT_SHOWN_VAR)

# WBP_HUD's widgets.
WEAR_PANEL = "WearPanel"
WEAR_SLOTS_BOX = "WearSlots"        # a grid of WBP_InventorySlot, one per slot
WEAR_COLUMNS = 4
WEAR_ROWS = len(WEAR_SLOTS)
# The character's portrait (item_icons/portrait.py renders it): a picture of
# the player's body from the front, in what is worn, left of the kit, up
# while the panel is open.
WEAR_PORTRAIT = "WearPortrait"
WEAR_PORTRAIT_IMAGE = "WearPortraitImage"
WEAR_PORTRAIT_SIZE = (150.0, 300.0)     # the texture's own 1:2
WEAR_PORTRAIT_PAD = 12.0                # the panel's edge round the picture
WEAR_PORTRAIT_GAP = 12.0                # between it and the kit

# Each worn slot's silhouette: the item (item_icons/items.py's DisplayName)
# whose icon stands, translucent, in the empty slot.
WEAR_GHOSTS = tuple(s.capitalize() for s in WEAR_SLOTS)
