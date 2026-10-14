"""Build the grass patch the 200 m level plants (forest_import/grass_patch.py):
copies of the library clump merged into one mesh, with its own pivot textures
so it sways by the pack's wind.

    python3 Scripts/dev/uepy.py Scripts/build_grass_patch.py

Run it again after a change to forest_generator/grass_patch.py; the level's
import plants the mesh and does not build it.
"""

import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
for _name in [n for n in sys.modules
              if n.split(".")[0] in ("forest_generator", "forest_import", "world")]:
    del sys.modules[_name]

from forest_import import grass_look, grass_patch  # noqa: E402


def main():
    grass_look.ensure_grass_look()      # the patch's material is its child
    grass_patch.build_grass_patch()


if __name__ == "__main__":
    main()
