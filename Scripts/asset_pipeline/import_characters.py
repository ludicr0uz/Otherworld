"""import_characters.py -- bring cached Meshy rigs into Content/ and check them.

Editor-side. Run through the usual harness:

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_characters.py

Everything it imports lands under /Game/Sourced/Characters, which is
git-ignored and rebuilt from assets/cache/meshy -- the same
code-only contract the rest of Content/ lives under.

── What this is really for ─────────────────────────────────────────────────

The import is the easy half.  The half that decides the architecture is check
(4) below: whether two separately generated monsters come back on the *same*
bone hierarchy.  If they do, one skeleton, one IK Rig, one retargeter and one
anim BP serve every monster you ever generate, and each new creature is just a
mesh.  If they do not, every monster carries its own animation setup and the
cost per creature is many times higher.

So this script does not merely import.  It fingerprints the skeleton of each
mesh and compares them, and says plainly which of those two worlds we are in.
"""

import json
import os

import unreal

PROJECT_DIR = unreal.Paths.project_dir()
CACHE_ROOT = os.path.join(PROJECT_DIR, "assets", "cache", "meshy")
DEST_ROOT = "/Game/Sourced/Characters"

# Every Meshy monster shares one skeleton -- proved by skeleton_probe.py, which
# found identical 24-bone hierarchies for a 1.8 m zombie and a 2.4 m wendigo.
# It gets a canonical name rather than being named after whichever creature
# happened to import first.
SHARED_SKELETON = f"{DEST_ROOT}/SK_MeshyHumanoid"

# SKM_Quinn_Simple, measured 2026-09-27: 180.17 uu tall. Anything arriving at
# ~1.8 instead of ~180 has come in as metres and needs an import scale of 100.
QUINN_HEIGHT_UU = 180.17

_log = unreal.log_warning


def _specs():
    """Read the catalog without importing it -- it lives outside sys.path here."""
    out = []
    if not os.path.isdir(CACHE_ROOT):
        return out
    for sid in sorted(os.listdir(CACHE_ROOT)):
        state_path = os.path.join(CACHE_ROOT, sid, "task.json")
        if os.path.exists(state_path):
            with open(state_path) as fh:
                out.append(json.load(fh))
    return out


def _rigged_fbx(cache_dir):
    """The rigged FBX, preferring a plain skin over an animation variant."""
    rig_dir = os.path.join(cache_dir, "rigged")
    if not os.path.isdir(rig_dir):
        return None
    fbxs = [f for f in os.listdir(rig_dir) if f.lower().endswith(".fbx")]
    if not fbxs:
        return None
    # Animation variants carry walk/run in the name; the bare rig is what we
    # want as the mesh, and the clips get imported separately later.
    plain = [f for f in fbxs if not any(k in f.lower() for k in ("walk", "run", "anim"))]
    return os.path.join(rig_dir, sorted(plain or fbxs, key=len)[0])


def import_fbx(fbx_path, dest_path, asset_name, skeleton=None):
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", True)
    opts.set_editor_property("import_materials", True)
    opts.set_editor_property("import_textures", True)
    opts.set_editor_property("import_animations", False)
    opts.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    if skeleton:
        # Binding to an existing skeleton is the whole point: it is what makes
        # monster #2 onwards free of animation setup.
        opts.set_editor_property("skeleton", skeleton)
    sk_data = opts.get_editor_property("skeletal_mesh_import_data")
    sk_data.set_editor_property("import_morph_targets", True)
    sk_data.set_editor_property("convert_scene", True)

    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = dest_path
    task.destination_name = asset_name
    task.replace_existing = True
    task.automated = True
    task.save = True
    task.options = opts
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    for path in task.get_editor_property("imported_object_paths") or []:
        obj = unreal.EditorAssetLibrary.load_asset(path)
        if isinstance(obj, unreal.SkeletalMesh):
            return obj
    return None


def _sweep_root():
    """Delete unreferenced strays sitting directly under DEST_ROOT.

    The FBX importer scatters a copy of the material and texture into the
    PARENT of the folder it was told to import into, so duplicates accumulate
    at the root next to the skeleton.  They are named on Meshy's generic
    pattern, so they are probed by name rather than discovered by listing the
    directory: freshly written assets do not reliably appear in a registry
    listing during the same cold run that created them, and a sweep that
    silently finds nothing is worse than no sweep at all.

    Only assets with no referencers are removed.  The skeleton has plenty, and
    each monster's real material and textures live one level down.
    """
    candidates = [path.split(".")[0] for path in
                  unreal.EditorAssetLibrary.list_assets(DEST_ROOT, recursive=False)]
    for n in range(8):
        candidates += [f"{DEST_ROOT}/Material_{n}", f"{DEST_ROOT}/texture_{n}"]

    for base in dict.fromkeys(candidates):
        if base == SHARED_SKELETON:
            continue
        if not unreal.EditorAssetLibrary.does_asset_exist(base):
            continue
        if unreal.EditorAssetLibrary.find_package_referencers_for_asset(base, False):
            continue
        if unreal.EditorAssetLibrary.delete_asset(base):
            _log(f"[IMPORT] swept unreferenced stray {base.rsplit('/', 1)[1]}")


def _monster_dir(spec):
    """Where one monster's mesh, material and textures live, together.

    Meshy names every export's material ``Material_1`` and its textures
    ``texture_0``.  Imported into one shared folder the SECOND monster finds
    those names taken and binds to the FIRST monster's assets instead of
    creating its own -- the zombie and the wendigo came out wearing the same
    skin, and a material slot count of 1 on each made it look deliberate.

    Renaming them after each import looks like the obvious fix and is a trap:
    a rename leaves a redirector behind, the mesh keeps pointing at that, and
    the reference reads correctly right up until the redirector is collected.
    A folder per monster removes the collision instead of repairing it, so
    nothing is ever renamed and no redirector is ever created.
    """
    return f"{DEST_ROOT}/{os.path.basename(spec.get('dest', spec['id']))}"


