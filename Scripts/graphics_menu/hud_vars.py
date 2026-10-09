"""BP_GraphicsMenuHUD's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE and PANEL; a fragment's own variables are rows of its constants module
(cursor_consts.TABLE, loot_consts.TABLE, a tab's tune_tab.tab_table, ...),
or, where it has none, a group below, and its declare_*_vars declares them.
"""

from uebp.vars import BOOL, FLOAT, INT, STRING, Var, array, obj, struct
from combat.paths import SETTINGS_CLASS_PATH
from graphics_menu.settings_rows import DIFFICULTY_LABELS, PAGE_TITLE
from graphics_menu.umg_consts import GAME_STARTED_VAR, PAUSE_ROW_VAR

# MenuOpen drives both input gating and drawing; Quality drives the caret
# (its default is the startup preset, which the builder writes).
MenuOpen = Var("MenuOpen", BOOL, False)
# This frame's copy of the GameMode's DebugMode. Taken once at the top of DrawHUD.
DebugOn = Var("DebugOn", BOOL, False)
Quality = Var("Quality", INT)
# Which page of the menu panel is on screen, and which line of it the caret is on.
MenuPage = Var("MenuPage", INT, PAGE_TITLE)
MenuRow = Var("MenuRow", INT, 0)
# Armed by Enter on a bind row; the next key the player presses becomes that bind.
Capturing = Var("Capturing", BOOL, False)
# The loaded save. Typed as BP_Settings rather than as SaveGame so the page
# can read MouseSensitivity and Binds off it without a cast per read; the
# one cast is at BeginPlay, where LoadGameFromSlot hands back a USaveGame.
Settings = Var("Settings", obj(SETTINGS_CLASS_PATH))
# What a bind may be captured as -- walked by a ForEachLoop while
# Capturing. A variable rather than a literal chain because the
# graph tests every entry with the same three nodes.
KeyPool = Var("KeyPool", array(struct("/Script/InputCore.Key")))

TABLE = (MenuOpen, DebugOn, Quality, MenuPage, MenuRow, Capturing, Settings, KeyPool)

# Whether the controller was told to ignore move input for the open panel
# (menu_still.py).
MenuStill = Var("MenuStill", BOOL, False)
# The M panel's caret, MenuStill, and GameStarted: false until the player picks
# NEW GAME, and BeginPlay pauses the world alongside it.
PANEL = (PAUSE_ROW_VAR, MenuStill, GAME_STARTED_VAR)

# The names the difficulty row shows, indexed like the save (difficulty.py).
DifficultyLabels = Var("DifficultyLabels", array(STRING), list(DIFFICULTY_LABELS))
DIFFICULTY = (DifficultyLabels,)

# The FPS readout (fps.py). All three start at zero, which is what a
# declaration leaves.
FpsFrames = Var("FpsFrames", INT)     # frames drawn since FpsSince
FpsSince = Var("FpsSince", FLOAT)     # real time the current window opened
FpsShown = Var("FpsShown", INT)       # what the readout says, rounded
FPS = (FpsFrames, FpsSince, FpsShown)
