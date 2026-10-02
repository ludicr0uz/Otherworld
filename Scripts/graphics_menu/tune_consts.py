"""The M panel's GUN TUNING tab: its row and keys, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), tune_tick and tune_draw (the graph), tune_save (the
save, run inside the game) and tune_checks read one table.

    the M panel's row           opens the tab (the keys below are tune_tab's,
                                shared by every tab); BACK shuts it
    Up / Down                   pick a row: the gun, then one row per stat
    Left / Right                on the gun row: the previous / next gun;
                                on a stat: one step down / up (on every
                                carried copy of that gun, at once)
    Enter                       save every gun's numbers to gun_tuning.csv

The melee weapons (the knife, the axe) are subjects too, after the guns, with
only their throw's rows: a stat that is not the shown weapon's own
(gun_tuning.columns_of) shows a dash and does not move (TuneLive).

The stats, their steps and minimums are combat/gun_tuning.TUNE_STATS. GUN_TAB
is the same names as a TuneTab (tune_tab.py), which is what the shared
fragments take.
"""

from combat.gun_tuning import TUNE_STATS
from graphics_menu.tune_tab import TuneTab, save_command

TUNE_ACTION = "gun_tuning"         # the M panel row that opens the tab
TUNE_ROW_LABEL = "gun tuning"

# The HUD's variables. The keys only raise TuneNudge / TuneSaveRequested and
# Tick serves them, so a probe can tune and save without a keyboard.
TUNE_OPEN_VAR = "TuneOpen"
TUNE_ROW_VAR = "TuneRow"            # 0 = the gun row, 1.. = TUNE_STATS
TUNE_WEAPON_VAR = "TuneWeapon"      # index into TuneWeapons
TUNE_NUDGE_VAR = "TuneNudge"        # -1 / +1 asked for this Tick, 0 = none
TUNE_SAVE_VAR = "TuneSaveRequested"
TUNE_SAVED_VAR = "TuneSaved"        # the last save succeeded, nothing moved since
TUNE_TOUCHED_VAR = "TuneTouched"    # something was tuned: apply every Tick
# The table: TuneValues[w * len(TUNE_STATS) + s] is gun w's stat s. Seeded
# from the built specs (so gun_tuning.csv), the page's working copy.
TUNE_VALUES_VAR = "TuneValues"
TUNE_WEAPONS_VAR = "TuneWeapons"    # the guns' DisplayNames, in spec order
# TuneLive[w * len(TUNE_STATS) + s]: is stat s weapon w's own (a gun has no
# throw damage, a melee weapon only its throw)?
TUNE_LIVE_VAR = "TuneLive"
TUNE_DASH = "-"                     # what a row that is not shows
TUNE_STEPS_VAR = "TuneSteps"        # per stat
TUNE_MINS_VAR = "TuneMins"          # per stat

STAT_COUNT = len(TUNE_STATS)
TUNE_ROW_COUNT = 1 + STAT_COUNT

# WBP_PauseMenu's widgets.
TUNE_PANEL = "TunePanel"
TUNE_ROWS_BOX = "TuneRows"
TUNE_SAVED_TEXT = "TuneSavedText"
TUNE_TITLE_TEXT = "GUN TUNING"
TUNE_GUN_LABEL = "gun"
TUNE_ROW_LABELS = (TUNE_GUN_LABEL,) + tuple(s[2] for s in TUNE_STATS)
TUNE_HINT_TEXT = ("UP / DOWN  pick   ·   LEFT / RIGHT  change   ·   "
                  "ENTER  save to gun_tuning.csv")
TUNE_SAVED_WORDS = "saved to Scripts/combat/gun_tuning.csv"
TUNE_PANEL_W = 520.0
TUNE_POS = (60.0, 130.0)            # where the M panel was: an open tab replaces it
# A tab in the corner (TuneTab.corner): its bottom-right, in from the screen's,
# clear of the watermark (legal_consts.WATERMARK_BOTTOM).
TUNE_CORNER_MARGIN = (24.0, 44.0)
# The corner tab is small: tighter inside than umg_consts.PANEL_PADDING.
TUNE_CORNER_PADDING = (24.0, 14.0, 24.0, 12.0)
# One row of a scrolling tab (TuneTab.visible_rows), in slate units: the
# list is a window visible_rows of these high. A WBP_MenuRow's desired
# height at ROW_FONT, read off a rendered run (22.52): no API gives it to
# the build.
TUNE_ROW_H = 22.5
TUNE_ROW_LABEL_W = 250.0
TUNE_TITLE_FONT, TUNE_HINT_FONT = 20.0, 11.0

# The HUD's own class, which the save finds the live instance of. Spelt out,
# not built from umg_consts.UI_DIR: umg_consts imports this module's label.
HUD_CLASS_PATH = "/Game/UI/BP_GraphicsMenuHUD.BP_GraphicsMenuHUD_C"

# What Enter runs: tune_save.save() (see tune_tab.save_command).
TUNE_SAVE_COMMAND = save_command("graphics_menu.tune_save")

GUN_TAB = TuneTab(
    action=TUNE_ACTION, open_var=TUNE_OPEN_VAR, row_var=TUNE_ROW_VAR,
    pick_var=TUNE_WEAPON_VAR, nudge_var=TUNE_NUDGE_VAR, save_var=TUNE_SAVE_VAR,
    saved_var=TUNE_SAVED_VAR, touched_var=TUNE_TOUCHED_VAR,
    values_var=TUNE_VALUES_VAR, names_var=TUNE_WEAPONS_VAR,
    steps_var=TUNE_STEPS_VAR, mins_var=TUNE_MINS_VAR, live_var=TUNE_LIVE_VAR,
    stat_count=STAT_COUNT,
    save_command=TUNE_SAVE_COMMAND, panel=TUNE_PANEL, rows_box=TUNE_ROWS_BOX,
    saved_text=TUNE_SAVED_TEXT, title_widget="TuneTitle", hint_widget="TuneHint",
    back_widget="TuneBack",
    title_text=TUNE_TITLE_TEXT, row_labels=TUNE_ROW_LABELS, hint_text=TUNE_HINT_TEXT,
    saved_words=TUNE_SAVED_WORDS)
