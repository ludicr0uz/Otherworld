"""Where the browser's files live on disk. Both are build output, under
git-ignored assets/.
"""

import hashlib
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT_DIR = os.path.join(PROJECT_DIR, "assets", "generated", "map_assets")
# inventory.py writes it, page.py reads it: one dict per mesh, and when.
SCAN_JSON = os.path.join(OUT_DIR, "meshes.json")
PAGE_HTML = os.path.join(OUT_DIR, "map_asset_browser.html")
# build_map_asset_browser.py --no-pictures leaves this for the scan to find.
NO_PICTURES = os.path.join(OUT_DIR, "no_pictures")
# thumbs.py writes two passes per mesh (pass_file), shade.py one picture
# (thumb_file), and the page shows the pictures from the folder beside it.
PASSES_DIR = os.path.join(OUT_DIR, "passes")
THUMB_DIR = os.path.join(OUT_DIR, "thumbs")


def _key(path):
    return hashlib.sha1(path.encode()).hexdigest()[:16]


def pass_file(path, name):
    """The file of one pass ("base", "normal") of the mesh at a /Game path."""
    return f"{_key(path)}_{name}.png"


def thumb_file(path):
    return f"{_key(path)}.png"
