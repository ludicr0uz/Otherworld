"""The settings screen's constants: what is saved, which row is which, the
labels, and what a bind may be set to. Constants only -- the page is laid out
by wbp_screens.py, filled by settings_page.py and driven by settings_input.py.
"""

from collections import namedtuple

from combat import difficulty as combat_difficulty
from combat import paths as combat_paths
from combat import tuning as combat_tuning

# ── The settings screen, and what survives a restart ─────────────────────────
#
# Two pages of WBP_MainMenu: MenuPage picks which, MenuRow picks the line, and
# the lit caret is MenuRow's row, the way the M panel's is Quality's. The rows'
# labels are the designer's (graphics_menu/wbp_screens.py).
#
# Everything on the settings page is stored in BP_Settings, which is a USaveGame
# written to disk on every change (see SETTINGS_SLOT). That is what "loadable
# across future game runs" means here, and it is why the save happens at the
# moment of the edit rather than on leaving the page: a game closed from the
# settings screen still has to remember what was set.
#
# BP_Settings, BIND_VARS and the sensitivity range are all built and defined by
# build_weapons_and_combat.py, which runs first. This file is the only thing
# that reads or writes the save; BP_WeaponComponent is PUSHED the values every
# DrawHUD frame and never learns that a disk exists.
SETTINGS_CLASS_PATH = combat_paths.SETTINGS_CLASS_PATH
SETTINGS_SLOT = combat_paths.SETTINGS_SLOT
SETTINGS_USER_INDEX = combat_paths.SETTINGS_USER_INDEX
BIND_VARS = combat_tuning.BIND_VARS
MOUSE_SENSITIVITY_MIN = combat_tuning.COMBAT.mouse_sensitivity_min
MOUSE_SENSITIVITY_MAX = combat_tuning.COMBAT.mouse_sensitivity_max
MOUSE_SENSITIVITY_STEP = combat_tuning.COMBAT.mouse_sensitivity_step
SCOPE_SENSITIVITY_MIN = combat_tuning.COMBAT.scope_sensitivity_min
SCOPE_SENSITIVITY_MAX = combat_tuning.COMBAT.scope_sensitivity_max
SCOPE_SENSITIVITY_STEP = combat_tuning.COMBAT.scope_sensitivity_step

PAGE_TITLE = 0
PAGE_SETTINGS = 1

# The number rows at the top of the page, one per BP_Settings float that
# Left/Right nudge. Each is drawn, nudged, clamped, saved and pushed onto the
# weapon component by the same code, so adding one is one line here plus the
# variable on BP_Settings and BP_WeaponComponent. The floors are not zero: a
# sensitivity of 0 is a mouse that does not turn, on a screen the player would
# then have to navigate to fix.
Slider = namedtuple("Slider", "label var step lo hi")
SLIDERS = (
    Slider("MOUSE SENSITIVITY", "MouseSensitivity", MOUSE_SENSITIVITY_STEP,
           MOUSE_SENSITIVITY_MIN, MOUSE_SENSITIVITY_MAX),
    # The sniper scope's extra multiplier on top of the zoom's own slowdown;
    # see COMBAT.ads_scope_sens_scale.
    Slider("SCOPE SENSITIVITY", "ScopeSensitivity", SCOPE_SENSITIVITY_STEP,
           SCOPE_SENSITIVITY_MIN, SCOPE_SENSITIVITY_MAX),
)

# Rows 0..len(SLIDERS)-1 are the sliders, then DIFFICULTY, then BIND_VARS in
# order, then BACK. The arithmetic "row - FIRST_BIND_ROW is the bind index"
# appears in the graph twice and is the reason the binds are contiguous.
# DIFFICULTY sits with the sliders because the arrows are its control too, and
# above FIRST_BIND_ROW so Enter on it arms no capture.
SENS_ROW = 0
SCOPE_SENS_ROW = 1
DIFFICULTY_ROW = len(SLIDERS)
FIRST_BIND_ROW = DIFFICULTY_ROW + 1
SETTINGS_ROWS = FIRST_BIND_ROW + len(BIND_VARS) + 1
BACK_ROW = SETTINGS_ROWS - 1
BIND_LABELS = ("FIRE", "SHOULDER AIM", "AIM DOWN SIGHTS", "SPRINT", "SWITCH", "DROP",
               "PICK UP", "RELOAD", "BLOCK", "CROUCH", "PRONE")
SENS_LABEL = SLIDERS[SENS_ROW].label
SCOPE_SENS_LABEL = SLIDERS[SCOPE_SENS_ROW].label
BACK_LABEL = "BACK"
DIFFICULTY_LABEL = "DIFFICULTY"
DIFFICULTY_LABELS = combat_difficulty.DIFFICULTY_LABELS
SETTINGS_TITLE = "SETTINGS"

# What a bind may be set to. Letters, digits, the mouse and the usual
# modifiers -- and nothing the menu itself uses, so no keypress can make the
# settings screen unusable. The capture loop walks this every frame it is
# armed, which is why it is a list of what is ALLOWED rather than a sweep of
# every FKey the engine knows about.
KEY_POOL = (tuple(chr(c) for c in range(ord("A"), ord("Z") + 1))
            + ("One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
               "Nine", "Zero",
               "LeftMouseButton", "RightMouseButton", "MiddleMouseButton",
               "ThumbMouseButton", "ThumbMouseButton2",
               "LeftShift", "LeftControl", "LeftAlt", "Tab"))
