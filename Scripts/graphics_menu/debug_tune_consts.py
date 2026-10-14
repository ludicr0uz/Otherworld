"""The menu's DEBUG SETTINGS tab: its row, the HUD's variables, the widget
names and words. Constants only, so wbp_tune (the layout), debug_tune_tick
and tune_draw (the graph) and debug_tune_checks read one table.

    the menu's row              opens the tab (tune_tab.py); BACK shuts it
    Up / Down, Left / Right     as GUN SETTINGS (tune_tab.py), over one subject,
                                "overlays", and two switches, each OFF or ON:
                                  monster vision and agro: the sight cones,
                                    the agro log, the wanderers' numbers
                                    (the GameState's DebugMode)
                                  shot trajectory: the tracers, the impact
                                    damage, the crosshair down the sights
                                    (the GameState's DebugShots)
    FULL STATS (Enter on it,    the cheat: the player's health, stamina,
    or a click)                 hunger, thirst and warmth to their maximums

The switches are kept between sessions (tune_keep.py) and applied onto the
GameState where this machine owns it: single player, not a client of a
server. Nothing here is written to a CSV, so the tab has no save command.
"""

from graphics_menu.tune_tab import TuneTab

DEBUG_TUNE_ACTION = "debug_settings"   # the menu row that opens the tab
DEBUG_TUNE_ROW_LABEL = "Debug Settings"

DEBUG_TUNE_OPEN_VAR = "DebugTuneOpen"
DEBUG_TUNE_ROW_VAR = "DebugTuneRow"        # 0 = the subject row, 1.. = the switches
DEBUG_TUNE_PICK_VAR = "DebugTunePick"      # always 0: one subject
DEBUG_TUNE_NUDGE_VAR = "DebugTuneNudge"
# The FULL STATS row asked for (the tab's save flag), and done.
DEBUG_TUNE_SAVE_VAR = "DebugTuneCheatRequested"
DEBUG_TUNE_SAVED_VAR = "DebugTuneCheated"
DEBUG_TUNE_TOUCHED_VAR = "DebugTuneTouched"
# DebugTuneValues[s]: 0 = off, 1 = on, in DEBUG_SWITCHES' order.
DEBUG_TUNE_VALUES_VAR = "DebugTuneValues"
DEBUG_TUNE_NAMES_VAR = "DebugTuneNames"
DEBUG_TUNE_STEPS_VAR = "DebugTuneSteps"
DEBUG_TUNE_MINS_VAR = "DebugTuneMins"
DEBUG_TUNE_MAXS_VAR = "DebugTuneMaxs"

DEBUG_SUBJECT = "overlays"
# (the row's label, the GameState flag it sets: combat/game_state.py)
MONSTER_SWITCH = ("Monster vision & agro", "DebugMode")
SHOTS_SWITCH = ("Shot trajectory", "DebugShots")
DEBUG_SWITCHES = (MONSTER_SWITCH, SHOTS_SWITCH)
# A switch reads ON above this.
SWITCH_ON_ABOVE = 0.5
DEBUG_OFF_WORD, DEBUG_ON_WORD = "OFF", "ON"

FULL_STATS_LABEL = "FULL STATS"
FULL_STATS_DONE = "health, stamina, hunger, thirst and warmth filled"

DEBUG_TAB = TuneTab(
    action=DEBUG_TUNE_ACTION, open_var=DEBUG_TUNE_OPEN_VAR,
    row_var=DEBUG_TUNE_ROW_VAR, pick_var=DEBUG_TUNE_PICK_VAR,
    nudge_var=DEBUG_TUNE_NUDGE_VAR, save_var=DEBUG_TUNE_SAVE_VAR,
    saved_var=DEBUG_TUNE_SAVED_VAR, touched_var=DEBUG_TUNE_TOUCHED_VAR,
    values_var=DEBUG_TUNE_VALUES_VAR, names_var=DEBUG_TUNE_NAMES_VAR,
    steps_var=DEBUG_TUNE_STEPS_VAR, mins_var=DEBUG_TUNE_MINS_VAR,
    maxs_var=DEBUG_TUNE_MAXS_VAR,
    stat_count=len(DEBUG_SWITCHES), save_command="",
    panel="DebugTunePanel", rows_box="DebugTuneRows",
    saved_text="DebugTuneSavedText", back_widget="DebugTuneBack",
    save_widget="DebugTuneFullStats", save_label=FULL_STATS_LABEL,
    title_widget="DebugTuneTitle", hint_widget="DebugTuneHint",
    title_text="DEBUG SETTINGS",
    row_labels=(DEBUG_SUBJECT,) + tuple(label for label, _flag in DEBUG_SWITCHES),
    hint_text=("UP / DOWN  pick   ·   LEFT / RIGHT or click  switch   ·   "
               "FULL STATS  fills them"),
    saved_words=FULL_STATS_DONE, fraction_digits=0,
    words=(DEBUG_OFF_WORD, DEBUG_ON_WORD))
