"""
verify_day_night.py -- read the saved day/night assets back and check them.

    python3 Scripts/dev/uepy.py Scripts/verify_day_night.py

The checks live in the world.verify package, one module per area; this file
runs them in order and prints the summary.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("uebp", "combat", "world", "forest_generator")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from combat.verify.common import FAIL, PASS                       # noqa: E402
from world.verify import SECTIONS                                 # noqa: E402

for _section in SECTIONS:
    importlib.import_module(f"world.verify.{_section}").run()

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
