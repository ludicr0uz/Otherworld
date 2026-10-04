#!/usr/bin/env python3
"""build_sound_audition.py -- one HTML page that plays every sound.

    python3 Scripts/Sound/build_sound_audition.py          # write the page
    python3 Scripts/Sound/build_sound_audition.py --open   # and open it

Writes assets/generated/sound_audition.html: the candidates by category, then
the sounds the game plays now. Run Scripts/Sound/prepare_sound_candidates.py first;
re-run this after it. See Scripts/Sound/sound_candidates/audition.py.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import audition  # noqa: E402


def main():
    path, count = audition.build()
    print(f"{count} sounds -> {path}")
    if "--open" in sys.argv[1:]:
        subprocess.run(["open", path], check=False)


if __name__ == "__main__":
    main()
