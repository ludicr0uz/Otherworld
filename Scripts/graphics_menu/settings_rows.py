"""The settings screen's constants: what is saved, which row is which, the
panel's geometry, and what a bind may be set to. Constants only -- the page is
drawn by settings_page.py and driven by settings_input.py.
"""

from collections import namedtuple

from combat import paths as combat_paths
from combat import tuning as combat_tuning

# ── The settings screen, and what survives a restart ─────────────────────────
#
# Two pages, one panel: MenuPage picks which, MenuRow picks the line, and the
# caret is drawn from MenuRow the same way the quality caret is drawn from
# Quality. There is no second HUD and no widget -- see the AHUD note at the top
# of this file for why there cannot be.
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

# Rows 0..len(SLIDERS)-1 are the sliders, then BIND_VARS in order, then BACK.
# The arithmetic "row - FIRST_BIND_ROW is the bind index" appears in the graph
# twice and is the reason the binds are contiguous.
SENS_ROW = 0
SCOPE_SENS_ROW = 1
FIRST_BIND_ROW = len(SLIDERS)
SETTINGS_ROWS = FIRST_BIND_ROW + len(BIND_VARS) + 1
BACK_ROW = SETTINGS_ROWS - 1
BIND_LABELS = ("FIRE", "SHOULDER AIM", "AIM DOWN SIGHTS", "SPRINT", "SWITCH", "DROP",
               "PICK UP", "RELOAD", "BLOCK", "CROUCH", "PRONE")
SENS_LABEL = SLIDERS[SENS_ROW].label
SCOPE_SENS_LABEL = SLIDERS[SCOPE_SENS_ROW].label
BACK_LABEL = "BACK"
SETTINGS_TITLE = "SETTINGS"

SET_TITLE_OFF = 44.0
SET_ROW0_OFF = 118.0
SET_ROW_STEP = 46.0
SET_HINT_OFF = SET_ROW0_OFF + SETTINGS_ROWS * SET_ROW_STEP + 12.0
# Tall enough for every row plus the hint, with the 16 px bottom margin the
# nine-row page had (560 px); it grows with the rows instead of being retyped.
SETTINGS_PANEL = (620.0, SET_HINT_OFF + 16.0)
SET_LABEL_X = 96.0         # from the panel's left edge
SET_VALUE_X = 380.0        # the value column, so the rows line up
SET_CARET_X = 56.0
SET_TITLE_SCALE = 2.2
SET_ROW_SCALE = 1.5
SET_HINT_SCALE = 1.2

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
