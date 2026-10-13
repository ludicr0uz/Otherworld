"""
build_title_level.py -- the title level: the stage the game opens on, where
the menu stands over the character in its saved gear (Scripts/title).

    python3 Scripts/dev/uepy.py Scripts/build_title_level.py

The menu over it, and the figure's dressing, are build_graphics_menu.py's.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m.split(".")[0] in ("title", "forest_generator", "forest_import")]:
    del sys.modules[_name]

from title import stage                                           # noqa: E402


def main():
    stage.open_level()
    stage.place_floor()
    stage.plant_trees()
    stage.place_lights()
    stage.place_camera()
    stage.place_player_start()
    stage.save()


if __name__ == "__main__":
    main()
