"""
build_day_night.py -- the day/night cycle: the star map, the sky material,
BP_DayNightCycle, and one cycle actor in every generated level.

    python3 Scripts/dev/uepy.py Scripts/build_day_night.py

Run after any import_<Level>.py (which rebuilds the level from scratch and so
drops the cycle actor). The settings are in Scripts/world/world_config.py.
"""

import os
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS)
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("uebp", "combat", "world", "forest_generator", "survival")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from combat.graph import BGE, _create_blueprint                   # noqa: E402
from world.day_night_blueprint import (                           # noqa: E402
    apply_config, build_components, declare_variables,
)
from world.day_night_graph import build_graph                     # noqa: E402
from world.level_placement import place_day_night                 # noqa: E402
from world.night_cold import author_night_cold                    # noqa: E402
from world.paths import DAY_NIGHT_BP_PATH                         # noqa: E402
from world.sky_material import build_sky_material                 # noqa: E402
from world.star_texture import build_star_texture                 # noqa: E402

LEVELS = sorted(
    f"/Game/Maps/{name}"
    for name in os.listdir(os.path.join(_SCRIPTS, "generated_levels"))
    if unreal.EditorAssetLibrary.does_asset_exist(f"/Game/Maps/{name}"))


def build_blueprint():
    bp = _create_blueprint(DAY_NIGHT_BP_PATH, unreal.Actor)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    build_components(bp)
    declare_variables(ed)
    author_night_cold(ed, *build_graph(bp, ed))
    apply_config(bp)          # compiles, saves, reads the defaults back
    return bp


def main():
    build_star_texture()
    build_sky_material()
    build_blueprint()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    was_open = world.get_path_name().split(".")[0] if world else None
    for level in LEVELS:
        place_day_night(level)
    if was_open and LEVELS and was_open != LEVELS[-1]:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(was_open)


if __name__ == "__main__":
    main()
