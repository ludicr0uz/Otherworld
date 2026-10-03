"""The WORLD SETTINGS tab's save, run inside the game by the HUD's
ExecutePythonCommand (world_tune_consts.WORLD_TUNE_SAVE_COMMAND) on Enter.

It reads the live HUD's working table (WorldTuneValues) and writes the day's
and the night's lengths and the night's cold to world/world_tuning.csv, which world_config lays
over its literals and the next build_day_night.py bakes into
BP_DayNightCycle (and build_graphics_menu.py into the HUD's table). The time
of day is not saved: a level starts at a random one.
"""

import unreal

from graphics_menu.tune_save import _live_hud
from graphics_menu.world_tune_consts import WORLD_TUNE_VALUES_VAR
from world.world_tuning import CSV_PATH, WORLD_STATS, write_table


def save(path=CSV_PATH):
    values = [float(v) for v in _live_hud().get_editor_property(WORLD_TUNE_VALUES_VAR)]
    if len(values) != len(WORLD_STATS):
        raise RuntimeError(f"WorldTuneValues holds {len(values)} numbers, not "
                           f"{len(WORLD_STATS)}")
    write_table({st[0]: v for st, v in zip(WORLD_STATS, values) if st[0]}, path)
    unreal.log_warning(f"[TUNE] saved the day and night lengths and the night's cold to {path}; "
                       "build_day_night.py bakes them into the cycle")
    return path
