"""The M panel's GUN TUNING tab: its keys, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), tune_tick and tune_draw (the graph), tune_save (the
save, run inside the game) and tune_checks read one table.

    [T] with the M panel open   open / close the tab
    Up / Down                   pick a row: the gun, then one row per stat
    Left / Right                on the gun row: the previous / next gun;
                                on a stat: one step down / up (on every
                                carried copy of that gun, at once)
    Enter                       save every gun's numbers to gun_tuning.csv

The stats, their steps and minimums are combat/gun_tuning.TUNE_STATS.
"""

from combat.gun_tuning import TUNE_STATS

TUNE_KEY = "T"
TUNE_UP, TUNE_DOWN = "Up", "Down"
TUNE_LESS, TUNE_MORE = "Left", "Right"
TUNE_SAVE_KEY = "Enter"
TUNE_ROW_LABEL = f"[{TUNE_KEY}]   gun tuning"

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
TUNE_POS = (700.0, 130.0)           # right of the M panel (PAUSE_POS, PAUSE_W)
TUNE_ROW_LABEL_W = 250.0
TUNE_TITLE_FONT, TUNE_HINT_FONT = 20.0, 11.0

# The HUD's own class, which the save finds the live instance of. Spelt out,
# not built from umg_consts.UI_DIR: umg_consts imports this module's label.
HUD_CLASS_PATH = "/Game/UI/BP_GraphicsMenuHUD.BP_GraphicsMenuHUD_C"

# What Enter runs (PythonScriptLibrary.ExecutePythonCommand): Scripts/ onto
# the path, then tune_save.save(). Only where the Python plugin runs, which
# is the editor, PIE and a -game run of the editor binary: a dev tool.
TUNE_SAVE_COMMAND = (
    "import sys, unreal; "
    "d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()) + 'Scripts'; "
    "d in sys.path or sys.path.insert(0, d); "
    "import graphics_menu.tune_save as t; t.save()")
