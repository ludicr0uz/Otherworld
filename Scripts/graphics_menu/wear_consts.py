"""The I panel: what the player wears. Its key, the HUD's variables, WBP_HUD's
widget names and words. Constants only, so wbp_wear (the layout), wear_tick
and wear_draw (the graph) and wear_checks read one table.

    [I]                 open the panel (I again closes it); the walk is
                        held while it is open, as under the menu
    Up / Down           move the caret over the slots
    Enter, or a click   take the garment in that slot off, into the bag
    a click on "[I] close"  shuts it, as I does

A fixed key, like Tab: not a gameplay bind. Up/Down/Enter are the menu's
navigation keys; with the loot window open they are the loot window's, and
with the menu open the menu's.
"""

from combat.wear_tuning import WEAR_SLOTS

WEAR_KEY = "I"
WEAR_UP, WEAR_DOWN = "Up", "Down"       # menu_nav.NAV_UP / NAV_DOWN
WEAR_TAKE_KEY = "Enter"

# The HUD's variables. The keys only raise WearOpen / WearTakeOffRequested,
# so a probe can open the panel and take a garment off without a keyboard.
WEAR_OPEN_VAR = "WearOpen"
WEAR_SEL_VAR = "WearSel"
WEAR_TAKE_VAR = "WearTakeOffRequested"

# WBP_HUD's widgets.
WEAR_PANEL = "WearPanel"
WEAR_ROWS_BOX = "WearRows"
WEAR_CLOSE = "WearClose"            # the close button: a line a click lands on
WEAR_ROWS = len(WEAR_SLOTS)

WEAR_LABELS = tuple(s.upper() for s in WEAR_SLOTS)
WEAR_NONE_TEXT = "-"                # a slot with nothing worn in it
WEAR_TITLE_TEXT = "WORN"
WEAR_HINT_TEXT = "UP / DOWN   ·   ENTER or click takes off"
WEAR_CLOSE_TEXT = f"[{WEAR_KEY}]   close"
WEAR_PANEL_W = 420.0
WEAR_LABEL_W = 150.0                # the slot's name; the garment's beside it
WEAR_LEFT = 60.0                    # px in from the left edge, centred vertically
WEAR_TITLE_FONT, WEAR_HINT_FONT = 20.0, 12.0
