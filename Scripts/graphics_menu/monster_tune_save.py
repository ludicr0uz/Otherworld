"""The MONSTER SETTINGS tab's save, run inside the game by the HUD's
ExecutePythonCommand (monster_tune_consts.MON_TUNE_SAVE_COMMAND) on Enter.

It reads the live HUD's working table (MonTuneCreatures, MonTuneValues) and
writes npc/monster_tuning.csv, which the next build_npc_blueprints.py bakes
into the controllers' Tune* defaults (and build_graphics_menu.py into the
HUD's table).
"""

import unreal

from graphics_menu.monster_tune_consts import MON_TUNE_CREATURES_VAR, MON_TUNE_VALUES_VAR
from graphics_menu.tune_save import _live_hud
from npc.monster_tuning import CSV_PATH, MONSTER_STATS, write_table


def save(path=CSV_PATH):
    hud = _live_hud()
    creatures = [str(c) for c in hud.get_editor_property(MON_TUNE_CREATURES_VAR)]
    values = [float(v) for v in hud.get_editor_property(MON_TUNE_VALUES_VAR)]
    n = len(MONSTER_STATS)
    if len(values) != n * len(creatures):
        raise RuntimeError(f"MonTuneValues holds {len(values)} numbers, not "
                           f"{len(creatures)} creatures x {n} stats")
    rows = [(key, {st[0]: values[c * n + s] for s, st in enumerate(MONSTER_STATS)})
            for c, key in enumerate(creatures)]
    write_table(rows, path)
    unreal.log_warning(f"[TUNE] saved {len(rows)} creatures to {path}; "
                       "build_npc_blueprints.py bakes them into the wanderers")
    return path
