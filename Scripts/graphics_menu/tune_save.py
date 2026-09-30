"""The GUN TUNING tab's save, run inside the game by the HUD's
ExecutePythonCommand (tune_consts.TUNE_SAVE_COMMAND) when Enter is pressed.

It reads the live HUD's working table (TuneWeapons, TuneValues) and writes
combat/gun_tuning.csv through combat.gun_tuning, which the next
build_weapons_and_combat.py bakes into the guns. Reading needs no Instance
Editable flag; only writing a Blueprint variable from Python does.
"""

import unreal

from combat.gun_tuning import CSV_PATH, TUNE_STATS, write_table
from graphics_menu.tune_consts import HUD_CLASS_PATH, TUNE_VALUES_VAR, TUNE_WEAPONS_VAR


def _live_hud():
    """The HUD actor of the running game: an instance of our class that has a
    world and is not the class default."""
    cls = unreal.load_class(None, HUD_CLASS_PATH)
    live = [h for h in unreal.ObjectIterator(unreal.HUD)
            if h.get_class() == cls and not h.get_name().startswith("Default__")
            and h.get_world() is not None]
    if not live:
        raise RuntimeError(f"no live {HUD_CLASS_PATH} to read the tuning from")
    return live[-1]


def save(path=CSV_PATH):
    hud = _live_hud()
    guns = [str(g) for g in hud.get_editor_property(TUNE_WEAPONS_VAR)]
    values = [float(v) for v in hud.get_editor_property(TUNE_VALUES_VAR)]
    n = len(TUNE_STATS)
    if len(values) != n * len(guns):
        raise RuntimeError(f"TuneValues holds {len(values)} numbers, not "
                           f"{len(guns)} guns x {n} stats")
    rows = [(gun, {st[0]: values[w * n + s] for s, st in enumerate(TUNE_STATS)})
            for w, gun in enumerate(guns)]
    write_table(rows, path)
    unreal.log_warning(f"[TUNE] saved {len(rows)} guns to {path}; "
                       "build_weapons_and_combat.py bakes them into the guns")
    return path
