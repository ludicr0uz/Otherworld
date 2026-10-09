#!/usr/bin/env python3
"""import_mixamo.py's last step alone: the player's melee set (mixamo_paths.
PLAYER_CLIPS), leaving the creatures' clips as they are.  Editor-side:

    Scripts/dev/uepy.py Scripts/asset_pipeline/import_mixamo_player.py

then build_weapons_and_combat.py, which bakes the game's clips from them
(combat/melee_clips.py).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from asset_pipeline.mixamo_player import import_player_set        # noqa: E402


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    results = []

    def check(label, ok, detail=""):
        results.append(ok)
        unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'} {label} {detail}")

    import_player_set(check)
    unreal.log_warning(f"[VERIFY] {sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
