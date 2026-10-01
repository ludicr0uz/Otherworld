"""
fetch_star_catalogue.py -- rewrite Scripts/world/star_catalogue.csv from the
Yale Bright Star Catalogue (downloaded once into assets/cache/stars).

    python3 Scripts/fetch_star_catalogue.py

The CSV is committed, so this is only for rebuilding it. The night sky's
texture is drawn from it by build_day_night.py (world/star_texture.py).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from world.star_catalogue import CSV_PATH, fetch                  # noqa: E402

if __name__ == "__main__":
    print(f"{len(fetch())} stars -> {CSV_PATH}")
