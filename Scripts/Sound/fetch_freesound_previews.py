#!/usr/bin/env python3
"""fetch_freesound_previews.py -- CC0 Freesound previews for the sounds the
packs do not cover, to listen to before downloading any original.

    python3 Scripts/Sound/fetch_freesound_previews.py                 # every need
    python3 Scripts/Sound/fetch_freesound_previews.py owl drinking    # these only

Writes assets/cache/sounds/freesound_previews/<need>/<id>_<author>.mp3 and an
index.json. What is searched for is the table in
Scripts/Sound/sound_candidates/freesound_previews.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import freesound_previews  # noqa: E402


def main():
    index = freesound_previews.fetch(only=tuple(sys.argv[1:]))
    print(f"{len(index)} previews in {freesound_previews.OUT_DIR}")


if __name__ == "__main__":
    main()
