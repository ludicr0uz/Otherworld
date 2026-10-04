#!/usr/bin/env python3
"""fetch_free_packs.py -- download the small CC0 sound packs (Kenney,
OpenGameArt) into assets/cache/sounds/.

    python3 Scripts/Sound/fetch_free_packs.py

A pack already there is not fetched again. Which packs is the table in
Scripts/Sound/sound_candidates/free_packs.py, which also says what has to be
downloaded by hand.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import free_packs  # noqa: E402

if __name__ == "__main__":
    free_packs.fetch()
