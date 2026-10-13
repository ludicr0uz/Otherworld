#!/usr/bin/env python3
"""build_map_asset_browser.py -- one HTML page of every mesh in the project:
the map pieces, the weapons, the items, the clothing, the characters.

Run outside the editor:

    python3 Scripts/build_map_asset_browser.py              # scan, write the page
    python3 Scripts/build_map_asset_browser.py --open       # and open it
    python3 Scripts/build_map_asset_browser.py --no-editor  # the page again, from the last scan
    python3 Scripts/build_map_asset_browser.py --no-pictures  # scan, but draw no new picture

Three steps, and this script runs them all:

    1. scan   Scripts/scan_map_assets.py, inside the editor (uepy.py: the open
              editor if one is listening, a cold one otherwise, about a
              minute): every StaticMesh and SkeletalMesh the registry knows under /Game,
              with its triangle counts and the levels that use it
              -> assets/generated/map_assets/meshes.json
              and each mesh photographed, as base colour and normals
              (only the new and the changed ones after the first run),
              once for its picture -> assets/generated/map_assets/passes/
              and from 16 sides for its turn -> .../spin_passes/
    2. shade  map_assets/shade.py, here (Pillow + numpy): the passes lit
              into a picture -> assets/generated/map_assets/thumbs/
              and the turn into one strip -> .../spins/ (its passes deleted)
    3. page   map_assets/page.py, here
              -> assets/generated/map_assets/map_asset_browser.html

Nothing lists the meshes: a pack added to Content/ is on the page after the
next run. See Scripts/map_assets/__init__.py.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from map_assets import page, shade                                  # noqa: E402
from map_assets.paths import NO_PICTURES, OUT_DIR, SCAN_JSON        # noqa: E402

UEPY = os.path.join(HERE, "dev", "uepy.py")


def main():
    args = sys.argv[1:]
    if "--no-editor" not in args:
        os.makedirs(OUT_DIR, exist_ok=True)
        if "--no-pictures" in args:
            open(NO_PICTURES, "w").close()
        elif os.path.isfile(NO_PICTURES):
            os.remove(NO_PICTURES)
        before = os.path.getmtime(SCAN_JSON) if os.path.isfile(SCAN_JSON) else 0.0
        subprocess.run([sys.executable, UEPY, os.path.join(HERE, "scan_map_assets.py")],
                       check=True)
        if not os.path.isfile(SCAN_JSON) or os.path.getmtime(SCAN_JSON) <= before:
            sys.exit(f"the scan wrote no {SCAN_JSON}: read the editor's output above")
    elif not os.path.isfile(SCAN_JSON):
        sys.exit(f"no scan at {SCAN_JSON}: run once without --no-editor")
    with open(SCAN_JSON) as fh:
        paths = [m["path"] for m in json.load(fh)["meshes"]]
    thumbs = shade.shade_all(paths)
    # A mesh with no picture (a translucent one) has an empty turn too.
    spins = {p: name for p, name in shade.spin_all(paths).items() if p in thumbs}
    path, counts = page.build(thumbs, spins)
    print(f"{sum(counts.values())} meshes, {len(thumbs)} with a picture: "
          + ", ".join(f"{n} {c.lower()}" for c, n in counts.items()))
    print(path)
    if "--open" in args:
        subprocess.run(["open", path], check=False)


if __name__ == "__main__":
    main()