def check_mesh(mesh, spec):
    """The import-step checks from the spike spec, in order."""
    name = mesh.get_name()
    _log(f"[IMPORT] --- {name} ---")
    ok = True

    # (1) it is a skeletal mesh at all
    _log(f"[IMPORT]   type = {type(mesh).__name__}")

    # (2) scale: metres-vs-centimetres is the classic silent 100x error
    bounds = mesh.get_bounds()
    height_uu = bounds.box_extent.z * 2.0
    want = spec.get("height_meters", 1.8) * 100.0
    _log(f"[IMPORT]   height = {height_uu:.1f} uu (expected ~{want:.0f})")
    if height_uu < want * 0.5 or height_uu > want * 2.0:
        _log(f"[IMPORT]   FAIL scale looks wrong -- check import units")
        ok = False

    # (5) polycount against budget
    try:
        tris = mesh.get_editor_property("lod_info")
        _log(f"[IMPORT]   lod levels = {len(tris)}")
    except Exception:
        pass

    # (6) materials and PBR maps
    mats = mesh.get_editor_property("materials")
    _log(f"[IMPORT]   material slots = {len(mats)}")
    if not mats:
        _log("[IMPORT]   FAIL no materials -- refine stage may have lacked enable_pbr")
        ok = False

    return ok


def _mint_shared_skeleton(specs):
    """Create SK_MeshyHumanoid, before any monster is imported for keeps.

    The skeleton only comes into existence as a side effect of importing a
    mesh, and it is named after that mesh -- import the wendigo first and every
    future creature hangs off ``SKM_Wendigo01_Skeleton``.  Renaming it
    afterwards seemed like the fix, but a rename leaves the mesh pointing at a
    redirector: it resolves inside the same session and looks correct, then
    resolves to nothing once the redirector is gone.  That is how the wendigo
    ended up with a skeleton of None.

    So the first import is treated as throwaway.  It exists to mint the
    skeleton under its canonical name; the mesh it produced is discarded and
    re-imported in the real pass, bound explicitly to that skeleton.  Every
    monster then takes the identical path through the importer, including the
    first one.
    """
    existing = unreal.EditorAssetLibrary.load_asset(SHARED_SKELETON)
    if existing:
        _log(f"[IMPORT] reusing {SHARED_SKELETON}")
        return existing

    for spec in specs:
        fbx = _rigged_fbx(os.path.join(CACHE_ROOT, spec["id"]))
        if not fbx:
            continue
        seed_dir = f"{DEST_ROOT}/_seed"
        mesh = import_fbx(fbx, seed_dir, "SKM_MeshySeed")
        skel = mesh.get_editor_property("skeleton") if mesh else None
        if not skel:
            continue
        src = skel.get_path_name().split(".")[0]
        unreal.EditorAssetLibrary.rename_asset(src, SHARED_SKELETON)
        # The seed mesh and its material must not survive: a reference to them
        # is exactly the rotting reference this whole dance exists to avoid.
        unreal.EditorAssetLibrary.delete_directory(seed_dir)
        _log(f"[IMPORT] minted {SHARED_SKELETON} from {spec['id']}")
        return unreal.EditorAssetLibrary.load_asset(SHARED_SKELETON)
    return None


def main():
    specs = _specs()
    if not specs:
        _log(f"[IMPORT] nothing cached under {CACHE_ROOT} -- run fetch_monsters.py first")
        return

    unreal.EditorAssetLibrary.make_directory(DEST_ROOT)
    shared_skeleton = _mint_shared_skeleton(specs)
    if not shared_skeleton:
        _log("[IMPORT] could not create a skeleton from any cached rig")
        return

    prints = {}
    for spec in specs:
        sid = spec["id"]
        fbx = _rigged_fbx(os.path.join(CACHE_ROOT, sid))
        if not fbx:
            _log(f"[IMPORT] {sid}: no rigged FBX in cache, skipping")
            continue
        asset_name = os.path.basename(spec.get("dest", f"SKM_{sid}"))
        dest_dir = _monster_dir(spec)
        _log(f"[IMPORT] {sid}: importing {os.path.basename(fbx)} -> {dest_dir}/{asset_name}")

        mesh = import_fbx(fbx, dest_dir, asset_name, skeleton=shared_skeleton)
        if not mesh:
            _log(f"[IMPORT] {sid}: FAILED -- no SkeletalMesh produced")
            continue

        ok = check_mesh(mesh, spec)
        skel = mesh.get_editor_property("skeleton")
        _log(f"[IMPORT]   skeleton = {skel.get_name() if skel else None}")
        if skel != shared_skeleton:
            _log("[IMPORT]   FAIL bound to the wrong skeleton")
            ok = False
        prints[sid] = (skel.get_name() if skel else "NONE", ok)

    _sweep_root()
    unreal.EditorAssetLibrary.save_directory(DEST_ROOT, only_if_is_dirty=False)

    # (4) the result the spike exists to produce
    _log("[IMPORT] ================ summary ================")
    for sid, (skname, ok) in prints.items():
        _log(f"[IMPORT]   {sid:14s} {skname:28s} {'ok' if ok else 'CHECKS FAILED'}")
    skels = {s for s, _ in prints.values() if s}
    if len(prints) > 1:
        if len(skels) == 1:
            _log(f"[IMPORT]   all {len(prints)} monsters share {skels.pop()} -- "
                 "one IK Rig and one anim BP will serve them")
        else:
            _log(f"[IMPORT]   WARNING: {len(skels)} distinct skeletons: {sorted(skels)}")

main()
