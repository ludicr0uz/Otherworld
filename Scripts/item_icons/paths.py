"""Where the icon pipeline's files live on disk. All of it is under git-ignored
assets/: the passes are build output and so are the PNGs.
"""

import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# capture.py writes <PASSES_DIR>/<DisplayName>/{base,normal,mask}.png, depth.exr + view.json
PASSES_DIR = os.path.join(PROJECT_DIR, "assets", "generated", "item_icons")
# compose.py writes T_UI_Icon_<DisplayName>.png beside the rest of the HUD's
# artwork, and a contact sheet of them all beside the passes.
ICON_DIR = os.path.join(PROJECT_DIR, "assets", "ui")
SHEET_PATH = os.path.join(PASSES_DIR, "sheet.png")
# The names build_item_icons.py was given, for the capture: a file, because
# an editor that is already open never sees the caller's environment.
ONLY_PATH = os.path.join(PASSES_DIR, "only.txt")

# A picture of several parts (the portrait) also gets a mask of some of them,
# each alone, which light.py mends the picture by (parts.py).
PART_SEAM, PART_HAIR = "face", "hair"


def part_file(name):
    return f"part_{name}.png"
