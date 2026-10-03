"""
verify_clothing.py -- read the garments and the test ones back and check them.

    python3 Scripts/dev/uepy.py Scripts/verify_clothing.py

The checks live in the clothing.verify package, one module per area; this file
runs them in order and prints the summary. Wearing (the weapon component's
graph) is checked by verify_weapons_and_combat.py, the I panel by
verify_graphics_menu.py.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("uebp", "combat", "survival", "clothing", "item_icons")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from combat.verify.common import FAIL, PASS                       # noqa: E402
from clothing.verify import SECTIONS                              # noqa: E402

for _section in SECTIONS:
    importlib.import_module(f"clothing.verify.{_section}").run()

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
