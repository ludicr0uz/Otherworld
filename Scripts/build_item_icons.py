#!/usr/bin/env python3
"""build_item_icons.py -- render every item's inventory icon from its 3D model.

Run outside the editor (the compose step needs Pillow and numpy, which the
editor's embedded Python does not have):

    python3 Scripts/build_item_icons.py              # every item
    python3 Scripts/build_item_icons.py Axe Wood     # only these
    python3 Scripts/build_item_icons.py Character    # the I panel's portrait

Three steps, and this script runs all of them:

    1. capture   Scripts/capture_item_icons.py, inside the editor (uepy.py):
                 each item's model, alone, as base colour + normals + mask
                 + depth
                 -> assets/generated/item_icons/<DisplayName>/
    2. compose   item_icons/light.py and compose.py, here: lit as a studio
                 shot, levelled, fitted to 128 x 64, contoured in black
                 -> assets/ui/T_UI_Icon_<DisplayName>.png, and a contact sheet
                 of them all at assets/generated/item_icons/sheet.png
    3. import    Scripts/asset_pipeline/import_ui_art.py, inside the editor
                 -> /Game/UI/Art

--no-editor does step 2 alone, on the passes already captured: for tuning the
light in item_icons/light.py, which needs no editor.

An item is added in item_icons/items.py. On a fresh clone the items are built
before their icons can be (the icon is a picture of the built item), so run
the weapons and survival builds again after this.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from item_icons.compose import compose_all                          # noqa: E402
from item_icons.items import DISPLAYS                               # noqa: E402
from item_icons.paths import ICON_DIR, SHEET_PATH                   # noqa: E402
from item_icons.portrait import PORTRAIT                            # noqa: E402

UEPY = os.path.join(HERE, "dev", "uepy.py")


def _in_editor(script, **env):
    subprocess.run([sys.executable, UEPY, os.path.join(HERE, script)],
                   check=True, env={**os.environ, **env})


def main(argv):
    editor = "--no-editor" not in argv
    only = tuple(a for a in argv if not a.startswith("--"))
    unknown = [n for n in only if n not in DISPLAYS + (PORTRAIT,)]
    if unknown:
        sys.exit(f"no such item: {', '.join(unknown)} "
                 f"(items: {', '.join(DISPLAYS)}, and {PORTRAIT})")

    if editor:
        _in_editor("capture_item_icons.py", ITEM_ICONS_ONLY=",".join(only))
    made = compose_all(only)
    print(f"wrote {len(made)} icons to {ICON_DIR}: {', '.join(made)}", flush=True)
    print(f"contact sheet: {SHEET_PATH}", flush=True)
    if not made:
        sys.exit("no item was captured, so there is nothing to import")
    if editor:
        _in_editor(os.path.join("asset_pipeline", "import_ui_art.py"))


if __name__ == "__main__":
    main(sys.argv[1:])
