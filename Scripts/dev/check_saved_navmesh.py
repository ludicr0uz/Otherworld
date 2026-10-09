#!/usr/bin/env python3
"""Do the generated maps on disk carry a saved navmesh? Run before packaging.

    python3 Scripts/dev/check_saved_navmesh.py

A RecastNavMesh saved into a map is loaded by the game and never built, so
the wanderers stand still in a packaged or -game run (Scripts/world/
level_save.py). The editor cannot be asked: it re-creates the actor on open.
So this reads each .umap's bytes for the actor's name and changes nothing.
Exit status 1 if any map has one.
"""

import glob
import os
import sys

MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                    "Content", "Maps", "Lvl_*.umap")
MARK = b"RecastNavMesh-Default"


def main():
    bad = []
    for path in sorted(glob.glob(MAPS)):
        with open(path, "rb") as f:
            found = MARK in f.read()
        print(f"{'SAVED NAVMESH' if found else 'ok           '}  {os.path.basename(path)}")
        if found:
            bad.append(path)
    if bad:
        print("re-save these through world/level_save.py (any of build_survival.py, "
              "build_day_night.py) or re-import the level")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
