"""The loot window: its keys, the HUD's variables, WBP_HUD's widget names and
words. Constants only, so wbp_loot (the layout), loot_tick and loot_draw (the
graph) and loot_checks read one table.

    [Tab] near a body with loot   open the window (Tab again closes it)
    Up / Down                     move the caret
    Enter                         take the selected item into the bag

Fixed keys, like the menu's: Up/Down/Enter are the menu's own navigation keys,
and Tab is not a gameplay bind. E stays the pick-up: a gun a kill drops lies
beside the body, and E on it must not also empty the body.
"""

LOOT_KEY = "Tab"
LOOT_UP, LOOT_DOWN = "Up", "Down"       # menu_nav.NAV_UP / NAV_DOWN
LOOT_TAKE_KEY = "Enter"

# The HUD's variables. LootTarget is the nearest searchable body's health
# component, found every Tick; the keys only raise LootOpen / LootTakeRequested,
# so a probe can open and take without a keyboard.
LOOT_TARGET_VAR = "LootTarget"
LOOT_BEST_VAR = "LootBest"          # scratch: the nearest body's distance so far
LOOT_OPEN_VAR = "LootOpen"
LOOT_SEL_VAR = "LootSel"
LOOT_TAKE_VAR = "LootTakeRequested"
LOOT_BAG_FULL_VAR = "LootBagFull"

# WBP_HUD's widgets.
LOOT_PROMPT = "LootPrompt"
LOOT_PANEL = "LootPanel"
LOOT_ROWS_BOX = "LootRows"
LOOT_FULL = "LootFull"
LOOT_ROWS = 6                       # rows the window has; a table rolls fewer

LOOT_PROMPT_TEXT = f"[{LOOT_KEY.upper()}]   search the body"
LOOT_TITLE_TEXT = "THE BODY CARRIES"
LOOT_HINT_TEXT = f"UP / DOWN   ·   ENTER takes   ·   [{LOOT_KEY.upper()}] close"
LOOT_FULL_TEXT = "BAG FULL"
LOOT_PANEL_W = 380.0
LOOT_RIGHT = 60.0                   # px in from the right edge, centred vertically
LOOT_PROMPT_Y = 90.0                # px below the viewport centre
LOOT_TITLE_FONT, LOOT_HINT_FONT, LOOT_PROMPT_FONT = 20.0, 12.0, 16.0
