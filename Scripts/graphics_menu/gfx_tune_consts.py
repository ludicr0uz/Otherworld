"""The M panel's GRAPHICS SETTINGS tab: its row, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), gfx_tune_tick and tune_draw (the graph), gfx_tune_save
(the save, run inside the game) and gfx_checks read one table.

    the M panel's row           opens the tab (tune_tab.py); BACK shuts it
    Up / Down, Left / Right     as GUN SETTINGS. The subject row is the quality
                                preset: Left / Right there pick Low / Medium /
                                High / Custom, and it is the only place a
                                preset is picked. The rows under it are that
                                preset's numbers
    SAVE DEFAULT (Enter on it,  all four presets, and the picked one as the
    or a click)                 default, to graphics_menu/graphics_tuning.csv.
                                Enter on a number saves nothing here

The pick and Custom's numbers are the player's: every change of either is
kept in BP_GraphicsSave (gfx_save.py) and is there again next session. Low,
Medium and High start every session as the CSV has them.

The tab is the one the player keeps open while looking at the picture, so it
is small and out of the way: bottom right, a small title, and a list that
shows GFX_VISIBLE_ROWS rows at a time behind a scroll bar (the list follows
the caret, and the bar is dragged: tune_scroll.py). The rows, their steps and limits are
gfx_stats.GFX_STATS.
"""

from graphics_menu.gfx_stats import GFX_STATS, PRESET_LABELS, STAT_COUNT
from graphics_menu.tune_tab import TuneTab, save_command

GFX_TUNE_ACTION = "graphics_tuning"  # the M panel row that opens the tab
GFX_TUNE_ROW_LABEL = "Graphics Settings"

GFX_TUNE_OPEN_VAR = "GfxTuneOpen"
GFX_TUNE_ROW_VAR = "GfxTuneRow"          # 0 = the preset row, 1.. = GFX_STATS
GFX_TUNE_PICK_VAR = "GfxTunePick"        # the preset shown: follows Quality
GFX_TUNE_NUDGE_VAR = "GfxTuneNudge"
GFX_TUNE_SAVE_VAR = "GfxTuneSaveRequested"
GFX_TUNE_SAVED_VAR = "GfxTuneSaved"
# A number moved: Tick spreads the look rows over every preset, hands the
# table to BP_GraphicsTuner and lowers it again.
GFX_TUNE_TOUCHED_VAR = "GfxTuneTouched"
# GfxTuneValues[p * STAT_COUNT + s] is preset p's stat s.
GFX_TUNE_VALUES_VAR = "GfxTuneValues"
GFX_TUNE_NAMES_VAR = "GfxTuneNames"
GFX_TUNE_STEPS_VAR = "GfxTuneSteps"
GFX_TUNE_MINS_VAR = "GfxTuneMins"
GFX_TUNE_MAXS_VAR = "GfxTuneMaxs"
# The pick Tick last saw. GfxTunePick differing from it means Left / Right on
# the preset row moved it: Quality follows. Otherwise the pick follows Quality.
GFX_TUNE_PICK_SEEN_VAR = "GfxTunePickSeen"
# The Quality the tuner was last handed. -1 is no preset, so the first Tick
# of every session hands it the startup preset's row.
GFX_APPLIED_VAR = "GfxQualityApplied"
GFX_APPLIED_DEFAULT = -1

# The HUD's BP_GraphicsTuner component (gfx_tuner.py), which applies a row.
TUNER_COMPONENT = "GraphicsTuner"

# The list's window, and the title's size (the other tabs: TUNE_TITLE_FONT).
GFX_VISIBLE_ROWS = 5
GFX_TITLE_FONT = 13.0

GFX_TUNE_SAVE_COMMAND = save_command("graphics_menu.gfx_tune_save")
GFX_SAVE_DEFAULT_LABEL = "SAVE DEFAULT"

