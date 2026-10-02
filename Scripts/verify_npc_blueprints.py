"""
verify_npc_blueprints.py -- read the wanderers' controllers back and check
their patrol and agro against forest_generator/npc_agro.py.

    python3 Scripts/dev/uepy.py Scripts/verify_npc_blueprints.py

The chase and melee are checked by the level verifier; the checks here live in
Scripts/npc/verify.py (patrol, agro, corpse, guard) and Scripts/npc/verify_tree.py
(the Blackboard, the Behavior Trees and their steps),
Scripts/npc/verify_sight_cone.py (debug mode's sight cone),
Scripts/npc/verify_strafe.py (the step back and round between two swings) and
Scripts/npc/verify_stalk.py and verify_stalk_cover.py (the wendigo's roar,
tree-to-tree hunt and charge)
and Scripts/npc/verify_ward.py and verify_ward_roar.py (fire holding the
wendigo off, and its roars at it)
and Scripts/npc/verify_drawn.py (the fire that draws a zombie).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m == "npc" or m.startswith("npc.")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from npc.verify import FAIL, PASS, run                            # noqa: E402
from npc.verify_tree import run as run_tree                       # noqa: E402
from npc.verify_sight_cone import run as run_sight_cone           # noqa: E402
from npc.verify_strafe import run as run_strafe                   # noqa: E402
from npc.verify_stalk import run as run_stalk                     # noqa: E402
from npc.verify_ward import run as run_ward                       # noqa: E402
from npc.verify_ward_roar import run as run_ward_roar             # noqa: E402
from npc.verify_drawn import run as run_drawn                     # noqa: E402
from npc.verify_on_hit import run as run_on_hit                   # noqa: E402

run()
run_tree()
run_sight_cone()
run_strafe()
run_stalk()
run_ward()
run_ward_roar()
run_drawn()
run_on_hit()
unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
