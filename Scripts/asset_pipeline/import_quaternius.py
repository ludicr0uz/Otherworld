#!/usr/bin/env python3
"""Import the Quaternius packs and put their clips on the player.

Run inside the editor:

    Scripts/dev/uepy.py Scripts/asset_pipeline/import_quaternius.py

Before the weapons build, which draws the shotgun and the pistol from the gun
pack; and again after build_retarget.py, because retargeting the clips needs
the adventurer's IK rig. Without the rig, step 2 is skipped with a note and
the player crouches and lies down procedurally until it runs again.

Put the five downloads in assets/cache/quaternius/ first (git-ignored), under
the names quaternius_paths lists.  Then:

    1. each UAL GLB -> Quaternius/UAL1|UAL2: SKM_, SK_, one A_ per clip
                                                        (quaternius_import)
    2. IK_UAL1/2, RTG_Adventurer01_from_UAL1/2, every clip retargeted into
       Quaternius/UAL/Adventurer01/, palms calibrated     (ual_retarget)
    3. every gun and survival FBX -> Quaternius/Guns|Survival/SM_*
    4. the zombie -> Quaternius/Zombie/SKM_Zombie and its clips
    5. check it all, and log [VERIFY] lines like the suites do

Then rebuild the weapons (build_weapons_and_combat.py): the player's anim BP
plays the crouch and the crawl, and the shotgun and pistol are the pack's.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# A live editor keeps imported modules between runs: drop the packages so an
# edit to any of their modules is what actually runs.
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("asset_pipeline", "combat")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from asset_pipeline.quaternius_import import (                    # noqa: E402
    import_prop_packs, import_ual_packs, import_zombie,
)
from asset_pipeline.quaternius_paths import (                     # noqa: E402
    CROUCH_IDLE, CROUCH_WALK, PISTOL_MODEL, PRONE_CRAWL, SEARCH_KNEEL, SHOTGUN_MODEL,
    UAL_CHARACTERS, prop_mesh, ual_clip,
)
from asset_pipeline.rig_util import _bone_world, _load            # noqa: E402
from asset_pipeline.ual_retarget import retarget_ual              # noqa: E402
from combat.skin import SKIN_ADVENTURER                           # noqa: E402
from combat.weapon_models import PISTOL_MESH, SHOTGUN_MESH        # noqa: E402


def _extent(clip, bones):
    """(lowest, highest) z any of ``bones`` reaches over the clip."""
    length = clip.get_editor_property("sequence_length")
    zs = [_bone_world(clip, b, length * i / 8.0).z
          for i in range(9) for b in bones]
    return min(zs), max(zs)


def check_player_clips(check):
    who = UAL_CHARACTERS[0]
    wanted = {"crouch_idle": CROUCH_IDLE, "crouch_walk": CROUCH_WALK,
              "prone_crawl": PRONE_CRAWL, "search_kneel": SEARCH_KNEEL}
    for field, (short, name) in wanted.items():
        path = ual_clip(who, short, name)
        check(f"combat.skin's {field} is the {short} {name} this imported",
              getattr(SKIN_ADVENTURER, field) == path
              and unreal.EditorAssetLibrary.does_asset_exist(path),
              getattr(SKIN_ADVENTURER, field))

    head, feet = "Head", ("LeftFoot", "RightFoot")
    stand = _load(SKIN_ADVENTURER.idle)
    stand_head = _extent(stand, [head])[1]
    for field in ("crouch_idle", "crouch_walk"):
        clip = _load(getattr(SKIN_ADVENTURER, field))
        top = _extent(clip, [head])[1]
        low = _extent(clip, feet)[0]
        # 8 cm: a foot bone dips about 5 cm under its standing height as the
        # crouched step rolls from heel to toe.
        check(f"{field}: the head comes down at least 40 cm from the idle's, "
              "and the feet stay on the ground (within 8 cm)",
              stand_head - top >= 40.0 and abs(low - _extent(stand, feet)[0]) < 8.0,
              f"(head {stand_head:.0f} -> {top:.0f}, feet {low:.1f})")
    crawl = _load(SKIN_ADVENTURER.prone_crawl)
    lo, hi = _extent(crawl, [head, "Hips", *feet])
    check("prone_crawl lies flat: head, hips and feet within 60 cm of each other",
          hi - lo < 60.0, f"({lo:.0f}..{hi:.0f})")


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    packs = import_ual_packs()
    ready = [who for who in UAL_CHARACTERS if unreal.EditorAssetLibrary.does_asset_exist(
        f"/Game/Sourced/Characters/Rigs/IK_{who}")]
    for who in sorted(set(UAL_CHARACTERS) - set(ready)):
        unreal.log_warning(f"[RETARGET] note: no IK_{who} yet, so no UAL clips on it: "
                           "run build_retarget.py, then this again")
    palms = {who: retarget_ual(who, packs) for who in ready}
    props = import_prop_packs()
    zombie = import_zombie()

    results = []

    def check(label, ok, detail=""):
        results.append(ok)
        unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'} {label} {detail}")

    for short, clips in packs.items():
        check(f"{short}: every clip imported", len(clips) >= 43, f"({len(clips)})")
    for who, worst in palms.items():
        made = unreal.EditorAssetLibrary.list_assets(
            os.path.dirname(ual_clip(who, "UAL1", "x")), recursive=False)
        want = sum(len(c) for c in packs.values())
        check(f"{who}: every UAL clip retargeted, palms within {worst:.1f} deg",
              len(made) == want, f"({len(made)}/{want})")
    if UAL_CHARACTERS[0] in palms:
        check_player_clips(check)

    for short, (fbxs, meshes) in props.items():
        check(f"{short}: every FBX of the pack is a static mesh",
              fbxs > 0 and len(meshes) == fbxs, f"({len(meshes)}/{fbxs})")
    for (short, stem), used in ((SHOTGUN_MODEL, SHOTGUN_MESH),
                                (PISTOL_MODEL, PISTOL_MESH)):
        check(f"combat.weapon_models draws {stem} from {short}",
              used == prop_mesh(short, stem)
              and unreal.EditorAssetLibrary.does_asset_exist(used), used)
    check("Zombie: the character and its clips", len(zombie) >= 1,
          f"({len(zombie)} clips)")
    unreal.log_warning(f"[VERIFY] {sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
