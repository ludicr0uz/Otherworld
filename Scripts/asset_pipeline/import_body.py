#!/usr/bin/env python3
"""import_body.py -- bring newly generated bodies all the way in, and no others.

Editor-side, after fetch_monsters.py has cached a new character:

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_body.py

Every catalog character that is cached but has no mesh in Content/ yet goes
through the three steps a body needs before anything can wear it, in order:

    import_characters        mesh, skeleton, physics bodies (the reference's,
                             for a body that names compatible_with)
    build_creature_materials its material instance
    build_retarget           fingers, IK rig, retargeter, clips, anim BP

The characters already imported are left exactly as they are: a re-import
replaces a mesh and drops the fingers the retarget added, and a retarget
regenerates clips the built Blueprints hold. ``main(only={"adventurer_02"})``
does the named ids again, whatever is there.
"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import unreal                                                     # noqa: E402

from asset_pipeline import catalog, player_body                   # noqa: E402


def _step(script):
    """A sibling entry point's namespace. Loaded by path, not imported: each
    purges the asset_pipeline package as it loads, which an import of it from
    inside the package cannot survive."""
    return runpy.run_path(os.path.join(HERE, script), run_name="import_body")


def missing():
    """The ids of the catalog characters with a rig cached and no mesh yet."""
    cache = os.path.join(unreal.Paths.project_dir(), "assets", "cache", "meshy")
    out = set()
    for spec in catalog.CHARACTERS:
        name = player_body.name_of(spec.id)
        cached = os.path.isdir(os.path.join(cache, spec.id, "rigged"))
        if cached and not unreal.EditorAssetLibrary.does_asset_exist(
                f"/Game/Sourced/Characters/SKM_{name}/SKM_{name}"):
            out.add(spec.id)
    return out


def main(only=None):
    ids = set(only) if only else missing()
    if not ids:
        unreal.log_warning("[IMPORT] every cached character is already imported")
        return
    names = {player_body.name_of(i) for i in ids}
    unreal.log_warning(f"[IMPORT] bringing in {sorted(ids)}")
    _step("import_characters.py")["main"](only=ids)
    _step("build_creature_materials.py")["main"](only=ids)
    _step("build_retarget.py")["main"](only=names)


if __name__ == "__main__":
    main()
