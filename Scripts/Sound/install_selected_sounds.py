#!/usr/bin/env python3
"""install_selected_sounds.py -- write the chosen takes to
assets/generated/sounds/, as the sounds the game plays.

    python3 Scripts/Sound/install_selected_sounds.py

Then run Scripts/build_sound.py (in the editor: uepy.py), which imports them. What is chosen is the table
in Scripts/Sound/sound_candidates/selection.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import install  # noqa: E402


def main():
    written = install.install()
    for name, seconds, source in written:
        print(f"{name:22s} {seconds:6.2f} s  {source}")
    print(f"{len(written)} sounds in {install.SOUND_DIR}")


if __name__ == "__main__":
    main()
