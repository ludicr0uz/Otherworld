"""TuneTab: what one developer tuning tab of the M panel is called -- its key,
the HUD variables, the widget names and words, and the save's Python command.

The GUN TUNING tab (tune_consts.GUN_TAB) and the MONSTER TUNING tab
(monster_tune_consts.MONSTER_TAB) are the same machine over a different
table: tune_tick's keys, nudge and save, tune_draw's panel and wbp_tune's
widgets all take a TuneTab. Only what the table is applied to differs
(tune_tick._author_apply: carried guns; monster_tune_tick: live controllers).

    [key] with the M panel open   open / close the tab (and shut the other)
    Up / Down                     pick a row: the subject, then one per stat
    Left / Right                  the subject row: the previous / next one;
                                  a stat: one step down / up, never under
                                  its minimum
    Enter                         save the whole table to its CSV

Constants only.
"""

from dataclasses import dataclass

TUNE_UP, TUNE_DOWN = "Up", "Down"
TUNE_LESS, TUNE_MORE = "Left", "Right"
TUNE_SAVE_KEY = "Enter"


@dataclass(frozen=True)
class TuneTab:
    key: str
    # The HUD's variables. The keys only raise the nudge and save flags and
    # Tick serves them, so a probe can tune and save without a keyboard.
    open_var: str
    row_var: str          # 0 = the subject row, 1.. = the stats
    pick_var: str         # index into names_var: the subject shown
    nudge_var: str        # -1 / +1 asked for this Tick, 0 = none
    save_var: str
    saved_var: str        # the last save succeeded, nothing moved since
    touched_var: str      # something was tuned: apply every Tick
    values_var: str       # values[subject * stat_count + stat]
    names_var: str        # the subjects, in table order
    steps_var: str        # per stat
    mins_var: str         # per stat
    stat_count: int
    save_command: str
    # WBP_PauseMenu's widgets and words.
    panel: str
    rows_box: str
    saved_text: str
    title_widget: str
    hint_widget: str
    title_text: str
    row_labels: tuple     # the subject row's, then one per stat
    hint_text: str
    saved_words: str

    @property
    def row_count(self):
        return 1 + self.stat_count


def save_command(module):
    """What Enter runs (PythonScriptLibrary.ExecutePythonCommand): Scripts/
    onto the path, then ``module``.save(). Only where the Python plugin runs,
    which is the editor, PIE and a -game run of the editor binary: a dev tool."""
    return ("import sys, unreal; "
            "d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()) + 'Scripts'; "
            "d in sys.path or sys.path.insert(0, d); "
            f"import {module} as t; t.save()")
