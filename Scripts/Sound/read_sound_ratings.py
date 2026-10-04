#!/usr/bin/env python3
"""read_sound_ratings.py -- copy the audition page's ratings and notes out of
Chrome into assets/generated/, and print what changed since the last copy.

    python3 Scripts/Sound/read_sound_ratings.py

See Scripts/Sound/sound_candidates/ratings.py.
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import ratings  # noqa: E402


def main():
    rated, notes, changed = ratings.read()
    print(f"{len(rated)} ratings, {len(notes)} notes: {dict(collections.Counter(rated.values()))}")
    print(f"{len(changed)} changed since the last read:")
    for take in changed:
        note = f"  -- {notes[take]}" if take in notes else ""
        print(f"  {take.replace('sound_candidates/', ''):58s} {rated.get(take, 'cleared')}{note}")


if __name__ == "__main__":
    main()
