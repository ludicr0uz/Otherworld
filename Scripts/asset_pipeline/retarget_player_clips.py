#!/usr/bin/env python3
"""retarget_player_clips.py -- put the Quaternius clips on the player's body,
and nothing else.

Editor-side; swap_player_body.py runs it:

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/retarget_player_clips.py

import_quaternius.py does this as its step 2, after re-importing both
animation packs, forty guns, the survival props and the zombie from their
zips: six minutes, of which a body swap needs the 45 seconds that retarget the
clips onto the body player_body.PLAYER_BODY names. This is that step alone,
on the packs as they are already imported. With a pack missing or short of
its clips it runs import_quaternius.py whole instead.
"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("asset_pipeline", "combat")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from asset_pipeline.quaternius_paths import (                     # noqa: E402
    UAL_CHARACTERS, UAL_PACKS, pack_dir, ual_clip,
)
from asset_pipeline.ual_retarget import retarget_ual              # noqa: E402

# What import_quaternius.py asks of a pack (each ships 43 clips).
MIN_CLIPS = 43


def _log(msg):
    unreal.log_warning(f"[RETARGET] {msg}")


def imported_packs():
    """{short: {clip name: AnimSequence}} for the packs as imported, or None
    if one is missing or short of its clips."""
    eal = unreal.EditorAssetLibrary
    packs = {}
    for _stem, short, _glb in UAL_PACKS:
        prefix = f"A_{short}_"
        clips = {}
        for path in eal.list_assets(pack_dir(short), recursive=False):
            name = path.split(".")[0].rsplit("/", 1)[1]
            if not name.startswith(prefix):
                continue
            asset = eal.load_asset(path.split(".")[0])
            if isinstance(asset, unreal.AnimSequence):
                clips[name[len(prefix):]] = asset
        if len(clips) < MIN_CLIPS:
            _log(f"{short}: {len(clips)} clips imported, {MIN_CLIPS} wanted")
            return None
        packs[short] = clips
    return packs


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    whole = runpy.run_path(os.path.join(HERE, "import_quaternius.py"),
                           run_name="retarget_player_clips")
    packs = imported_packs()
    if packs is None:
        _log("the packs are not all imported: running import_quaternius.py whole")
        whole["main"]()
        return

    results = []

    def check(label, ok, detail=""):
        results.append(ok)
        unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'} {label} {detail}")

    want = sum(len(c) for c in packs.values())
    for who in UAL_CHARACTERS:
        if not unreal.EditorAssetLibrary.does_asset_exist(
                f"/Game/Sourced/Characters/Rigs/IK_{who}"):
            raise RuntimeError(f"no IK_{who}: {who} is not imported and rigged "
                               "(asset_pipeline/import_body.py)")
        worst = retarget_ual(who, packs)
        made = unreal.EditorAssetLibrary.list_assets(
            os.path.dirname(ual_clip(who, "UAL1", "x")), recursive=False)
        check(f"{who}: every UAL clip retargeted, palms within {worst:.1f} deg",
              len(made) == want, f"({len(made)}/{want})")
    whole["check_player_clips"](check)
    unreal.log_warning(f"[VERIFY] {sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
