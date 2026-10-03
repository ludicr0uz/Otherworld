"""The menu's PLAYER SETTINGS tab: its row, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), player_tune_tick and tune_draw (the graph),
player_tune_save (the save, run inside the game) and player_tune_checks read
one table.

    the menu's row              opens the tab (tune_tab.py); BACK shuts it
    Up / Down, Left / Right,    as GUN SETTINGS (tune_tab.py), over one subject,
    Enter                       "player": the jog's and the sprint's speed
                                (m/s), how long a full stamina bar sprints
                                and an empty one refills (s); Enter saves
                                them to combat/player_tuning.csv

The rows, their steps and minimums are combat/player_tuning.PLAYER_STATS.
"""

from combat.player_tuning import PLAYER_STATS
from graphics_menu.tune_tab import TuneTab, save_command

PLAYER_TUNE_ACTION = "player_tuning"   # the menu row that opens the tab
PLAYER_TUNE_ROW_LABEL = "Player Settings"

PLAYER_TUNE_OPEN_VAR = "PlayerTuneOpen"
PLAYER_TUNE_ROW_VAR = "PlayerTuneRow"        # 0 = the subject row, 1.. = PLAYER_STATS
PLAYER_TUNE_PICK_VAR = "PlayerTunePick"      # always 0: one subject
PLAYER_TUNE_NUDGE_VAR = "PlayerTuneNudge"
PLAYER_TUNE_SAVE_VAR = "PlayerTuneSaveRequested"
PLAYER_TUNE_SAVED_VAR = "PlayerTuneSaved"
PLAYER_TUNE_TOUCHED_VAR = "PlayerTuneTouched"
# PlayerTuneValues[s] is PLAYER_STATS[s], in the table's units (m/s, s).
PLAYER_TUNE_VALUES_VAR = "PlayerTuneValues"
PLAYER_TUNE_NAMES_VAR = "PlayerTuneNames"
PLAYER_TUNE_STEPS_VAR = "PlayerTuneSteps"
PLAYER_TUNE_MINS_VAR = "PlayerTuneMins"

PLAYER_SUBJECT = "player"
PLAYER_STAT_COUNT = len(PLAYER_STATS)

PLAYER_TUNE_SAVE_COMMAND = save_command("graphics_menu.player_tune_save")

PLAYER_TAB = TuneTab(
    action=PLAYER_TUNE_ACTION, open_var=PLAYER_TUNE_OPEN_VAR,
    row_var=PLAYER_TUNE_ROW_VAR, pick_var=PLAYER_TUNE_PICK_VAR,
    nudge_var=PLAYER_TUNE_NUDGE_VAR, save_var=PLAYER_TUNE_SAVE_VAR,
    saved_var=PLAYER_TUNE_SAVED_VAR, touched_var=PLAYER_TUNE_TOUCHED_VAR,
    values_var=PLAYER_TUNE_VALUES_VAR, names_var=PLAYER_TUNE_NAMES_VAR,
    steps_var=PLAYER_TUNE_STEPS_VAR, mins_var=PLAYER_TUNE_MINS_VAR,
    stat_count=PLAYER_STAT_COUNT, save_command=PLAYER_TUNE_SAVE_COMMAND,
    panel="PlayerTunePanel", rows_box="PlayerTuneRows",
    saved_text="PlayerTuneSavedText", back_widget="PlayerTuneBack",
    title_widget="PlayerTuneTitle", hint_widget="PlayerTuneHint",
    title_text="PLAYER SETTINGS",
    row_labels=(PLAYER_SUBJECT,) + tuple(s[1] for s in PLAYER_STATS),
    hint_text=("UP / DOWN  pick   ·   LEFT / RIGHT  change   ·   "
               "ENTER  save to player_tuning.csv"),
    saved_words="saved to Scripts/combat/player_tuning.csv",
    fraction_digits=2)
