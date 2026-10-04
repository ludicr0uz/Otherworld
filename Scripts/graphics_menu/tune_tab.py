"""TuneTab: what one developer tuning tab of the M panel is called -- its row
in the panel, the HUD variables, the widget names and words, and the save's Python command.

The GUN SETTINGS tab (tune_consts.GUN_TAB), the MONSTER SETTINGS tab
(monster_tune_consts.MONSTER_TAB), the WORLD SETTINGS tab
(world_tune_consts.WORLD_TAB) and the GRAPHICS SETTINGS tab
(gfx_tune_consts.GFX_TAB) are the same machine over a different table:
tune_tick's keys, nudge and save, tune_draw's panel and wbp_tune's widgets
all take a TuneTab. Only what the table is applied to differs
(tune_tick._author_apply: carried guns; monster_tune_tick: live controllers;
world_tune_tick: the day/night cycle; gfx_tune_tick: BP_GraphicsTuner).
The PLAYER SETTINGS and SOUND SETTINGS tabs (player_tune_consts.PLAYER_TAB,
sound_tune_consts.SOUND_TAB) are two more: the player's weapon component,
and the game's sound mix.

    its row in the M panel        open the tab (and shut the others). An open
                                  tab stands in place of the panel's rows
    Up / Down                     pick a row: the subject, then one per stat,
                                  then BACK
    Left / Right                  the subject row: the previous / next one;
                                  a stat: one step down / up, never under
                                  its minimum (nor, where the tab has
                                  maximums, over its maximum)
    Enter                         save the whole table to its CSV; on BACK,
                                  shut the tab: the M panel's rows return

A tab with a save_widget (GRAPHICS SETTINGS's SAVE DEFAULT) has a row for the
save instead, between the list and BACK: Enter saves only with the caret on
it, as does a click on it, and Enter on a number does nothing.

Every tab's table but GRAPHICS SETTINGS' is kept between sessions in a save
slot of its own (kept, keep_slot, built_var: tune_keep.py), which is what a
build without the Python plugin has in place of the CSV.

Constants only.
"""

from dataclasses import dataclass

TUNE_UP, TUNE_DOWN = "Up", "Down"
TUNE_LESS, TUNE_MORE = "Left", "Right"
TUNE_SAVE_KEY = "Enter"


@dataclass(frozen=True)
class TuneTab:
    action: str           # its M panel row (umg_consts.PAUSE_ROW_ACTIONS)
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
    back_widget: str      # a WBP_MenuRow under the list: BACK
    title_widget: str
    hint_widget: str
    title_text: str
    row_labels: tuple     # the subject row's, then one per stat
    hint_text: str
    saved_words: str
    fraction_digits: int = 4  # the panel's values, at most this many decimals
    maxs_var: str = ""        # per stat; "" = the tab has no maximums
    # Per cell, as values_var: is this stat the subject's own? One that is
    # not shows a dash and does not move; "" = every cell is.
    live_var: str = ""
    label_w: float = 0.0      # the rows' label column; 0 = TUNE_ROW_LABEL_W
    panel_w: float = 0.0      # 0 = TUNE_PANEL_W
    title_font: float = 0.0   # 0 = TUNE_TITLE_FONT
    # The list shows this many rows at a time behind a scroll bar, which the
    # mouse drags (tune_scroll.py); 0 = every row, no scrolling.
    visible_rows: int = 0
    corner: bool = False      # bottom right of the screen; else where the M panel is
    # A WBP_MenuRow between the list and BACK that saves, and its words;
    # "" = Enter anywhere in the list saves (and a click on the hint).
    save_widget: str = ""
    save_label: str = ""
    # The table persists between sessions through tune_keep.py: loaded over
    # the built one at BeginPlay, saved on every nudge. False = the tab has a
    # save of its own (GRAPHICS SETTINGS: gfx_save.py).
    kept: bool = True
    # Cells of values_var that are the session's alone and never read back
    # from a save (WORLD SETTINGS' hour: the live clock).
    unkept_cells: tuple = ()

    @property
    def row_count(self):
        """The rows of the list: the subject, then one per stat."""
        return 1 + self.stat_count

    @property
    def keep_slot(self):
        """The save slot a kept tab's table lives in."""
        return f"OtherworldTune_{self.action}"

    @property
    def built_var(self):
        """The HUD's copy of the built table, which a nudge never moves: what
        a save was made over (tune_keep.py)."""
        return f"{self.values_var}Built"

    @property
    def save_row(self):
        """The save row's place in the caret's order: after the list. Only
        for a tab with a save_widget."""
        return self.row_count

    @property
    def back_row(self):
        """BACK's place in the caret's order: last, after the list and the
        save row if there is one."""
        return self.row_count + (1 if self.save_widget else 0)


def save_command(module):
    """What Enter runs (PythonScriptLibrary.ExecutePythonCommand): Scripts/
    onto the path, then ``module``.save(). Only where the Python plugin runs,
    which is the editor, PIE and a -game run of the editor binary: a dev tool."""
    return ("import sys, unreal; "
            "d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()) + 'Scripts'; "
            "d in sys.path or sys.path.insert(0, d); "
            f"import {module} as t; t.save()")
