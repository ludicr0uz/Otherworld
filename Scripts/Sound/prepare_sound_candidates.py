#!/usr/bin/env python3
"""prepare_sound_candidates.py -- cut the downloaded packs into candidates.

    python3 Scripts/Sound/prepare_sound_candidates.py

Writes 48 kHz 16-bit WAVs into assets/generated/sound_candidates/, by
category, with a SOURCES.md. They are for listening: the game does not read
that folder. See Scripts/Sound/sound_candidates/__init__.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import build  # noqa: E402


def main():
    written = build.build()
    by_folder = {}
    for name, seconds, _channels, _src in written:
        folder = os.path.dirname(name)
        count, total = by_folder.get(folder, (0, 0.0))
        by_folder[folder] = (count + 1, total + seconds)
    for folder in sorted(by_folder):
        count, total = by_folder[folder]
        print(f"{folder:28s} {count:3d} files  {total:7.1f} s")
    print(f"{len(written)} candidates in {build.OUT_DIR}")


if __name__ == "__main__":
    main()
