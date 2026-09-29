#!/usr/bin/env python3
"""build_survival_icons.py -- draw the mushroom and canteen inventory icons.

Run outside the editor (Pillow), then import them with the rest of the UI art:

    python3 Scripts/build_survival_icons.py
    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/import_ui_art.py

Writes to assets/ui/ next to build_ui_art.py's PNGs; import_ui_art.py imports
every PNG in that folder, so nothing else has to know these exist. The code is
survival/icon_art.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from survival.icon_art import OUT_DIR, write_icons                  # noqa: E402

if __name__ == "__main__":
    made = write_icons()
    print(f"wrote {len(made)} PNGs to {OUT_DIR}: {', '.join(made)}")
