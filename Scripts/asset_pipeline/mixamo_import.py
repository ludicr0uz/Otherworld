"""mixamo_import -- unpack the cached Mixamo zips and import them: X Bot as
SKM_XBot on SK_XBot, and every clip of every pack onto SK_XBot.

One skeleton for all packs.  Unlike Meshy's creatures, Mixamo really does
share one skeleton AND one bind pose between downloads: every clip is keyed
against the character it was previewed on, and both packs ship the same
X Bot (byte-identical FBX).  So the character is imported once, and a clip
from any pack lands on the same skeleton.
"""

import os
import zipfile

import unreal

from asset_pipeline.mixamo_paths import (
    CHARACTER_FBX, MIXAMO_CACHE, PACKS, XBOT_DIR, XBOT_MESH, XBOT_SKELETON,
    clip_stem, pack_dir, source_clip,
)
from asset_pipeline.rig_util import _load, _log


def extract_packs(packs=PACKS):
    """Unzip each cached pack into a folder beside it; return {short: dir}.

    Re-extracted every run: a zip replaced by a fresh download must not be
    shadowed by the files of the old one.  A pack with no zip is a folder of
    loose FBX files by its name (mixamo_paths.PLAYER_PACKS).
    """
    out = {}
    for stem, short in packs:
        archive = os.path.join(MIXAMO_CACHE, f"{stem}.zip")
        dest = os.path.join(MIXAMO_CACHE, stem)
        if os.path.isfile(archive):
            with zipfile.ZipFile(archive) as z:
                z.extractall(dest)
        elif not os.path.isdir(dest):
            raise RuntimeError(
                f"{archive} is missing: copy the Mixamo download there "
                "(assets/cache/mixamo/, git-ignored)")
        out[short] = dest
    return out


def _import(fbx, dest_dir, name, skeleton=None):
    """One FBX through the legacy importer.  A clip when ``skeleton`` is
    given (no mesh), otherwise the character as a skeletal mesh."""
    anim = skeleton is not None
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", not anim)
    opts.set_editor_property("import_as_skeletal", True)
    opts.set_editor_property("import_animations", anim)
    # X Bot's two flat materials are not worth a folder of assets: nothing
    # ever renders SKM_XBot, it only carries the source skeleton.
    opts.set_editor_property("import_materials", False)
    opts.set_editor_property("import_textures", False)
    opts.set_editor_property("create_physics_asset", False)
    opts.set_editor_property("mesh_type_to_import",
                             unreal.FBXImportType.FBXIT_ANIMATION if anim
                             else unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    if anim:
        opts.set_editor_property("skeleton", skeleton)

    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = dest_dir
    task.destination_name = name
    task.replace_existing = True
    task.automated = True
    task.save = True
    task.options = opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return [unreal.EditorAssetLibrary.load_asset(p.split(".")[0])
            for p in task.get_editor_property("imported_object_paths") or []]


def import_xbot(pack_dirs):
    """SKM_XBot and its skeleton, renamed SK_XBot (the importer names it
    SKM_XBot_Skeleton)."""
    if not unreal.EditorAssetLibrary.does_asset_exist(XBOT_SKELETON):
        fbx = os.path.join(next(iter(pack_dirs.values())), CHARACTER_FBX)
        _import(fbx, XBOT_DIR, XBOT_MESH.rsplit("/", 1)[1])
        minted = f"{XBOT_MESH}_Skeleton"
        if not unreal.EditorAssetLibrary.rename_asset(minted, XBOT_SKELETON):
            raise RuntimeError(f"could not rename {minted} to {XBOT_SKELETON}")
    mesh = _load(XBOT_MESH)
    skel = mesh.get_editor_property("skeleton")
    if skel is None or skel.get_path_name().split(".")[0] != XBOT_SKELETON:
        raise RuntimeError(f"{XBOT_MESH} is not on {XBOT_SKELETON} "
                           f"(got {skel.get_path_name() if skel else None})")
    _log(f"X Bot: {XBOT_MESH} on {XBOT_SKELETON}")
    return mesh, skel


def import_clips(pack_dirs, skeleton):
    """Every clip FBX of every pack -> A_Mx_<Pack>_<Clip> on SK_XBot.

    Returns {(short, stem): AnimSequence}.
    """
    out = {}
    for short, folder in pack_dirs.items():
        fbxs = sorted(f for f in os.listdir(folder)
                      if f.lower().endswith(".fbx") and f != CHARACTER_FBX)
        for fbx in fbxs:
            stem = clip_stem(fbx)
            path = source_clip(short, stem)
            imported = _import(os.path.join(folder, fbx), pack_dir(short),
                               path.rsplit("/", 1)[1], skeleton=skeleton)
            clip = next((a for a in imported
                         if isinstance(a, unreal.AnimSequence)), None)
            if clip is None:
                raise RuntimeError(f"{fbx}: no AnimSequence imported")
            if clip.get_editor_property("skeleton") != skeleton:
                raise RuntimeError(f"{fbx}: imported onto the wrong skeleton")
            out[(short, stem)] = clip
        _log(f"{short}: {len(fbxs)} clips -> {pack_dir(short)}")
    return out
