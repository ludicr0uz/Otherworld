"""The menu's SOUND SETTINGS tab: its row, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), sound_tune_tick and tune_draw (the graph),
sound_tune_save (the save, run inside the game) and sound_tune_checks read
one table.

    the menu's row              opens the tab (tune_tab.py); BACK shuts it
    Up / Down, Left / Right,    as GUN SETTINGS (tune_tab.py), over one subject,
    Enter                       "volume": one row per sound of the game, its
                                volume as a multiplier (0 silent, 1 as
                                recorded, at most 2); Enter saves them to
                                combat/sound_tuning.csv

The rows are combat/sound_tuning.SOUND_STATS.
"""

from combat.sound_tuning import SOUND_STATS
from graphics_menu.tune_tab import TuneTab, save_command

SOUND_TUNE_ACTION = "sound_tuning"   # the menu row that opens the tab
SOUND_TUNE_ROW_LABEL = "Sound Settings"

SOUND_TUNE_OPEN_VAR = "SoundTuneOpen"
SOUND_TUNE_ROW_VAR = "SoundTuneRow"        # 0 = the subject row, 1.. = SOUND_STATS
SOUND_TUNE_PICK_VAR = "SoundTunePick"      # always 0: one subject
SOUND_TUNE_NUDGE_VAR = "SoundTuneNudge"
SOUND_TUNE_SAVE_VAR = "SoundTuneSaveRequested"
SOUND_TUNE_SAVED_VAR = "SoundTuneSaved"
# A volume moved and the mix has not been told. Unlike the other tabs' it is
# lowered again: the mix is the audio device's, not a player's who respawns.
SOUND_TUNE_TOUCHED_VAR = "SoundTuneTouched"
# SoundTuneValues[s] is SOUND_STATS[s]'s volume.
SOUND_TUNE_VALUES_VAR = "SoundTuneValues"
SOUND_TUNE_NAMES_VAR = "SoundTuneNames"
SOUND_TUNE_STEPS_VAR = "SoundTuneSteps"
SOUND_TUNE_MINS_VAR = "SoundTuneMins"
SOUND_TUNE_MAXS_VAR = "SoundTuneMaxs"
# The mix holds this HUD's table: false until its first Tick has told it.
SOUND_TUNE_APPLIED_VAR = "SoundTuneApplied"

SOUND_SUBJECT = "volume"
SOUND_STAT_COUNT = len(SOUND_STATS)

SOUND_TUNE_SAVE_COMMAND = save_command("graphics_menu.sound_tune_save")

SOUND_TAB = TuneTab(
    action=SOUND_TUNE_ACTION, open_var=SOUND_TUNE_OPEN_VAR,
    row_var=SOUND_TUNE_ROW_VAR, pick_var=SOUND_TUNE_PICK_VAR,
    nudge_var=SOUND_TUNE_NUDGE_VAR, save_var=SOUND_TUNE_SAVE_VAR,
    saved_var=SOUND_TUNE_SAVED_VAR, touched_var=SOUND_TUNE_TOUCHED_VAR,
    values_var=SOUND_TUNE_VALUES_VAR, names_var=SOUND_TUNE_NAMES_VAR,
    steps_var=SOUND_TUNE_STEPS_VAR, mins_var=SOUND_TUNE_MINS_VAR,
    stat_count=SOUND_STAT_COUNT, save_command=SOUND_TUNE_SAVE_COMMAND,
    panel="SoundTunePanel", rows_box="SoundTuneRows",
    saved_text="SoundTuneSavedText", back_widget="SoundTuneBack",
    title_widget="SoundTuneTitle", hint_widget="SoundTuneHint",
    title_text="SOUND SETTINGS",
    row_labels=(SOUND_SUBJECT,) + tuple(s[1] for s in SOUND_STATS),
    hint_text=("UP / DOWN  pick   ·   LEFT / RIGHT  change   ·   "
               "ENTER  save to sound_tuning.csv"),
    saved_words="saved to Scripts/combat/sound_tuning.csv",
    fraction_digits=2, maxs_var=SOUND_TUNE_MAXS_VAR)
