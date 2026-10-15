"""
build_drawn_grip.py -- the drawn MetaHuman's fingers fitted to each gun's real
mesh, keyed into /Game/Sourced/MetaHuman/A_DrawnGrip (combat/drawn_grip_bake.py).

    python3 Scripts/dev/uepy.py Scripts/build_drawn_grip.py

About 7 minutes (the fit asks the gun meshes a few hundred thousand
questions), so it is not a step of the weapons build: run it after a gun's
model, a ready pose or the retarget's hands change, take the capture again
first when the wrists moved (combat/drawn_grip_bake.py says how), then run the
weapons build, whose drawn_grip step lays the clip over the fingers.
"""

import os
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS)
for _name in [m for m in sys.modules if m.split(".")[0] in ("uebp", "combat")]:
    del sys.modules[_name]

from combat.drawn_grip_bake import build_drawn_grip                # noqa: E402


def main():
    build_drawn_grip()


main()
