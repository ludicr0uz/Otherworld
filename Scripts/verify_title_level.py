"""
verify_title_level.py -- read the title level back and check its stage.

    python3 Scripts/dev/uepy.py Scripts/verify_title_level.py

The checks are title/checks.py's; this file runs them and prints the summary.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m.split(".")[0] in ("title", "combat")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from combat.verify.common import FAIL, PASS                       # noqa: E402
from title import checks                                          # noqa: E402

checks.run()

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
