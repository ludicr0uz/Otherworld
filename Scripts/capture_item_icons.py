"""capture_item_icons.py -- photograph every item's 3D model for its icon.

    python3 Scripts/dev/uepy.py Scripts/capture_item_icons.py

The editor's half of Scripts/build_item_icons.py, which runs this, composes the
icons and imports them: run that one. It limits this to the names it was
given by writing them to item_icons/paths.ONLY_PATH (comma-separated).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m.split(".")[0] == "item_icons"]:
    del sys.modules[_name]

from item_icons.capture import capture_all                          # noqa: E402
from item_icons.paths import ONLY_PATH                              # noqa: E402
from item_icons.portrait import PORTRAIT                            # noqa: E402
from item_icons.portrait_capture import capture_portrait            # noqa: E402


def main():
    only = ()
    if os.path.isfile(ONLY_PATH):
        with open(ONLY_PATH) as fh:
            only = tuple(n for n in fh.read().strip().split(",") if n)
    capture_all(only)
    if not only or PORTRAIT in only:
        capture_portrait()


main()
