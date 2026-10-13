#!/usr/bin/env python3
"""fab_raw_import.py -- import every staged raw Fab item into /Game/Fab.

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/fab_raw_import.py

Editor-side. Stage an item first: fab_raw_scan.py <item> --stage. Each item
not imported yet becomes /Game/Fab/<Name>: its textures, a static mesh per
file, a material per texture set, and an entry in fab_library.json. Lines
marked LOOK in the log are guesses or sizes a person should check.
FAB_RAW_ONLY (comma-separated item names) imports just those, again if need be.
Afterwards: uepy.py Scripts/asset_pipeline/fab_index.py. The work is fab_raw/.
"""

import os
import sys

import unreal

SCRIPTS = os.path.join(unreal.Paths.project_dir(), "Scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline.fab_raw import editor_import    # noqa: E402

editor_import.main(tuple(
    s.strip() for s in os.environ.get("FAB_RAW_ONLY", "").split(",") if s.strip()))
