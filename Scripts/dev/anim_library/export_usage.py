"""export_usage.py -- which clips the game uses, from the asset registry.

    python3 Scripts/dev/uepy.py --cold --summary Scripts/dev/anim_library/export_usage.py

Needs export_poses.py's rows.jsonl. Writes Saved/AnimLibrary/usage.json:
{clip id: {"game": [game assets that reference it], "reach": [what the player's
motion-matching graph reaches it through]}}. build_library.py adds the clips
the code names (a copy of a clip counts for its source) and writes the
catalogue's "used" levels.

    game   a referencer outside the sample/library folders: the weapons
           component, a creature's blend space, a Blueprint of ours.
    reach  a referencer the player's anim Blueprint can reach (its choosers
           and their pose-search databases): in the pool the motion matching
           chooses from, not necessarily playing.
"""
import json
import os

import unreal

LIB = os.path.join(unreal.Paths.project_dir(), "Saved", "AnimLibrary")
PLAYER_ABP = "/Game/GAS/Blueprints/SandboxCharacter_CMC_ABP"
# Not ours: the libraries and the samples' own assets.
LIBRARY_ROOTS = ("/Game/GAS/", "/Game/Sourced/Lyra/", "/Game/Sourced/Quaternius/",
                 "/Game/Sourced/Mixamo/", "/Game/Sourced/MetaHuman/", "/Game/MetaHumans/",
                 "/Game/Fab/", "/Game/Tmp/", "/Game/AnimStarterPack/",
                 "/Game/FreeAnimationLibrary/", "/Game/FreeLadderAnimationSet/",
                 "/Game/FP_AKS74U_Animation/", "/Game/Survival_Character/",
                 "/Game/PN_GrassLibrary/")
DEPTH = 7


def main():
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    q = unreal.AssetRegistryDependencyOptions()
    q.include_hard_package_references = True
    q.include_soft_package_references = True
    q.include_searchable_names = False
    q.include_soft_management_references = False
    q.include_hard_management_references = False

    reach, frontier = {PLAYER_ABP}, [PLAYER_ABP]
    for _ in range(DEPTH):
        nxt = []
        for p in frontier:
            for d in reg.get_dependencies(p, q) or []:
                d = str(d)
                if d.startswith("/Game") and d not in reach:
                    reach.add(d)
                    nxt.append(d)
        frontier = nxt
    unreal.log_warning(f"[ANIMLIB] the player's graph reaches {len(reach)} assets")

    out = {}
    rows = [json.loads(l) for l in open(os.path.join(LIB, "rows.jsonl")) if l.strip()]
    for r in rows:
        game, via = [], []
        for ref in sorted(str(x) for x in (reg.get_referencers(r["path"], q) or [])):
            if not ref.startswith("/Game") or ref == r["path"]:
                continue
            if ref in reach:
                via.append(ref)
            elif not ref.startswith(LIBRARY_ROOTS):
                game.append(ref)
        if game or via:
            out[r["id"]] = {"game": game, "reach": via}
    with open(os.path.join(LIB, "usage.json"), "w") as f:
        json.dump(out, f)
    unreal.log_warning(f"[ANIMLIB] usage for {len(out)} of {len(rows)} clips")


main()
