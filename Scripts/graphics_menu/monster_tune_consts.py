"""The M panel's MONSTER TUNING tab: its key, the HUD's variables, the widget
names and words, and the Python command its save runs. Constants only, so
wbp_tune (the layout), monster_tune_tick and tune_draw (the graph),
monster_tune_save (the save, run inside the game) and monster_tune_checks
read one table.

    [N] with the M panel open   open / close the tab (and shut GUN TUNING)
    Up / Down, Left / Right,    as GUN TUNING (tune_tab.py), over the
    Enter                       creatures instead of the guns; Enter saves
                                npc/monster_tuning.csv

The stats, their steps and minimums are npc/monster_tuning.MONSTER_STATS;
each is a Tune* variable on every creature's AI controller (npc/tuned.py).
"""

from forest_generator.npc_placement import NPC_VARIANTS
from graphics_menu.tune_tab import TuneTab, save_command
from npc.monster_tuning import MONSTER_STATS

MON_TUNE_KEY = "N"
MON_TUNE_ROW_LABEL = f"[{MON_TUNE_KEY}]   monster tuning"

MON_TUNE_OPEN_VAR = "MonTuneOpen"
MON_TUNE_ROW_VAR = "MonTuneRow"            # 0 = the creature row, 1.. = MONSTER_STATS
MON_TUNE_CREATURE_VAR = "MonTuneCreature"  # index into MonTuneCreatures
MON_TUNE_NUDGE_VAR = "MonTuneNudge"
MON_TUNE_SAVE_VAR = "MonTuneSaveRequested"
MON_TUNE_SAVED_VAR = "MonTuneSaved"
MON_TUNE_TOUCHED_VAR = "MonTuneTouched"
# MonTuneValues[c * MON_STAT_COUNT + s] is creature c's stat s. Seeded from
# the built monster_specs (so monster_tuning.csv).
MON_TUNE_VALUES_VAR = "MonTuneValues"
MON_TUNE_CREATURES_VAR = "MonTuneCreatures"  # NPC_VARIANTS' keys, in order
MON_TUNE_STEPS_VAR = "MonTuneSteps"
MON_TUNE_MINS_VAR = "MonTuneMins"

MON_STAT_COUNT = len(MONSTER_STATS)
MON_CREATURES = tuple(v.key for v in NPC_VARIANTS)
# Each creature's controller class, which the HUD writes the table onto.
MON_CONTROLLERS = tuple(
    (v.key, v.ai_blueprint,
     f"{v.ai_blueprint}.{v.ai_blueprint.rsplit('/', 1)[-1]}_C") for v in NPC_VARIANTS)

MON_TUNE_SAVE_COMMAND = save_command("graphics_menu.monster_tune_save")

MONSTER_TAB = TuneTab(
    key=MON_TUNE_KEY, open_var=MON_TUNE_OPEN_VAR, row_var=MON_TUNE_ROW_VAR,
    pick_var=MON_TUNE_CREATURE_VAR, nudge_var=MON_TUNE_NUDGE_VAR,
    save_var=MON_TUNE_SAVE_VAR, saved_var=MON_TUNE_SAVED_VAR,
    touched_var=MON_TUNE_TOUCHED_VAR, values_var=MON_TUNE_VALUES_VAR,
    names_var=MON_TUNE_CREATURES_VAR, steps_var=MON_TUNE_STEPS_VAR,
    mins_var=MON_TUNE_MINS_VAR, stat_count=MON_STAT_COUNT,
    save_command=MON_TUNE_SAVE_COMMAND,
    panel="MonTunePanel", rows_box="MonTuneRows", saved_text="MonTuneSavedText",
    title_widget="MonTuneTitle", hint_widget="MonTuneHint",
    title_text="MONSTER TUNING",
    row_labels=("creature",) + tuple(s[2] for s in MONSTER_STATS),
    hint_text=("UP / DOWN  pick   ·   LEFT / RIGHT  change   ·   "
               "ENTER  save to monster_tuning.csv"),
    saved_words="saved to Scripts/npc/monster_tuning.csv")
