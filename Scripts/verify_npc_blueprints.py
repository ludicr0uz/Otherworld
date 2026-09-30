"""
verify_npc_blueprints.py -- read the wanderers' controllers back and check
their patrol and agro against forest_generator/npc_agro.py.

    python3 Scripts/dev/uepy.py Scripts/verify_npc_blueprints.py

The chase and melee are checked by the level verifier; the checks here live in
Scripts/npc/verify.py (patrol, agro, corpse, guard) and Scripts/npc/verify_tree.py
(the Blackboard, the Behavior Trees and their steps).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m == "npc" or m.startswith("npc.")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from npc.verify import FAIL, PASS, run                            # noqa: E402
from npc.verify_tree import run as run_tree                       # noqa: E402

run()
run_tree()
unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
