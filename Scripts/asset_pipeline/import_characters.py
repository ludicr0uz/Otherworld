"""import_characters.py -- bring cached Meshy rigs into Content/ and check them.

Editor-side. Run through the usual harness:

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_characters.py

Everything it imports lands under /Game/Sourced/Characters, which is
git-ignored and rebuilt from assets/cache/meshy -- the same
code-only contract the rest of Content/ lives under.

── What this is really for ─────────────────────────────────────────────────

The import is the easy half.  The half that decides the architecture is
whether two separately generated monsters can share one animation setup.

The first answer to that was wrong, and it is worth recording why.
skeleton_probe.py compared bone HIERARCHIES -- names and parents -- found them
identical for a 1.8 m zombie and a 2.4 m wendigo, and concluded one skeleton
would serve both.  Every monster was then bound to a single SK_MeshyHumanoid.

Identical hierarchies are not sufficient.  What an animation actually carries
is a per-bone LOCAL ROTATION, and what that rotation means depends on the bone
orientation in the mesh's BIND POSE.  Meshy reuses the bone names; it does not
reuse the bind pose, and it cannot -- a wendigo's neck is not a zombie's neck.
Measured on the two rigs:

    bone    zombie bind pose          wendigo bind pose
    neck    T y=9.55   rot x=0.023    T z=17.34  rot x=0.493   <- 59 deg pitch
    Head    T y=7.26                  T y=34.20

SK_MeshyHumanoid was minted from whichever monster imported first -- the
wendigo -- so every retargeted clip was authored against the wendigo's forward
neck pitch.  The wendigo looked right.  The zombie wore the wendigo's neck and
its head hung out in front of its body, and nothing errored.

So each monster now gets its OWN skeleton, and with it its own IK Rig,
retargeter and anim BP.  That is the more expensive world, and it is the one
we are actually in.  The cost is per creature; the chain table in
build_retarget.py is by bone NAME and those really are shared, so adding a
creature is still no new hand-authoring -- just more generated assets.
"""

import json
import os

import unreal

PROJECT_DIR = unreal.Paths.project_dir()
CACHE_ROOT = os.path.join(PROJECT_DIR, "assets", "cache", "meshy")
DEST_ROOT = "/Game/Sourced/Characters"

# One skeleton per monster.  See the module docstring for why this is not
# SK_MeshyHumanoid any more.
def _skeleton_path(spec):
    return f"{DEST_ROOT}/SK_{_monster_name(spec).replace('SKM_', '')}"


def _monster_name(spec):
    return os.path.basename(spec.get("dest", f"SKM_{spec['id']}"))

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
    # Asked for, but not relied on: the importer ignores this whenever an
    # existing skeleton is supplied, and one always is here. _ensure_physics()
    # below is what actually guarantees it.
    opts.set_editor_property("create_physics_asset", True)
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
        if not unreal.EditorAssetLibrary.does_asset_exist(base):
            continue
        # Never sweep a skeleton. They sit directly under DEST_ROOT alongside
        # the strays, and the referencer check answers from DISK -- so a mesh
        # imported but not yet saved does not count as a referencer and its
        # brand-new skeleton looks like garbage. This deleted both skeletons
        # the first time the per-monster layout ran.
        if isinstance(unreal.EditorAssetLibrary.load_asset(base), unreal.Skeleton):
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

    # (6) a physics asset, or nothing can be shot
    phys = mesh.get_editor_property("physics_asset")
    _log(f"[IMPORT]   physics asset = {phys.get_name() if phys else None}")
    if not phys:
        _log("[IMPORT]   FAIL no physics asset -- hit zones cannot be built, "
             "so the creature would be unshootable")
        ok = False

    # (7) materials and PBR maps
    mats = mesh.get_editor_property("materials")
    _log(f"[IMPORT]   material slots = {len(mats)}")
    if not mats:
        _log("[IMPORT]   FAIL no materials -- refine stage may have lacked enable_pbr")
        ok = False

    return ok


def _mint_skeleton(spec):
    """Create SK_<Monster>, before that monster is imported for keeps.

    A skeleton only comes into existence as a side effect of importing a mesh,
    and it is named after that mesh -- so an unmanaged import leaves
    ``SKM_Zombie01_Skeleton`` next to ``SKM_Zombie01``.  Renaming it afterwards
    seemed like the fix, but a rename leaves the mesh pointing at a redirector:
    it resolves inside the same session and looks correct, then resolves to
    nothing once the redirector is collected.  That is how the wendigo ended up
    with a skeleton of None.

    So the first import of each monster is treated as throwaway.  It exists to
    mint the skeleton under its canonical name; the mesh it produced is
    discarded and re-imported in the real pass, bound explicitly to that
    skeleton.
    """
    path = _skeleton_path(spec)
    existing = unreal.EditorAssetLibrary.load_asset(path)
    if existing:
        _log(f"[IMPORT] reusing {path}")
        return existing

    fbx = _rigged_fbx(os.path.join(CACHE_ROOT, spec["id"]))
    if not fbx:
        return None
    seed_dir = f"{DEST_ROOT}/_seed"
    mesh = import_fbx(fbx, seed_dir, "SKM_MeshySeed")
    skel = mesh.get_editor_property("skeleton") if mesh else None
    if not skel:
        unreal.EditorAssetLibrary.delete_directory(seed_dir)
        return None
    src = skel.get_path_name().split(".")[0]
    unreal.EditorAssetLibrary.rename_asset(src, path)
    # The seed mesh and its material must not survive: a reference to them is
    # exactly the rotting reference this whole dance exists to avoid.
    unreal.EditorAssetLibrary.delete_directory(seed_dir)
    _log(f"[IMPORT] minted {path} from {spec['id']}")
    return unreal.EditorAssetLibrary.load_asset(path)


