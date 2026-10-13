"""editor_import.py -- import a staged raw item into /Game/Fab/<Item>.

Reads plan.json and does what it says: each texture with the settings its
role needs, each FBX, OBJ or GLB as one static mesh, a material per texture
set worn by the slots textures.assign gives it, each USD layer through the USD
importer (usd_import.py). The staged files are hashed against the plan first.
What was made and what was checked goes in imported.json beside the plan, and
the listing in fab_library.json (an existing entry keeps its licence).

A mesh with no texture set keeps the materials its file carries. Nothing
here knows what the thing is for: a gun's grip, a hat's fit and a tree's wind
belong to the systems that use them.
"""

import datetime
import json
import os

import unreal

from asset_pipeline import fab_library
from asset_pipeline.fab_raw import material, prefixes, stage, textures, usd_import

EAL = unreal.EditorAssetLibrary
TC = unreal.TextureCompressionSettings
TG = unreal.TextureGroup

# The downloads are 4k; 2k is what the project ships (build_creature_materials).
MAX_TEXTURE_SIZE = 2048
# role -> (srgb, compression, lod group). A texture with no role is colour.
TEXTURE_SETTINGS = {
    "basecolor": (True, TC.TC_DEFAULT, TG.TEXTUREGROUP_WORLD),
    "normal": (False, TC.TC_NORMALMAP, TG.TEXTUREGROUP_WORLD_NORMAL_MAP),
    "roughness": (False, TC.TC_MASKS, TG.TEXTUREGROUP_WORLD_SPECULAR),
    "metallic": (False, TC.TC_MASKS, TG.TEXTUREGROUP_WORLD_SPECULAR),
    "ao": (False, TC.TC_MASKS, TG.TEXTUREGROUP_WORLD_SPECULAR),
    "opacity": (False, TC.TC_MASKS, TG.TEXTUREGROUP_WORLD),
    None: (True, TC.TC_DEFAULT, TG.TEXTUREGROUP_WORLD),
}
# A hand prop or a garment outside this range is probably in the wrong unit.
SANE_SIZE_CM = (2.0, 2000.0)


def _log(msg):
    unreal.log_warning(f"[FAB-RAW] {msg}")


