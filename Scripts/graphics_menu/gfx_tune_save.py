"""The GRAPHICS TUNING tab's save, run inside the game by the HUD's
ExecutePythonCommand (gfx_tune_consts.GFX_TUNE_SAVE_COMMAND) on Enter.

It reads the live HUD's working table (GfxTuneValues) and writes all four
presets to graphics_menu/graphics_tuning.csv, which gfx_stats lays over its
defaults and the next build_graphics_menu.py bakes into the HUD's table and
BP_GraphicsTuner's.
"""

import unreal

from graphics_menu.gfx_stats import CSV_PATH, PRESET_LABELS, STAT_COUNT, write_table
from graphics_menu.gfx_tune_consts import GFX_TUNE_VALUES_VAR
from graphics_menu.tune_save import _live_hud


def save(path=CSV_PATH):
    values = [float(v) for v in _live_hud().get_editor_property(GFX_TUNE_VALUES_VAR)]
    if len(values) != len(PRESET_LABELS) * STAT_COUNT:
        raise RuntimeError(f"GfxTuneValues holds {len(values)} numbers, not "
                           f"{len(PRESET_LABELS)} presets x {STAT_COUNT} stats")
    write_table([values[p * STAT_COUNT:(p + 1) * STAT_COUNT]
                 for p in range(len(PRESET_LABELS))], path)
    unreal.log_warning(f"[TUNE] saved {len(PRESET_LABELS)} graphics presets to {path}; "
                       "build_graphics_menu.py bakes them into the HUD")
    return path
