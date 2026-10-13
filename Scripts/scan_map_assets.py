"""scan_map_assets.py -- list every static mesh in the project, with its triangles.

    python3 Scripts/dev/uepy.py Scripts/scan_map_assets.py

The editor's half of Scripts/build_map_asset_browser.py, which runs this and
writes the page: run that one. Writes map_assets/paths.SCAN_JSON, then each
mesh's passes for its picture (map_assets/thumbs.py), unless that script left
the NO_PICTURES file: a file, because an editor that is already open never
sees the caller's environment.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _name in [m for m in sys.modules if m.split(".")[0] == "map_assets"]:
    del sys.modules[_name]

from map_assets import thumbs                                       # noqa: E402
from map_assets.inventory import scan                               # noqa: E402
from map_assets.paths import NO_PICTURES                            # noqa: E402


def main():
    meshes = scan()
    if not os.path.isfile(NO_PICTURES):
        thumbs.render([m["path"] for m in meshes])


main()
