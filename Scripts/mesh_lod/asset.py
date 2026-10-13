"""In the editor: the built mesh as an asset -- a copy of the source with
Nanite off, a LOD per geometry, and the settings that make the chain work.

The source is read and never written: the first build duplicates it, which
brings its materials and collision settings along, and everything lands on
the copy. A built mesh is tagged with its spec's stamp and a later run skips
it until the spec changes.

Collision. A classic mesh is hit through the triangles of one of its LODs,
where the Nanite tree was hit through a fallback that had no leaves in it. So
the foliage sections are taken out of collision in every LOD, and collision
reads the last mesh LOD: a trunk and boughs, a few hundred triangles.
"""

import unreal

from mesh_lod import spec as S

STAMP_TAG = "OW_MeshLodSpec"
SOURCE_TAG = "OW_MeshLodSource"
GS_ASSET = unreal.GeometryScript_AssetUtils
SUCCESS = unreal.GeometryScriptOutcomePins.SUCCESS


def _eas():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _sms():
    return unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def load(path):
    asset = _eas().load_asset(path)
    if not asset:
        raise RuntimeError(f"missing asset {path}")
    return asset


def is_built(job):
    """True when the mesh on disk was built from this job's spec."""
    eas = _eas()
    if not eas.does_asset_exist(job.path):
        return False
    mesh = eas.load_asset(job.path)
    return bool(mesh) and str(eas.get_metadata_tag(mesh, STAMP_TAG)) == job.spec.stamp


def open_copy(job):
    """The job's mesh: the one there, or a new duplicate of the source."""
    eas = _eas()
    if job.path == job.source:
        raise RuntimeError(f"{job.path}: a mesh is not built over its own source")
    if eas.does_asset_exist(job.path):
        return load(job.path)
    mesh = eas.duplicate_asset(job.source, job.path)
    if not mesh:
        raise RuntimeError(f"could not duplicate {job.source} to {job.path}")
    return mesh


def write_lod(mesh, dm, lod, tangents=False):
    """``dm`` as the mesh's LOD ``lod``, its material slots kept."""
    opts = unreal.GeometryScriptCopyMeshToAssetOptions()
    opts.set_editor_property("enable_recompute_normals", False)
    opts.set_editor_property("enable_recompute_tangents", tangents)
    opts.set_editor_property("replace_materials", False)
    target = unreal.GeometryScriptMeshWriteLOD()
    target.set_editor_property("lod_index", lod)
    _, outcome = GS_ASSET.copy_mesh_to_static_mesh(dm, mesh, opts, target)
    if outcome != SUCCESS:
        raise RuntimeError(f"could not write LOD{lod} of {mesh.get_path_name()}: {outcome}")


def write_mesh_lods(mesh, lods):
    """Nanite off and the mesh LODs written; any LOD past them is dropped."""
    nanite = unreal.MeshNaniteSettings()
    nanite.set_editor_property("enabled", False)
    _sms().set_nanite_settings(mesh, nanite, apply_changes=False)
    mesh.set_num_source_models(len(lods))
    for index, dm in enumerate(lods):
        write_lod(mesh, dm, index)


def impostor_slot(mesh, material):
    """The index of the material slot the impostor's cards use: the one that
    already holds ``material``, or a new one."""
    for index, slot in enumerate(mesh.static_materials):
        if slot.material_interface == material:
            return index
    mesh.add_material(material)
    return len(mesh.static_materials) - 1


def section_slots(mesh, lod):
    """{section index: material slot} of one LOD."""
    sms = _sms()
    return {section: sms.get_lod_material_slot(mesh, lod, section)
            for section in range(mesh.get_num_sections(lod))}


def finish(mesh, job, foliage, radius_cm):
    """Screen sizes, collision, the stamp, and the save. Returns the screen
    sizes the mesh reports."""
    spec, sms = job.spec, _sms()
    sizes = S.screen_sizes(spec, radius_cm)
    if not sms.set_lod_screen_sizes(mesh, sizes):
        raise RuntimeError(f"{mesh.get_name()}: the LOD screen sizes were refused: {sizes}")
    for lod in range(mesh.get_num_lods()):
        for section, slot in section_slots(mesh, lod).items():
            solid = slot not in foliage and lod < spec.mesh_lods
            sms.enable_section_collision(mesh, solid, lod, section)
    mesh.set_editor_property("lod_for_collision", spec.mesh_lods - 1)
    eas = _eas()
    eas.set_metadata_tag(mesh, STAMP_TAG, spec.stamp)
    eas.set_metadata_tag(mesh, SOURCE_TAG, job.source)
    eas.save_loaded_asset(mesh, only_if_is_dirty=False)
    return [round(s, 4) for s in sms.get_lod_screen_sizes(mesh)]


def lod_triangles(mesh):
    """The triangles each LOD is drawn with."""
    return [mesh.get_num_triangles(lod) for lod in range(mesh.get_num_lods())]
