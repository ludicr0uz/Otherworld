"""
verify_weapons_and_combat.py -- read the saved assets back and check them.

    python3 Scripts/dev/uepy.py Scripts/verify_weapons_and_combat.py
or cold:
    UnrealEditor-Cmd <uproject> \\
      -ExecutePythonScript="<abs>/Scripts/verify_weapons_and_combat.py" -NoUI -stdout

Everything here reads assets from disk rather than trusting the builder's return
values, because the failures that matter in this project are the silent ones: a
pin default that does not apply, a variable that compiles as int when it should
be a float, a rename that quietly did not happen. Each of those compiles, saves,
and looks entirely correct until something depends on it.

The checks themselves live in the combat.verify package, one module per area;
this file runs them in order and prints the summary.
"""

import importlib
import os
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS)

# A live editor keeps imported modules between runs, and combat.verify.fixtures
# holds assets loaded at import: without this a second run would check the
# first run's objects, and an edit to any combat module would be ignored.
for _name in [m for m in sys.modules if m.split(".")[0] in ("combat", "loot")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from combat.verify import SECTIONS                                # noqa: E402
from combat.verify.common import FAIL, PASS                       # noqa: E402

for _section in SECTIONS:
    importlib.import_module(f"combat.verify.{_section}").run()

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
