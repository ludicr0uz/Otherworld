"""Check the grass and bush meshes are there before a level plants them, and
verify them.

Called by the generated import_<Level>.py (step 5a) and verify_<Level>.py. The
meshes come out of two Fab packs and are planted as the pack made them
(forest_generator/undergrowth_meshes.py): nothing here writes to one.

What the verifier guards is the two ways this can go wrong without anyone
touching the code: the pack is updated and the mesh is no longer the one
measured, or the mesh references a package the repository does not carry, so
a clone draws it with the default grey material.
"""

import unreal

from forest_generator.undergrowth_meshes import UNDERGROWTH_MESHES

_CELL_PREFIXES = ("HISM_Grass", "HISM_Bush")


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def ensure_undergrowth_assets():
    """Raise, naming the pack to add, if a mesh is missing."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    for mesh in UNDERGROWTH_MESHES:
        if not eas.does_asset_exist(mesh.mesh):
            raise RuntimeError(
                f"{mesh.mesh} is missing. It is committed with the game; in a "
                f"clone without it, add the Fab pack \"{mesh.pack}\" "
                f"(Scripts/asset_pipeline/fab_library.json)")
        _log(f"   {mesh.name}: {mesh.mesh}")


def _dependencies(package):
    """Every /Game package ``package`` needs, itself included."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    options = unreal.AssetRegistryDependencyOptions(
        include_hard_package_references=True,
        include_soft_package_references=True)
    seen, todo = set(), [package]
    while todo:
        current = todo.pop()
        if current in seen or not current.startswith("/Game/"):
            continue
        seen.add(current)
        todo.extend(str(d) for d in registry.get_dependencies(current, options) or [])
    return seen


def verify_undergrowth_assets(check, actors):
    """``check`` is the verify script's harness; ``actors`` the level's."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for record in UNDERGROWTH_MESHES:
        mesh = eas.load_asset(record.mesh)
        check(f"{record.name} Exists", bool(mesh), record.mesh)
        if not mesh:
            continue
        check(f"{record.name} Not Nanite",
              not mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))
        lods = mesh.get_num_lods()
        check(f"{record.name} LOD Chain", lods == record.lods,
              f"(expected {record.lods}, got {lods})")
        triangles = mesh.get_num_triangles(0)
        check(f"{record.name} Is The Mesh That Was Measured",
              triangles == record.lod0_triangles,
              f"(expected {record.lod0_triangles} triangles in LOD0, got {triangles})")
        height = float(mesh.get_bounds().box_extent.z) * 2.0
        check(f"{record.name} Height", abs(height - record.height_cm) < 1.0,
              f"(expected {record.height_cm:.1f} cm, got {height:.1f} cm)")
        check(f"{record.name} No Collision Shapes",
              meshes.get_simple_collision_count(mesh) <= 0)
        unusable = []
        for slot in mesh.get_editor_property("static_materials"):
            material = slot.get_editor_property("material_interface")
            base = material.get_base_material() if material else None
            if not base or not base.get_editor_property("used_with_instanced_static_meshes"):
                unusable.append(str(slot.get_editor_property("material_slot_name")))
        check(f"{record.name} Materials Draw On Instances", not unusable, str(unusable))
        stray = sorted(_dependencies(record.mesh) - set(record.packages))
        check(f"{record.name} Needs Nothing The Repository Does Not Carry",
              not stray, str(stray[:3]))

    # Every undergrowth cell draws one of these, with the mesh's own materials.
    wanted = {m.mesh for m in UNDERGROWTH_MESHES}
    other, overridden = [], []
    for actor in actors:
        label = actor.get_actor_label()
        if not (label.startswith(_CELL_PREFIXES) and "__" in label):
            continue
        root = actor.get_editor_property("root_component")
        mesh = root.get_editor_property("static_mesh") if root else None
        if not mesh or mesh.get_path_name().split(".")[0] not in wanted:
            other.append(label)
        elif any(root.get_editor_property("override_materials")):
            overridden.append(label)
    check("Undergrowth Cells Draw The Library Meshes", not other, str(other[:3]))
    check("Undergrowth Cells Keep The Meshes' Own Materials", not overridden,
          str(overridden[:3]))
