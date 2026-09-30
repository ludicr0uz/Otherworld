#!/usr/bin/env python3
"""fab_index.py -- write the index of every Fab asset in the project.

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/fab_index.py

Walks /Game/Fab plus each folder recorded in fab_library.json and writes
assets/cache/fab/index.json (one asset per line, so it greps) and index.md
(a summary: the library, counts per class, and each skeleton with whether the
mannequin retarget chains apply). Agents read these instead of booting the
editor to find out what exists. Re-run it after anything is acquired.

FAB_INDEX_ROOTS (comma-separated /Game paths) overrides the folders walked,
e.g. /Game/Characters/Mannequins to try the index on stock content.
"""

import json
import os
import sys

import unreal

SCRIPTS = os.path.join(unreal.Paths.project_dir(), "Scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline import fab_library                      # noqa: E402
from asset_pipeline.fab_inventory import describe          # noqa: E402


def _log(msg):
    unreal.log_warning(f"[FAB-INDEX] {msg}")


def main():
    items = fab_library.load()
    override = os.environ.get("FAB_INDEX_ROOTS", "").strip()
    roots = ([r.strip() for r in override.split(",") if r.strip()] if override
             else fab_library.index_roots(items))
    assets = []
    for root in roots:
        found = describe(root)
        _log(f"{root}: {len(found)} assets")
        assets += found
    os.makedirs(fab_library.INDEX_DIR, exist_ok=True)
    with open(fab_library.INDEX_JSON, "w") as fh:
        fh.write("[\n" + ",\n".join(json.dumps(a, sort_keys=True) for a in assets)
                 + ("\n" if assets else "") + "]\n")
    with open(fab_library.INDEX_MD, "w") as fh:
        fh.write(fab_library.render_index_md(assets, items))
    _log(f"wrote {len(assets)} assets to {fab_library.INDEX_JSON}")
    for item in items:
        if not fab_library.is_present(item):
            _log(f"MISSING {item.name}: nothing under {item.content} -- re-add it through Fab")


main()
