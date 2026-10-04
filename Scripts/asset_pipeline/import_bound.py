"""import_bound.py -- bring bound bodies into Content/ on SK_Mannequin.

Editor-side.

    python3 Scripts/asset_pipeline/bind_to_mannequin.py adventurer_03   # host-side, first
    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_bound.py

Each assets/cache/meshy/<id>/bound/SKM_<Name>.glb lands as
/Game/Sourced/Bound/SKM_<Name>/SKM_<Name>, bound to the mannequin's existing
skeleton -- no new Skeleton asset is made, which is the whole point: the
mannequin's anim blueprint and clips then play on it as they are.

WHAT IT CHECKS, AND WHY EACH ONE
--------------------------------
    skeleton     the mesh's skeleton IS SK_Mannequin.  An importer that could
                 not merge the file's joints into it makes a new skeleton
                 beside the mesh instead, and says nothing.
    reference    every bone's reference ROTATION is the mannequin mesh's.
    pose         This is the check on mannequin_bind/space.py: the bind writes
                 the mannequin's rotations through a glTF conversion, and a
                 convention wrong there would look fine host-side and put
                 every clip off by a fixed turn here.
    height       the body is its catalog height in centimetres (the classic
                 hundredfold error is a unit one).
    material     the body wears its creature material (build_creature_
                 materials.py), if that has been built for it.

WHAT TO LOOK AT AFTERWARDS (nothing here can)
---------------------------------------------
Open the mesh, set the preview animation to MM_Idle, then MM_Jump and
MM_Attack_01: the shoulders under lifted arms, the forearms (the bind turned
them about 130 degrees), and the fingers on a rifle's ready pose.
"""

import glob
import json
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]          # a warm editor keeps yesterday's modules

from asset_pipeline.mannequin_bind import paths                    # noqa: E402

EAL = unreal.EditorAssetLibrary
_log = unreal.log_warning
MANNEQUIN_MESH_ASSET = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
PER_BODY_ROOT = "/Game/Sourced/Characters"
ROTATION_TOLERANCE = 1e-3          # 1 - |dot| of two unit quaternions
HEIGHT_TOLERANCE = 0.05


def bound_files():
    """[(spec, short name, glb path)] for every bound body.  Read from where
    bind_to_mannequin.py writes (the checkout this script is run from, which
    in a worktree is not the project the editor has open); the spec beside
    the rig comes from the data root."""
    out = []
    root = os.path.join(paths.PROJECT_DIR, "assets", "cache", "meshy")
    for glb in sorted(glob.glob(os.path.join(root, "*", "bound", "SKM_*.glb"))):
        sid = os.path.basename(os.path.dirname(os.path.dirname(glb)))
        if sid.startswith("_"):
            continue
        with open(os.path.join(paths.meshy_cache(sid), "task.json")) as fh:
            spec = json.load(fh)
        short = os.path.basename(spec.get("dest", f"SKM_{sid}")).replace("SKM_", "")
        out.append((spec, short, glb))
    return out


def import_onto(glb, dest_dir, skeleton, with_materials):
    """Import one GLB as a skeletal mesh on an existing skeleton.  Without
    ``with_materials`` the file's material and its three 4k textures are left
    in the file: a body that has its creature material already would only
    carry 40 MB of copies beside it."""
    pipeline = unreal.InterchangeGenericAssetsPipeline()
    if not with_materials:
        pipeline.get_editor_property("material_pipeline").set_editor_property(
            "import_materials", False)
        pipeline.get_editor_property("material_pipeline").get_editor_property(
            "texture_pipeline").set_editor_property("import_textures", False)
    shared = pipeline.get_editor_property("common_skeletal_meshes_and_animations_properties")
    shared.set_editor_property("skeleton", skeleton)
    shared.set_editor_property("import_only_animations", False)
    meshes = pipeline.get_editor_property("mesh_pipeline")
    meshes.set_editor_property("import_skeletal_meshes", True)
    meshes.set_editor_property("import_static_meshes", False)
    meshes.set_editor_property("create_physics_asset", True)
    pipeline.get_editor_property("animation_pipeline").set_editor_property(
        "import_animations", False)

    stack = unreal.InterchangePipelineStackOverride()
    stack.add_pipeline(pipeline)

    task = unreal.AssetImportTask()
    task.filename = glb
    task.destination_path = dest_dir
    task.replace_existing = True
    task.automated = True
    task.save = True
    task.options = stack
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    made = [EAL.load_asset(p) for p in task.get_editor_property("imported_object_paths") or []]
    meshes = [a for a in made if isinstance(a, unreal.SkeletalMesh)]
    strays = [a for a in made if isinstance(a, unreal.Skeleton)]
    return (meshes[0] if meshes else None), strays