GFX_TAB = TuneTab(
    action=GFX_TUNE_ACTION, open_var=GFX_TUNE_OPEN_VAR, row_var=GFX_TUNE_ROW_VAR,
    pick_var=GFX_TUNE_PICK_VAR, nudge_var=GFX_TUNE_NUDGE_VAR,
    save_var=GFX_TUNE_SAVE_VAR, saved_var=GFX_TUNE_SAVED_VAR,
    touched_var=GFX_TUNE_TOUCHED_VAR, values_var=GFX_TUNE_VALUES_VAR,
    names_var=GFX_TUNE_NAMES_VAR, steps_var=GFX_TUNE_STEPS_VAR,
    mins_var=GFX_TUNE_MINS_VAR, stat_count=STAT_COUNT,
    save_command=GFX_TUNE_SAVE_COMMAND,
    panel="GfxTunePanel", rows_box="GfxTuneRows", saved_text="GfxTuneSavedText",
    back_widget="GfxTuneBack", save_widget="GfxTuneSaveDefault",
    save_label=GFX_SAVE_DEFAULT_LABEL,
    title_widget="GfxTuneTitle", hint_widget="GfxTuneHint",
    title_text="GRAPHICS SETTINGS",
    row_labels=("preset",) + tuple(s.label for s in GFX_STATS),
    hint_text="LEFT / RIGHT or click  change   ·   Custom is remembered",
    saved_words="default saved to Scripts/graphics_menu/graphics_tuning.csv",
    fraction_digits=2, maxs_var=GFX_TUNE_MAXS_VAR, label_w=280.0, panel_w=440.0,
    title_font=GFX_TITLE_FONT, visible_rows=GFX_VISIBLE_ROWS, corner=True,
    kept=False)   # its own save, of the Custom row alone: gfx_save.py

assert len(PRESET_LABELS) == 4

# ─── BP_GraphicsTuner: the component that applies a row ──────────────────────
TUNER_BP_PATH = "/Game/UI/BP_GraphicsTuner"
TUNER_CLASS_PATH = f"{TUNER_BP_PATH}.BP_GraphicsTuner_C"
# What the HUD hands it: the whole table, which preset to apply, and the ask.
TUNER_VALUES_VAR = "Values"
TUNER_PRESET_VAR = "Preset"
TUNER_DIRTY_VAR = "Dirty"
# Preset * STAT_COUNT, set once at the top of an apply: a stat is Values[Base + s].
TUNER_BASE_VAR = "Base"
# What the world was last set to, so an apply only redoes what moved. The
# distances start at 1 (a level is saved at its own distances); the rest at
# -1, no value, so the first apply of a session always does them.
TUNER_LEVEL_APPLIED_VAR = "LevelApplied"
TUNER_GRASS_DISTANCE_APPLIED_VAR = "GrassDistanceApplied"
TUNER_TREE_DISTANCE_APPLIED_VAR = "TreeDistanceApplied"
TUNER_GRASS_SHADOWS_APPLIED_VAR = "GrassShadowsApplied"
TUNER_GRASS_LAYERS_APPLIED_VAR = "GrassLayersApplied"
TUNER_WIND_APPLIED_VAR = "WindApplied"
TUNER_WIND_DISTANCE_APPLIED_VAR = "WindDistanceApplied"   # metres
TUNER_NEVER = -1

# ─── BP_GraphicsSave: what the player's graphics keep between sessions ───────
GFX_SAVE_BP_PATH = "/Game/UI/BP_GraphicsSave"
GFX_SAVE_CLASS_PATH = f"{GFX_SAVE_BP_PATH}.BP_GraphicsSave_C"
GFX_SAVE_SLOT = "OtherworldGraphics"
GFX_SAVE_USER_INDEX = 0
# The picked preset, and the HUD's whole table as it stood. Only Custom's row
# of it is read back; a table of any other length is from an older build
# (another STAT_COUNT) and is left alone, pick and all.
GFX_SAVE_QUALITY_FIELD = "SavedQuality"
GFX_SAVE_TABLE_FIELD = "SavedTable"
GFX_SAVE_TABLE_LEN = len(PRESET_LABELS) * STAT_COUNT
