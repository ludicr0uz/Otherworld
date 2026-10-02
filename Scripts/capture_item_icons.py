"""capture_item_icons.py -- photograph every item's 3D model for its icon.

    python3 Scripts/dev/uepy.py Scripts/capture_item_icons.py

The editor's half of Scripts/build_item_icons.py, which runs this, composes the
icons and imports them: run that one. $ITEM_ICONS_ONLY (comma-separated
DisplayNames) limits it to some items.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m.split(".")[0] == "item_icons"]:
    del sys.modules[_name]

from item_icons.capture import capture_all                          # noqa: E402


def main():
    only = tuple(n for n in os.environ.get("ITEM_ICONS_ONLY", "").split(",") if n)
    capture_all(only)


main()
