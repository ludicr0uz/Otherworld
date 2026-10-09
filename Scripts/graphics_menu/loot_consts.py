"""The loot window: its keys, the HUD's variables, WBP_HUD's widget names and
words. Constants only, so wbp_loot (the layout), loot_tick and loot_draw (the
graph) and loot_checks read one table.

    [Tab] near a body             kneel and open the window (Tab again closes
                                  it and stands up); a body with nothing on it
                                  can be searched too, and says so
    Up / Down                     move the caret
    Enter                         take the selected item into the bag
    a click on "[TAB] close"      shuts the window, as Tab does

Fixed keys, like the menu's: Up/Down/Enter are the menu's own navigation keys,
and Tab is not a gameplay bind. E stays interact, which picks up: a gun a kill
drops lies beside the body, and E on it must not also empty the body.
"""

from combat.paths import HEALTH_CLASS_PATH
from loot.consts import LOOT_RADIUS
from uebp.vars import BOOL, FLOAT, INT, Var, obj

LOOT_KEY = "Tab"
LOOT_UP, LOOT_DOWN = "Up", "Down"       # menu_nav.NAV_UP / NAV_DOWN
LOOT_TAKE_KEY = "Enter"

# The HUD's variables. LootTarget is the nearest searchable body's health
# component, found every Tick; the keys only raise LootOpen / LootTakeRequested,
# so a probe can open and take without a keyboard.
LOOT_TARGET_VAR = Var("LootTarget", obj(HEALTH_CLASS_PATH))
LOOT_BEST_VAR = Var("LootBest", FLOAT, LOOT_RADIUS)   # scratch: the nearest body's distance so far
LOOT_OPEN_VAR = Var("LootOpen", BOOL, False)
LOOT_SEL_VAR = Var("LootSel", INT, 0)
LOOT_TAKE_VAR = Var("LootTakeRequested", BOOL, False)
LOOT_BAG_FULL_VAR = Var("LootBagFull", BOOL, False)
# What LootOpen was last Tick: the edge that takes and gives back the walk
# (loot_kneel.py).
LOOT_KNEELING_VAR = Var("LootKneeling", BOOL, False)
# In the order loot_tick.py has always declared them.
TABLE = (LOOT_TARGET_VAR, LOOT_BEST_VAR, LOOT_SEL_VAR, LOOT_OPEN_VAR, LOOT_TAKE_VAR,
         LOOT_BAG_FULL_VAR, LOOT_KNEELING_VAR)

# WBP_HUD's widgets.
LOOT_PROMPT = "LootPrompt"
LOOT_PANEL = "LootPanel"
LOOT_ROWS_BOX = "LootRows"
LOOT_FULL = "LootFull"
LOOT_EMPTY = "LootEmpty"            # shown instead of rows on a body with nothing
LOOT_CLOSE = "LootClose"            # the close button: a line a click lands on
LOOT_ROWS = 6                       # rows the window has; a table rolls fewer

LOOT_PROMPT_TEXT = f"[{LOOT_KEY.upper()}]   search the body"
LOOT_TITLE_TEXT = "THE BODY CARRIES"
LOOT_HINT_TEXT = "UP / DOWN   ·   ENTER or click takes"
LOOT_CLOSE_TEXT = f"[{LOOT_KEY.upper()}]   close"
LOOT_FULL_TEXT = "BAG FULL"
LOOT_EMPTY_TEXT = "NOTHING"
LOOT_PANEL_W = 380.0
LOOT_RIGHT = 60.0                   # px in from the right edge, centred vertically
LOOT_PROMPT_Y = 90.0                # px below the viewport centre
LOOT_TITLE_FONT, LOOT_HINT_FONT, LOOT_PROMPT_FONT = 20.0, 12.0, 16.0
