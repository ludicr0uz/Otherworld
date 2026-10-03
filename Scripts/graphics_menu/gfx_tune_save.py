"""The GRAPHICS SETTINGS tab's SAVE DEFAULT, run inside the game by the HUD's
ExecutePythonCommand (gfx_tune_consts.GFX_TUNE_SAVE_COMMAND).

It reads the live HUD's working table (GfxTuneValues) and writes all four
presets to graphics_menu/graphics_tuning.csv, the picked one marked as the
default. gfx_stats lays the file over its defaults and the next
build_graphics_menu.py bakes it into the HUD's table and BP_GraphicsTuner's:
the numbers of Low, Medium and High, what Custom starts as, and the preset a
player with no save starts on.

The look is one for all four presets and the file is read from its first
row, so the look written is the one on screen: the picked preset's. (Custom's
can differ from the others' when it comes from the player's save.)
"""

import unreal

from graphics_menu.gfx_stats import (
    CSV_PATH, LOOK_FROM, PRESET_LABELS, STAT_COUNT, write_table,
)
from graphics_menu.gfx_tune_consts import GFX_TUNE_PICK_VAR, GFX_TUNE_VALUES_VAR
from graphics_menu.tune_save import _live_hud


def save(path=CSV_PATH):
    hud = _live_hud()
    values = [float(v) for v in hud.get_editor_property(GFX_TUNE_VALUES_VAR)]
    pick = int(hud.get_editor_property(GFX_TUNE_PICK_VAR))
    if len(values) != len(PRESET_LABELS) * STAT_COUNT:
        raise RuntimeError(f"GfxTuneValues holds {len(values)} numbers, not "
                           f"{len(PRESET_LABELS)} presets x {STAT_COUNT} stats")
    if not 0 <= pick < len(PRESET_LABELS):
        raise RuntimeError(f"GfxTunePick is {pick}, not one of {PRESET_LABELS}")
    rows = [values[p * STAT_COUNT:(p + 1) * STAT_COUNT] for p in range(len(PRESET_LABELS))]
    for row in rows:
        row[LOOK_FROM:] = rows[pick][LOOK_FROM:]
    write_table(rows, pick, path)
    unreal.log_warning(f"[TUNE] saved {len(PRESET_LABELS)} graphics presets to {path}, "
                       f"default {PRESET_LABELS[pick]}; build_graphics_menu.py bakes "
                       "them into the HUD")
    return path