def _run(filename, dest, name=None, options=None):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", dest)
    if name:
        task.set_editor_property("destination_name", name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    if options is not None:
        task.set_editor_property("options", options)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return [str(p).split(".")[0] for p in task.get_editor_property("imported_object_paths") or []]


def _fbx_options(own_materials, parts):
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", False)
    opts.set_editor_property("import_animations", False)
    opts.set_editor_property("import_materials", own_materials)
    opts.set_editor_property("import_textures", own_materials)
    opts.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    # One mesh per file: the parts of a gun are separate objects in the FBX.
    # A kit (the plan's "parts") is the other case: its objects are the point.
    opts.get_editor_property("static_mesh_import_data").set_editor_property(
        "combine_meshes", not parts)
    return opts


def _import_texture(path, dest, name, role):
    _run(path, dest, name)
    tex = EAL.load_asset(f"{dest}/{name}")
    if not isinstance(tex, unreal.Texture2D):
        raise RuntimeError(f"{os.path.basename(path)} did not import as a texture")
    srgb, compression, group = TEXTURE_SETTINGS[role]
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("compression_settings", compression)
    tex.set_editor_property("lod_group", group)
    tex.set_editor_property("max_texture_size", MAX_TEXTURE_SIZE)
    return tex


def _import_mesh(path, dest, name, own_materials, parts):
    options = (_fbx_options(own_materials, parts) if path.lower().endswith(".fbx") else None)
    # A kit's meshes keep the names its objects have; one name cannot be theirs all.
    made = _run(path, dest, None if parts else name, options)
    meshes = [m for m in (EAL.load_asset(p) for p in made) if isinstance(m, unreal.StaticMesh)]
    if not meshes:
        raise RuntimeError(f"{os.path.basename(path)} made no static mesh")
    return meshes


def _wear(mesh, materials, checks):
    slots = [str(s.get_editor_property("material_slot_name"))
             for s in mesh.get_editor_property("static_materials")]
    for n, (key, how) in enumerate(textures.assign(slots, list(materials))):
        mesh.set_material(n, materials[key])
        note = "" if how != "order" else "  (a guess: no name matched)"
        checks.append((how != "order", f"{mesh.get_name()} slot {n} '{slots[n]}' wears "
                                       f"{materials[key].get_name()}{note}"))


def _size_check(mesh, checks):
    extent = mesh.get_bounds().box_extent
    size = max(extent.x, extent.y, extent.z) * 2.0
    tris = mesh.get_num_triangles(0)
    ok = tris > 0 and SANE_SIZE_CM[0] <= size <= SANE_SIZE_CM[1]
    checks.append((ok, f"{mesh.get_name()}: {tris} triangles, {size:.1f} cm across"
                       + ("" if ok else "  (check the scale)")))


def _verify_staged(home, plan):
    for rel, info in sorted(plan["files"].items()):
        path = os.path.join(home, stage.FILES, *rel.split("/"))
        if not os.path.isfile(path) or stage.sha256(path) != info["sha256"]:
            raise RuntimeError(f"{rel} is not the file that was scanned: stage it again")


def _record(plan):
    if not plan["url"]:
        return
    old = fab_library.find(fab_library.load(), plan["title"], plan["url"])
    seller = f"{plan['seller']}; " if plan["seller"] else ""
    fab_library.record(fab_library.FabItem(
        plan["title"], plan["dest"], plan["url"], old.license if old else "",
        note=old.note if old and old.note else f"{seller}raw download, fab_raw_import.py"))


def import_item(home, plan):
    """Import one staged item. Returns (assets made, checks); raises on a failure."""
    dest, files = plan["dest"], os.path.join(home, stage.FILES)
    _verify_staged(home, plan)
    if EAL.does_directory_exist(dest) and EAL.list_assets(dest, True):
        if not plan.get("replace"):
            raise RuntimeError(f"{dest} already holds assets (stage with --replace)")
        EAL.delete_directory(dest)
    EAL.make_directory(dest)
    checks = []

    by_asset = {}
    for entry in plan["textures"]:
        by_asset[entry["asset"]] = _import_texture(
            os.path.join(files, *entry["file"].split("/")), dest, entry["asset"], entry["role"])
    materials = {key: material.build(spec["material"], dest,
                                     {role: by_asset[a] for role, a in spec["roles"].items()})
                 for key, spec in plan["sets"].items()}

    usd = [m["file"] for m in plan["meshes"] if m["usd"]]
    layers, problems = usd_import.roots(files, usd) if usd else ([], [])
    if problems:
        raise RuntimeError("; ".join(problems))
    for entry in plan["meshes"]:
        path = os.path.join(files, *entry["file"].split("/"))
        if entry["usd"]:
            if entry["file"] in layers:
                made = _run(path, dest, None, usd_import.options())
                checks.append((bool(made), f"{entry['file']}: {len(made)} assets from the USD stage"))
            continue
        for mesh in _import_mesh(path, dest, entry["asset"], not materials, plan.get("parts", False)):
            if materials:
                _wear(mesh, materials, checks)
            _size_check(mesh, checks)
    EAL.save_directory(dest, only_if_is_dirty=False, recursive=True)
    renamed = prefixes.apply(dest)
    if renamed:
        _log(f"{plan['slug']}: {renamed} assets the files named took the project's prefixes")
    made = sorted(str(p).split(".")[0] for p in EAL.list_assets(dest, True))
    checks.append((bool(made), f"{len(made)} assets in {dest}"))
    return made, checks


def main(only=()):
    """Import every staged item not imported yet (or the ones named). Raises if one fails."""
    todo = [(slug, plan) for slug, plan, done in stage.staged()
            if (slug in only) or (not only and not done)]
    if not todo:
        _log("nothing staged to import (fab_raw_scan.py <item> --stage)")
        return
    failed = []
    for slug, plan in todo:
        home = os.path.join(stage.RAW_DIR, slug)
        try:
            made, checks = import_item(home, plan)
        except Exception as exc:                    # one bad item does not stop the rest
            _log(f"FAIL {slug}: {exc}")
            failed.append(slug)
            continue
        for ok, text in checks:
            _log(f"  {'ok  ' if ok else 'LOOK'} {text}")
        with open(os.path.join(home, stage.IMPORTED), "w") as fh:
            json.dump({"imported": datetime.datetime.now().isoformat(timespec="seconds"),
                       "assets": made, "checks": [[ok, text] for ok, text in checks]},
                      fh, indent=1)
            fh.write("\n")
        _record(plan)
        _log(f"imported {slug}: {len(made)} assets in {plan['dest']}, "
             f"{sum(1 for ok, _t in checks if not ok)} to look at")
    if failed:
        raise RuntimeError(f"fab_raw: {len(failed)} item(s) failed: {', '.join(failed)}")
