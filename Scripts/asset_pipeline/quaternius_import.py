"""quaternius_import -- unpack the cached Quaternius zips and import them:
each UAL GLB as SKM_/SK_ plus one A_ clip per animation, each prop FBX as an
SM_ with its MI_ colours, and the zombie as a skinned, animated mesh.

Everything is imported into a staging folder and then renamed into
Quaternius/<Pack>/ with the project's prefixes.  The importers pick their own
names (UAL1_StandardCrouch_Idle_Loop, Metal, Zombie_Skeleton), and a batch
rename fixes every reference on the way, so nothing points back at staging.
A pack's folder is wiped first: it is generated in full, and the rename
refuses a name that is taken.
"""

import os
import zipfile

import unreal

from asset_pipeline.quaternius_paths import (
    PROP_PACKS, QUATERNIUS_CACHE, STAGING_DIR, UAL_PACKS, ZOMBIE_PACK,
    pack_dir,
)
from asset_pipeline.rig_util import _log

EAL = unreal.EditorAssetLibrary


def _extract(stem, members):
    """Unzip the members (files, or folders ending in /) of one cached zip
    beside it; return the folder.  Re-extracted every run, so a replaced
    download is never shadowed by the old files."""
    archive = os.path.join(QUATERNIUS_CACHE, f"{stem}.zip")
    if not os.path.isfile(archive):
        raise RuntimeError(
            f"{archive} is missing: copy the Quaternius download there "
            "(assets/cache/quaternius/, git-ignored; see quaternius_paths)")
    dest = os.path.join(QUATERNIUS_CACHE, stem)
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist()
                 if any(n == m or (m.endswith("/") and n.startswith(m))
                        for m in members)]
        if not names:
            raise RuntimeError(f"{archive} has none of {members}")
        z.extractall(dest, names)
    return dest


def _fresh(folder):
    for d in (folder, STAGING_DIR):
        if EAL.does_directory_exist(d):
            EAL.delete_directory(d)
    EAL.make_directory(folder)
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()


def _task(filename, options=None):
    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = STAGING_DIR
    task.replace_existing = True
    task.automated = True
    task.save = False
    if options is not None:
        task.options = options
    return task


def _run(tasks):
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    paths = [p for t in tasks for p in t.get_editor_property("imported_object_paths") or []]
    if not paths:
        raise RuntimeError(f"importing {tasks[0].filename} made nothing")
    return paths


def _rename_into(folder, name_of):
    """Move everything under staging into ``folder`` as name_of(asset), then
    drop staging.  name_of returns None for an asset to leave behind."""
    moves, seen = [], set()
    for path in EAL.list_assets(STAGING_DIR, recursive=True):
        asset = EAL.load_asset(path.split(".")[0])
        new = name_of(asset) if asset else None
        if new is None or new in seen:
            continue
        seen.add(new)
        moves.append(unreal.AssetRenameData(asset, folder, new))
    if not unreal.AssetToolsHelpers.get_asset_tools().rename_assets(moves):
        raise RuntimeError(f"could not rename the import into {folder}")
    EAL.delete_directory(STAGING_DIR)
    EAL.save_directory(folder, only_if_is_dirty=False)
    return len(moves)


def _flat_name(asset, short):
    """The project prefixes for whatever an import makes."""
    name = asset.get_name()
    if isinstance(asset, unreal.StaticMesh):
        return f"SM_{name}"
    if isinstance(asset, unreal.MaterialInstanceConstant):
        return f"MI_{short}_{name.removeprefix('M_')}"
    if isinstance(asset, unreal.PhysicsAsset):
        return f"SKM_{short}_PhysicsAsset"
    if isinstance(asset, unreal.Skeleton):
        return f"SK_{short}"
    if isinstance(asset, unreal.SkeletalMesh):
        return f"SKM_{short}"
    return None