def _ref_pose(mesh):
    """{bone: component-space reference Transform} of a mesh's own reference
    pose.  Component space is enough: a bound body is written with the
    mannequin's component rotations bone for bone, which is what makes its
    local ones the mannequin's."""
    from asset_pipeline.rig_util import mesh_ref_pose
    return {bone: pair[0] for bone, pair in mesh_ref_pose(mesh).items()}


def _quat(t):
    r = t.rotation
    return (r.x, r.y, r.z, r.w)


def check(mesh, strays, skeleton, spec, short):
    """True if the imported body is what the bind meant."""
    ok = True

    def fail(text):
        nonlocal ok
        ok = False
        _log(f"[BOUND]   FAIL {text}")

    got = mesh.get_editor_property("skeleton")
    if got != skeleton:
        fail(f"bound to {got.get_name() if got else None}, not {skeleton.get_name()}: "
             "the importer made its own skeleton -- the file's joints did not "
             "merge into the mannequin's")
    if strays:
        fail(f"the import made skeleton asset(s) {[s.get_name() for s in strays]}")

    mine, theirs = _ref_pose(mesh), _ref_pose(EAL.load_asset(MANNEQUIN_MESH_ASSET))
    missing = sorted(set(theirs) - set(mine))
    if missing:
        fail(f"{len(missing)} mannequin bones missing, first {missing[0]}")
    off = []
    for bone in sorted(set(mine) & set(theirs)):
        a, b = _quat(mine[bone]), _quat(theirs[bone])
        if 1.0 - abs(sum(p * q for p, q in zip(a, b))) > ROTATION_TOLERANCE:
            off.append(bone)
    if off:
        fail(f"{len(off)} bones' reference rotation is not the mannequin's, "
             f"first {off[0]}: see mannequin_bind/space.py -- the glTF "
             "conversion the bind writes through is not the importer's")
    else:
        _log(f"[BOUND]   reference pose: {len(mine)} bones, every rotation the mannequin's")

    height = mesh.get_bounds().box_extent.z * 2.0
    want = spec.get("height_meters", 1.8) * 100.0
    _log(f"[BOUND]   height {height:.1f} cm (catalog {want:.0f})")
    if abs(height / want - 1.0) > HEIGHT_TOLERANCE:
        fail("height is off: import units")
    return ok


def creature_material(short):
    """The creature material built for this body's per-body import, or None."""
    path = f"{PER_BODY_ROOT}/SKM_{short}/MI_{short}"
    return EAL.load_asset(path) if EAL.does_asset_exist(path) else None


def wear_material(mesh, short):
    """Give the body its creature material."""
    path = f"{PER_BODY_ROOT}/SKM_{short}/MI_{short}"
    material = creature_material(short)
    if not material:
        _log(f"[BOUND]   note: no {path}; it keeps the importer's material "
             "(build_creature_materials.py makes the real one)")
        return
    slots = list(mesh.get_editor_property("materials"))
    for slot in slots:
        slot.set_editor_property("material_interface", material)
    mesh.set_editor_property("materials", slots)
    _log(f"[BOUND]   wearing {material.get_name()}")


def main(only=None):
    skeleton = EAL.load_asset(paths.MANNEQUIN_SKELETON_ASSET)
    if not skeleton:
        raise RuntimeError(f"{paths.MANNEQUIN_SKELETON_ASSET} is missing")
    files = [f for f in bound_files() if only is None or f[0]["id"] in only]
    if not files:
        _log("[BOUND] nothing to import: run bind_to_mannequin.py first")
        return False
    EAL.make_directory(paths.BOUND_ROOT)
    results = {}
    for spec, short, glb in files:
        dest = paths.bound_asset_dir(short)
        _log(f"[BOUND] --- {spec['id']}: {os.path.basename(glb)} -> {dest}")
        # Generated in full: what an earlier import left is not merged with.
        if EAL.does_directory_exist(dest):
            EAL.delete_directory(dest)
        mesh, strays = import_onto(glb, dest, skeleton,
                                   with_materials=creature_material(short) is None)
        if mesh and mesh.get_name() != paths.bound_asset_name(short):
            _log(f"[BOUND]   FAIL the mesh arrived as {mesh.get_name()}, not "
                 f"{paths.bound_asset_name(short)}: combat/skin.py will not find it")
            results[spec["id"]] = False
            continue
        if not mesh:
            _log("[BOUND]   FAIL no SkeletalMesh produced")
            results[spec["id"]] = False
            continue
        results[spec["id"]] = check(mesh, strays, skeleton, spec, short)
        wear_material(mesh, short)
        EAL.save_directory(dest, only_if_is_dirty=False)
    _log("[BOUND] ================ summary ================")
    for sid, ok in results.items():
        _log(f"[BOUND]   {sid:16s} {'ok' if ok else 'CHECKS FAILED'}")
    return all(results.values())


if __name__ == "__main__":
    main()
