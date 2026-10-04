#!/usr/bin/env python3
"""fetch_sonniss_archive.py -- pull the wanted files out of the 2016-2019
Sonniss GDC bundles, without downloading the bundles.

    python3 Scripts/Sound/fetch_sonniss_archive.py

Writes assets/cache/sounds/sonniss_archive/<year>/<library>/. What is wanted
is the table in Scripts/Sound/sound_candidates/sonniss_archive.py; a file already
in the cache is not fetched again.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sound_candidates import sonniss_archive  # noqa: E402


def main():
    new, held = sonniss_archive.fetch()
    print(f"{new} fetched, {held} already in {sonniss_archive.OUT_DIR}")


if __name__ == "__main__":
    main()
