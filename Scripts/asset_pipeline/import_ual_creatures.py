#!/usr/bin/env python3
"""Retarget the UAL clips the creatures play (the zombie's scratch) onto them.

Run inside the editor, after import_quaternius.py and build_retarget.py:

    Scripts/dev/uepy.py Scripts/asset_pipeline/import_ual_creatures.py

import_quaternius.py runs the same step at its end; this is that step alone,
without re-importing the packs.  Then rebuild the NPCs
(build_npc_blueprints.py): the zombie's controller holds the clip.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("uebp", "asset_pipeline", "forest_generator")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from asset_pipeline.ual_creatures import (                        # noqa: E402
    check_creature_clips, retarget_creatures,
)


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    retarget_creatures()
    results = []

    def check(label, ok, detail=""):
        results.append(ok)
        unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'} {label} {detail}")

    check_creature_clips(check)
    unreal.log_warning(f"[VERIFY] {sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
