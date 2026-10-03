"""BP_GraphicsMenuHUD's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; the fragments' own variables are declared by their declare_*_vars.
"""

from uebp.vars import BOOL, INT, Var, array, obj, struct
from combat.paths import SETTINGS_CLASS_PATH
from graphics_menu.settings_rows import PAGE_TITLE

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
