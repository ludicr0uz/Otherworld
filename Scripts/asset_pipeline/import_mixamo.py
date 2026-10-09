#!/usr/bin/env python3
"""Import Mixamo downloads and animate the creatures with them.

Run inside the editor, after build_retarget.py (it needs each creature's IK
rig and blend space):

    Scripts/dev/uepy.py Scripts/asset_pipeline/import_mixamo.py

Put the downloads in assets/cache/mixamo/ first (git-ignored); the packs it
reads are mixamo_paths.PACKS.  Then:

    1. unzip each pack beside its zip                       (mixamo_import)
    2. X Bot -> SKM_XBot on SK_XBot, every clip onto SK_XBot
    3. IK_XBot, RTG_<Creature>_from_XBot, every clip retargeted
       into Mixamo/<Creature>/                               (mixamo_retarget)
    4. the creature's blend space plays the Mixamo idle/walk/run
       (mixamo_locomotion); its melee clip is NPC_VARIANTS's, so
       rebuild the NPCs afterwards: build_npc_blueprints.py
    5. the roar alone onto each of mixamo_paths.ROAR_CREATURES (the
       wendigo), for the hunt's first beat (npc/stalk.py)
    6. the player's melee set (mixamo_paths.PLAYER_CLIPS: the knife's and
       the axe's swing and ready pose) onto SK_XBot and from there onto the
       player's skeleton, into Mixamo/UEFN_Player/          (mixamo_player);
       rebuild the weapons afterwards: build_weapons_and_combat.py
    7. check it all, and log [VERIFY] lines like the suites do

A new pack is a PACKS entry; a new clip in a role is a LOCOMOTION or MELEE
edit.  Every clip of every pack is retargeted regardless of role.

Step 6 alone, which leaves the creatures' clips as they are:
import_mixamo_player.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# A live editor keeps imported modules between runs: drop the packages so an
# edit to any of their modules is what actually runs.
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("asset_pipeline", "forest_generator")]:
    del sys.modules[_name]

import unreal                                                     # noqa: E402

from asset_pipeline.mixamo_import import (                        # noqa: E402
    extract_packs, import_clips, import_xbot,
)
from asset_pipeline.mixamo_locomotion import (                    # noqa: E402
    apply_locomotion, check_mixamo_set,
)
from asset_pipeline.mixamo_paths import (                         # noqa: E402
    MELEE, MIXAMO_CREATURES, MIXAMO_ROOT, ROAR, ROAR_CREATURES, mixamo_clip,
)
from asset_pipeline.mixamo_player import import_player_set        # noqa: E402
from asset_pipeline.mixamo_retarget import (                      # noqa: E402
    build_xbot_rig, retarget_clips,
)
from forest_generator.npc_placement import NPC_VARIANTS            # noqa: E402
from forest_generator.npc_stalk import NPC_STALK_ROAR              # noqa: E402


def _creatures(check):
    packs = extract_packs()
    _mesh, skeleton = import_xbot(packs)
    clips = import_clips(packs, skeleton)
    unreal.EditorAssetLibrary.save_directory(MIXAMO_ROOT, only_if_is_dirty=False)

    rig = build_xbot_rig()
    for creature in MIXAMO_CREATURES:
        retarget_clips(rig, creature, list(clips.values()))
        apply_locomotion(creature)
    for creature in ROAR_CREATURES:
        retarget_clips(rig, creature, [clips[ROAR]])

    check("Mixamo Clips Imported", len(clips) >= 36, f"({len(clips)})")
    for creature in MIXAMO_CREATURES:
        check_mixamo_set(creature, check)
        worn = [v for v in NPC_VARIANTS if v.mesh.endswith(f"SKM_{creature}")]
        check(f"{creature} Wanderer Swings The Mixamo Attack",
              all(v.melee == mixamo_clip(creature, *MELEE) for v in worn),
              f"(NPC_VARIANTS melee: {[v.melee for v in worn]})")
    for creature in ROAR_CREATURES:
        roar = unreal.EditorAssetLibrary.load_asset(mixamo_clip(creature, *ROAR))
        mesh = unreal.EditorAssetLibrary.load_asset(
            f"/Game/Sourced/Characters/SKM_{creature}/SKM_{creature}")
        check(f"{creature} Mixamo Roar Clip On Its Skeleton",
              roar is not None
              and roar.get_editor_property("skeleton") == mesh.get_editor_property("skeleton"))
        worn = [v.key for v in NPC_VARIANTS if v.mesh.endswith(f"SKM_{creature}")]
        check(f"{creature} Wanderer Roars The Mixamo Scream",
              bool(worn) and all(NPC_STALK_ROAR.get(k) == mixamo_clip(creature, *ROAR)
                                 for k in worn),
              f"(NPC_STALK_ROAR: {NPC_STALK_ROAR})")


def main(creatures=True, player=True):
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    if not unreal.EditorAssetLibrary.does_directory_exist(MIXAMO_ROOT):
        unreal.EditorAssetLibrary.make_directory(MIXAMO_ROOT)

    results = []

    def check(label, ok, detail=""):
        results.append(ok)
        unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'} {label} {detail}")

    if creatures:
        _creatures(check)
    if player:
        import_player_set(check)
    unreal.log_warning(f"[VERIFY] {sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