def import_ual(stem, short, glb):
    """One UAL pack: SKM_<short>, SK_<short> and A_<short>_<Clip> per clip.
    Returns {clip name: AnimSequence}."""
    folder = _extract(stem, [glb])
    _fresh(pack_dir(short))
    # glTF goes through Interchange, which makes the mesh, the skeleton, the
    # physics asset, two materials and one AnimSequence per animation, named
    # <file><animation> (UAL1_StandardCrouch_Idle_Loop).
    _run([_task(os.path.join(folder, glb))])
    file_stem = os.path.splitext(os.path.basename(glb))[0]

    def name_of(asset):
        if isinstance(asset, unreal.AnimSequence):
            return f"A_{short}_{asset.get_name().removeprefix(file_stem)}"
        return _flat_name(asset, short)

    n = _rename_into(pack_dir(short), name_of)
    clips = {}
    for path in EAL.list_assets(pack_dir(short), recursive=False):
        asset = EAL.load_asset(path.split(".")[0])
        if isinstance(asset, unreal.AnimSequence):
            clips[asset.get_name().removeprefix(f"A_{short}_")] = asset
    _log(f"{short}: {n} assets, {len(clips)} clips -> {pack_dir(short)}")
    return clips


def import_ual_packs():
    """{short: {clip name: AnimSequence}} for every UAL pack."""
    return {short: import_ual(stem, short, glb) for stem, short, glb in UAL_PACKS}


def _static_options():
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", False)
    opts.set_editor_property("import_animations", False)
    # The pack's colours are flat FBX material colours; the importer turns
    # each into an instance of the engine's FBX Phong material.
    opts.set_editor_property("import_materials", True)
    opts.set_editor_property("import_textures", False)
    opts.set_editor_property("mesh_type_to_import",
                             unreal.FBXImportType.FBXIT_STATIC_MESH)
    # One mesh per gun: the parts are separate objects in the FBX.
    opts.get_editor_property("static_mesh_import_data").set_editor_property(
        "combine_meshes", True)
    return opts


def import_props(stem, short, fbx_dir):
    """Every FBX in a prop pack -> SM_<Stem>, its colours MI_<Pack>_<Name>.
    Returns (how many FBX the pack has, the meshes' package paths)."""
    folder = _extract(stem, [f"{fbx_dir}/"])
    _fresh(pack_dir(short))
    src = os.path.join(folder, fbx_dir)
    fbxs = sorted(f for f in os.listdir(src) if f.lower().endswith(".fbx"))
    tasks = []
    for fbx in fbxs:
        task = _task(os.path.join(src, fbx), _static_options())
        task.destination_name = os.path.splitext(fbx)[0]
        tasks.append(task)
    _run(tasks)
    _rename_into(pack_dir(short), lambda a: _flat_name(a, short))
    meshes = sorted(p.split(".")[0] for p in EAL.list_assets(pack_dir(short), False)
                    if isinstance(EAL.load_asset(p.split(".")[0]), unreal.StaticMesh))
    _log(f"{short}: {len(fbxs)} FBX -> {len(meshes)} static meshes in {pack_dir(short)}")
    return len(fbxs), meshes


def import_prop_packs():
    return {short: import_props(stem, short, d) for stem, short, d in PROP_PACKS}


def import_zombie():
    """The zombie pack's character: SKM_Zombie on SK_Zombie with its clips.
    Returns the mesh's clips as {name: AnimSequence}."""
    stem, short, fbx = ZOMBIE_PACK
    folder = _extract(stem, [fbx])
    _fresh(pack_dir(short))
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", True)
    opts.set_editor_property("import_animations", True)
    opts.set_editor_property("import_materials", True)
    opts.set_editor_property("mesh_type_to_import",
                             unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    _run([_task(os.path.join(folder, fbx), opts)])

    def name_of(asset):
        if isinstance(asset, unreal.AnimSequence):
            clip = asset.get_name().rsplit("_Anim_", 1)[-1].replace("|", "_")
            return f"A_{short}_{clip}"
        return _flat_name(asset, short)

    _rename_into(pack_dir(short), name_of)
    clips = {}
    for path in EAL.list_assets(pack_dir(short), recursive=False):
        asset = EAL.load_asset(path.split(".")[0])
        if isinstance(asset, unreal.AnimSequence):
            clips[asset.get_name()] = asset
    _log(f"{short}: SKM_{short} with {len(clips)} clips -> {pack_dir(short)}")
    return clips
