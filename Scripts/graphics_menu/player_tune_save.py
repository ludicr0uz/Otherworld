"""The PLAYER SETTINGS tab's save, run inside the game by the HUD's
ExecutePythonCommand (player_tune_consts.PLAYER_TUNE_SAVE_COMMAND) on Enter.

It reads the live HUD's working table (PlayerTuneValues) and writes the jog's
and the sprint's speed and the stamina bar's two times to
combat/player_tuning.csv, which combat/tuning.py lays over its literals and
the next build_weapons_and_combat.py bakes into the character and
BP_WeaponComponent (and build_graphics_menu.py into the HUD's table).
"""

import unreal

from combat.player_tuning import CSV_PATH, PLAYER_STATS, write_table
from graphics_menu.player_tune_consts import PLAYER_TUNE_VALUES_VAR
from graphics_menu.tune_save import _live_hud


def save(path=CSV_PATH):
    values = [float(v) for v in _live_hud().get_editor_property(PLAYER_TUNE_VALUES_VAR)]
    if len(values) != len(PLAYER_STATS):
        raise RuntimeError(f"PlayerTuneValues holds {len(values)} numbers, not "
                           f"{len(PLAYER_STATS)}")
    write_table({st[0]: v for st, v in zip(PLAYER_STATS, values)}, path)
    unreal.log_warning(f"[TUNE] saved the player's speeds and stamina times to {path}; "
                       "build_weapons_and_combat.py bakes them into the player")
    return path
