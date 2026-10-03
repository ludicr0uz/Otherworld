"""The SOUND SETTINGS tab's save, run inside the game by the HUD's
ExecutePythonCommand (sound_tune_consts.SOUND_TUNE_SAVE_COMMAND) on Enter.

It reads the live HUD's working table (SoundTuneValues) and writes each
sound's volume to combat/sound_tuning.csv, which the next
build_graphics_menu.py bakes into the HUD's table: the volumes a game
starts with.
"""

import unreal

from combat.sound_tuning import CSV_PATH, SOUND_STATS, write_table
from graphics_menu.sound_tune_consts import SOUND_TUNE_VALUES_VAR
from graphics_menu.tune_save import _live_hud


def save(path=CSV_PATH):
    values = [float(v) for v in _live_hud().get_editor_property(SOUND_TUNE_VALUES_VAR)]
    if len(values) != len(SOUND_STATS):
        raise RuntimeError(f"SoundTuneValues holds {len(values)} numbers, not "
                           f"{len(SOUND_STATS)}")
    write_table({st[0]: v for st, v in zip(SOUND_STATS, values)}, path)
    unreal.log_warning(f"[TUNE] saved the sounds' volumes to {path}; "
                       "build_graphics_menu.py bakes them into the HUD")
    return path
