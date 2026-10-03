"""The M panel's WORLD SETTINGS tab: its row, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), world_tune_tick and tune_draw (the graph),
world_tune_save (the save, run inside the game) and world_tune_checks read
one table.

    the M panel's row           opens the tab (tune_tab.py); BACK shuts it
    Up / Down, Left / Right,    as GUN SETTINGS (tune_tab.py), over one subject,
    Enter                       "world": the time of day (hours, live only),
                                the day's and the night's lengths, how fast
                                the night cools the player, whether an item
                                on the ground glimmers (1 on, 0 off); Enter
                                saves all but the hour to
                                world/world_tuning.csv

The rows, their steps and minimums are world/world_tuning.WORLD_STATS, and
their maximums its WORLD_MAXS (only the on/off row has a real one).
"""

from graphics_menu.tune_tab import TuneTab, save_command
from world.world_tuning import WORLD_STATS

WORLD_TUNE_ACTION = "world_tuning"   # the M panel row that opens the tab
WORLD_TUNE_ROW_LABEL = "World Settings"

WORLD_TUNE_OPEN_VAR = "WorldTuneOpen"
WORLD_TUNE_ROW_VAR = "WorldTuneRow"        # 0 = the subject row, 1.. = WORLD_STATS
WORLD_TUNE_PICK_VAR = "WorldTunePick"      # always 0: one subject
WORLD_TUNE_NUDGE_VAR = "WorldTuneNudge"
WORLD_TUNE_SAVE_VAR = "WorldTuneSaveRequested"
WORLD_TUNE_SAVED_VAR = "WorldTuneSaved"
WORLD_TUNE_TOUCHED_VAR = "WorldTuneTouched"
# WorldTuneValues[s] is WORLD_STATS[s]: the hour, the day's length, the
# night's, the night's cold, the item highlight.
WORLD_TUNE_VALUES_VAR = "WorldTuneValues"
WORLD_TUNE_NAMES_VAR = "WorldTuneNames"
WORLD_TUNE_STEPS_VAR = "WorldTuneSteps"
WORLD_TUNE_MINS_VAR = "WorldTuneMins"
WORLD_TUNE_MAXS_VAR = "WorldTuneMaxs"
# The hour the HUD last read off the cycle. WorldTuneValues[0] differing
# from it means a nudge moved the hour: write the cycle's Clock.
WORLD_TUNE_HOUR_SEEN_VAR = "WorldTuneHourSeen"

WORLD_SUBJECT = "world"
WORLD_STAT_COUNT = len(WORLD_STATS)
HOUR_ROW = 1                                # the tab row of the time of day

WORLD_TUNE_SAVE_COMMAND = save_command("graphics_menu.world_tune_save")

WORLD_TAB = TuneTab(
    action=WORLD_TUNE_ACTION, open_var=WORLD_TUNE_OPEN_VAR, row_var=WORLD_TUNE_ROW_VAR,
    pick_var=WORLD_TUNE_PICK_VAR, nudge_var=WORLD_TUNE_NUDGE_VAR,
    save_var=WORLD_TUNE_SAVE_VAR, saved_var=WORLD_TUNE_SAVED_VAR,
    touched_var=WORLD_TUNE_TOUCHED_VAR, values_var=WORLD_TUNE_VALUES_VAR,
    names_var=WORLD_TUNE_NAMES_VAR, steps_var=WORLD_TUNE_STEPS_VAR,
    mins_var=WORLD_TUNE_MINS_VAR, stat_count=WORLD_STAT_COUNT,
    save_command=WORLD_TUNE_SAVE_COMMAND,
    panel="WorldTunePanel", rows_box="WorldTuneRows", saved_text="WorldTuneSavedText",
    back_widget="WorldTuneBack",
    title_widget="WorldTuneTitle", hint_widget="WorldTuneHint",
    title_text="WORLD SETTINGS",
    row_labels=(WORLD_SUBJECT,) + tuple(s[2] for s in WORLD_STATS),
    hint_text=("UP / DOWN  pick   ·   LEFT / RIGHT  change   ·   "
               "ENTER  save to world_tuning.csv"),
    saved_words="saved to Scripts/world/world_tuning.csv",
    fraction_digits=2, maxs_var=WORLD_TUNE_MAXS_VAR)