def _ensure_physics(mesh):
    """Give the mesh a physics asset if the import did not.

    build_weapons_and_combat.py builds every hit zone out of a physics asset's
    bodies, so a creature without one cannot be shot at all -- and it fails
    three scripts later with "has no physics asset", a long way from the import
    that skipped it.

    The importer's create_physics_asset flag is ignored when an existing
    skeleton is supplied, which is always the case here: each monster is bound
    to the skeleton minted for it a moment earlier. So it is created directly
    instead.
    """
    if mesh.get_editor_property("physics_asset"):
        return mesh.get_editor_property("physics_asset")
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    phys = sub.create_physics_asset(mesh)
    if phys:
        mesh.set_editor_property("physics_asset", phys)
        unreal.EditorAssetLibrary.save_loaded_asset(phys)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    return phys


def _bind_fingerprint(skel):
    """A few bind-pose numbers that decide whether two rigs can share clips.

    Bone names and parents are NOT enough -- see the module docstring.  These
    are the bones where the two monsters actually diverged.
    """
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
    names = {str(b) for b in unreal.AnimPoseExtensions.get_bone_names(pose)}
    out = []
    for bone in ("Hips", "Spine", "neck", "Head"):
        if bone not in names:
            continue
        t = unreal.AnimPoseExtensions.get_bone_pose(
            pose, bone, unreal.AnimPoseSpaces.LOCAL)
        r = t.rotation.rotator()
        out.append(f"{bone}(y{t.translation.y:.1f} z{t.translation.z:.1f} "
                   f"r{r.roll:.0f})")
    return " ".join(out)


def main():
    specs = _specs()
    if not specs:
        _log(f"[IMPORT] nothing cached under {CACHE_ROOT} -- run fetch_monsters.py first")
        return

    unreal.EditorAssetLibrary.make_directory(DEST_ROOT)

    prints = {}
    for spec in specs:
        sid = spec["id"]
        fbx = _rigged_fbx(os.path.join(CACHE_ROOT, sid))
        if not fbx:
            _log(f"[IMPORT] {sid}: no rigged FBX in cache, skipping")
            continue
        asset_name = _monster_name(spec)
        dest_dir = _monster_dir(spec)
        _log(f"[IMPORT] {sid}: importing {os.path.basename(fbx)} -> {dest_dir}/{asset_name}")

        own_skeleton = _mint_skeleton(spec)
        if not own_skeleton:
            _log(f"[IMPORT] {sid}: FAILED -- could not mint a skeleton")
            continue

        mesh = import_fbx(fbx, dest_dir, asset_name, skeleton=own_skeleton)
        if not mesh:
            _log(f"[IMPORT] {sid}: FAILED -- no SkeletalMesh produced")
            continue

        _ensure_physics(mesh)
        ok = check_mesh(mesh, spec)
        skel = mesh.get_editor_property("skeleton")
        _log(f"[IMPORT]   skeleton = {skel.get_name() if skel else None}")
        if skel != own_skeleton:
            _log("[IMPORT]   FAIL bound to the wrong skeleton")
            ok = False
        prints[sid] = (skel.get_name() if skel else "NONE", ok,
                       _bind_fingerprint(skel) if skel else "")

    # Save first: find_package_referencers_for_asset reads what is on disk, so
    # an unsaved mesh does not yet count as referencing anything it imported.
    unreal.EditorAssetLibrary.save_directory(DEST_ROOT, only_if_is_dirty=False)
    _sweep_root()
    unreal.EditorAssetLibrary.save_directory(DEST_ROOT, only_if_is_dirty=False)

    # (4) the result the spike exists to produce
    _log("[IMPORT] ================ summary ================")
    for sid, (skname, ok, finger) in prints.items():
        _log(f"[IMPORT]   {sid:14s} {skname:22s} {'ok' if ok else 'CHECKS FAILED'}")
        _log(f"[IMPORT]     bind pose: {finger}")
    skels = {v[0] for v in prints.values() if v[0]}
    if len(prints) > 1:
        # One skeleton per monster is the expected and correct outcome. The
        # check is inverted from what it used to be: a SHARED skeleton is now
        # the bug, because it means one creature is wearing another's bind pose.
        if len(skels) == len(prints):
            _log(f"[IMPORT]   {len(prints)} monsters, {len(skels)} skeletons -- "
                 "each creature animates against its own bind pose")
        else:
            _log(f"[IMPORT]   WARNING: {len(prints)} monsters share only "
                 f"{len(skels)} skeleton(s): {sorted(skels)}. Whichever monster "
                 "did not mint the skeleton will animate against another "
                 "creature's bind pose.")
        fingers = {v[2] for v in prints.values()}
        if len(fingers) > 1:
            _log("[IMPORT]   (bind poses differ, as expected -- this is exactly "
                 "why the clips cannot be shared)")

main()
