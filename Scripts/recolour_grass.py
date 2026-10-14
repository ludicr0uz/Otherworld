"""Give the grass of every level that has the dark colour but not the patch
the dark instance, in place (forest_import/grass_recolour.py).

    python3 Scripts/dev/uepy.py Scripts/recolour_grass.py

A level with the patch is planted again by its import instead. Regenerate
the level's scripts after a change to its specs, so they say the same.
"""

import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
for _name in [n for n in sys.modules
              if n.split(".")[0] in ("forest_generator", "forest_import", "world")]:
    del sys.modules[_name]

from forest_generator.grass_look import DARK_GRASS_LEVELS, PATCH_GRASS_LEVELS  # noqa: E402
from forest_import import grass_recolour  # noqa: E402


def main():
    for level in DARK_GRASS_LEVELS:
        if level not in PATCH_GRASS_LEVELS:
            grass_recolour.recolour(level)


if __name__ == "__main__":
    main()
