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


LFS_POINTER = b"version https://git-lfs"
FIX = ("re-save through world/level_save.py (any of build_survival.py, "
       "build_day_night.py) or re-import the level")


def scan():
    """[(path, state)] for each map on disk: state is "navmesh", "ok", or
    "pointer" (a Git LFS pointer whose bytes were never pulled: unknown)."""
    found = []
    for path in sorted(glob.glob(MAPS)):
        with open(path, "rb") as f:
            data = f.read()
        if data.startswith(LFS_POINTER):
            found.append((path, "pointer"))
        else:
            found.append((path, "navmesh" if MARK in data else "ok"))
    return found


def main():
    labels = {"navmesh": "SAVED NAVMESH", "ok": "ok", "pointer": "LFS pointer"}
    bad = []
    for path, state in scan():
        print(f"{labels[state]:<14} {os.path.basename(path)}")
        if state == "navmesh":
            bad.append(path)
    if bad:
        print(FIX)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
