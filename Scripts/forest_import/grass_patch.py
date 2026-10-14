"""Build the grass patch under /Game/Forest/Undergrowth, and verify it.

The numbers and the reasons are forest_generator/grass_patch.py's. Run by
Scripts/build_grass_patch.py; the level import only checks the patch is there
(undergrowth_assets.py), since it is committed like the clump it is made of.
Nothing here imports forest_import.grass_look: it imports undergrowth_assets,
which imports this.

The clump and its pivot textures are read and never written. A copy of the
clump is its render data (the pack's lower LODs exist only there), moved as
its placement says, with its second UV set moved to its band of the patch's
pivot textures; the textures are written as files (assets/generated/
undergrowth) and imported with the pack's textures' settings.
"""

import os

import unreal

from forest_generator import grass_look as L
from forest_generator import grass_patch as P
from forest_generator.pivot_images import write_exr, write_png

GS_ASSET = unreal.GeometryScript_AssetUtils
GS_EDITS = unreal.GeometryScript_MeshEdits
GS_UVS = unreal.GeometryScript_UVs
GS_LIST = unreal.GeometryScript_List
SUCCESS = unreal.GeometryScriptOutcomePins.SUCCESS
MEL = unreal.MaterialEditingLibrary
PIVOT_UV = 1
# The pack's texture settings the patch's copy, so it is sampled the same way.
_TEXTURE_SETTINGS = ("compression_settings", "filter", "mip_gen_settings", "srgb",
                     "lod_group", "never_stream", "address_x", "address_y")
# A patch blade's root-to-pivot distance matches the clump's within this.
PIVOT_SLACK_CM = 0.5


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def _eas():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _sms():
    return unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)


def _must_load(path):
    asset = _eas().load_asset(path)
    if not asset:
        raise RuntimeError(f"{path} is missing")
    return asset


def _out_dir():
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    path = os.path.join(project, "assets", "generated", "undergrowth")
    os.makedirs(path, exist_ok=True)
    return path


# ─── Reading ─────────────────────────────────────────────────────────────────

def read_lod(mesh, lod):
    """One LOD of ``mesh`` as drawn, as a DynamicMesh."""
    read = unreal.GeometryScriptMeshReadLOD()
    read.set_editor_property("lod_type", unreal.GeometryScriptLODType.RENDER_DATA)
    read.set_editor_property("lod_index", lod)
    opts = unreal.GeometryScriptCopyMeshFromAssetOptions()
    opts.set_editor_property("request_tangents", True)
    dm, outcome = GS_ASSET.copy_mesh_from_static_mesh_v2(mesh, unreal.DynamicMesh(), opts,
                                                         read, True)
    if outcome != SUCCESS:
        raise RuntimeError(f"could not read LOD{lod} of {mesh.get_path_name()}")
    return dm


def texels(texture, wide, high):
    """Every texel of ``texture``, row by row, as (r, g, b, a)."""
    opts = unreal.GeometryScriptSampleTextureOptions()
    opts.set_editor_property("sampling_method", unreal.GeometryScriptPixelSamplingMethod.NEAREST)
    centres = [unreal.Vector2D((x + 0.5) / wide, (y + 0.5) / high)
               for y in range(high) for x in range(wide)]
    found = unreal.GeometryScript_TextureUtils.sample_texture2d_at_uv_positions(
        GS_LIST.convert_array_to_uv_list(centres), texture, opts)
    return [(c.r, c.g, c.b, c.a) for c in GS_LIST.convert_color_list_to_array(found)]


def blade_roots(dm, wide, high):
    """{texel index: the lowest point of the blade that reads it}."""
    _, uvs, *_ = GS_UVS.get_mesh_per_vertex_u_vs(dm, PIVOT_UV)
    _, points, *_ = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dm, False)
    roots = {}
    for uv, p in zip(GS_LIST.convert_uv_list_to_array(uvs),
                     GS_LIST.convert_vector_list_to_array(points)):
        texel = min(wide - 1, int(uv.x * wide)) + wide * min(high - 1, int(uv.y * high))
        if texel not in roots or p.z < roots[texel].z:
            roots[texel] = p
    return roots


# ─── Building ────────────────────────────────────────────────────────────────

def _placed(source, placement):
    """A copy of ``source`` where ``placement`` puts it, reading its band."""
    copy = GS_EDITS.append_mesh(unreal.DynamicMesh(), source, unreal.Transform())
    scale, offset = P.uv_scale_and_offset(placement)
    everything = unreal.GeometryScriptMeshSelection()
    GS_UVS.scale_mesh_u_vs(copy, PIVOT_UV, unreal.Vector2D(1.0, scale),
                           unreal.Vector2D(0.0, 0.0), everything)
    GS_UVS.translate_mesh_u_vs(copy, PIVOT_UV, unreal.Vector2D(0.0, offset), everything)
    return copy, unreal.Transform(
        location=unreal.Vector(placement.x_cm, placement.y_cm, 0.0),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=placement.yaw_deg),
        scale=unreal.Vector(placement.width, placement.width, 1.0))


def build_lods(clump):
    """The patch's LODs, as DynamicMeshes."""
    sources = {lod.source_lod: read_lod(clump, lod.source_lod) for lod in P.LODS}
    built = []
    for lod in P.LODS:
        dm = unreal.DynamicMesh()
        for placement in lod.placements:
            copy, xf = _placed(sources[lod.source_lod], placement)
            GS_EDITS.append_mesh(dm, copy, xf)
        built.append(dm)
    return built


def _import_texture(filename, path, like):
    folder, name = path.rsplit("/", 1)
    task = unreal.AssetImportTask()
    for key, value in (("filename", filename), ("destination_path", folder),
                       ("destination_name", name), ("automated", True),
                       ("replace_existing", True), ("save", False)):
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = _must_load(path)
    for key in _TEXTURE_SETTINGS:
        texture.set_editor_property(key, like.get_editor_property(key))
    _eas().save_loaded_asset(texture, False)
    return texture


def build_textures():
    """The patch's pivot and axis textures: a band of the clump's per placement."""
    wide, high = P.TEXELS_WIDE, P.TEXELS_HIGH
    piv_src, vec_src = _must_load(P.SOURCE_PIVOT_TEXTURE), _must_load(P.SOURCE_AXIS_TEXTURE)
    pivots, axes = texels(piv_src, wide, high), texels(vec_src, wide, high)
    piv_rows, vec_rows = [], []
    for placement in P.PLACEMENTS:
        for y in range(high):
            row = range(y * wide, (y + 1) * wide)
            piv_rows.append([P.move_pivot(placement, pivots[i]) for i in row])
            vec_rows.append([P.move_axis(placement, axes[i]) for i in row])
    out = _out_dir()
    piv_file, vec_file = (os.path.join(out, "grass_patch_piv.exr"),
                          os.path.join(out, "grass_patch_vec.png"))
    write_exr(piv_file, piv_rows)
    write_png(vec_file, vec_rows)
    return (_import_texture(piv_file, P.PIVOT_TEXTURE, piv_src),
            _import_texture(vec_file, P.AXIS_TEXTURE, vec_src))


def build_material(pivot, axis):
    """The dark grass with the patch's pivot textures (its parent is
    forest_import/grass_look.py's, built first by the entry point)."""
    if _eas().does_asset_exist(P.MATERIAL):
        instance = _must_load(P.MATERIAL)
    else:
        folder, name = P.MATERIAL.rsplit("/", 1)
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(instance, _must_load(L.GRASS_MATERIAL))
    MEL.set_material_instance_texture_parameter_value(instance, P.PIVOT_PARAM, pivot)
    MEL.set_material_instance_texture_parameter_value(instance, P.AXIS_PARAM, axis)
    MEL.update_material_instance(instance)
    _eas().save_loaded_asset(instance, False)
    return instance


def _write_lod(mesh, dm, lod):
    opts = unreal.GeometryScriptCopyMeshToAssetOptions()
    opts.set_editor_property("enable_recompute_normals", False)
    opts.set_editor_property("enable_recompute_tangents", False)
    opts.set_editor_property("replace_materials", False)
    target = unreal.GeometryScriptMeshWriteLOD()
    target.set_editor_property("lod_index", lod)
    _, outcome = GS_ASSET.copy_mesh_to_static_mesh(dm, mesh, opts, target)
    if outcome != SUCCESS:
        raise RuntimeError(f"could not write LOD{lod} of {P.MESH}: {outcome}")


def build_mesh(lods, material):
    """The patch as a static mesh: its LODs, its material, its screen sizes,
    no collision and no Nanite."""
    if not _eas().does_asset_exist(P.MESH):
        opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        for key, value in (("enable_collision", False), ("enable_nanite", False),
                           ("enable_recompute_normals", False),
                           ("enable_recompute_tangents", False)):
            opts.set_editor_property(key, value)
        _, outcome = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
            lods[0], P.MESH, opts)
        if outcome != SUCCESS:
            raise RuntimeError(f"could not create {P.MESH}")
    mesh, sms = _must_load(P.MESH), _sms()
    mesh.set_num_source_models(len(lods))
    for index, dm in enumerate(lods):
        _write_lod(mesh, dm, index)
    mesh.set_material(0, material)
    sms.remove_collisions(mesh)
    for lod in range(mesh.get_num_lods()):
        for section in range(mesh.get_num_sections(lod)):
            sms.enable_section_collision(mesh, False, lod, section)
    radius = float(mesh.get_bounds().sphere_radius)
    if not sms.set_lod_screen_sizes(mesh, P.screen_sizes(radius)):
        raise RuntimeError(f"{P.MESH}: the LOD screen sizes were refused")
    _eas().save_loaded_asset(mesh, False)
    return mesh


def build_grass_patch():
    clump = _must_load(P.SOURCE)
    pivot, axis = build_textures()
    material = build_material(pivot, axis)
    mesh = build_mesh(build_lods(clump), material)
    tris = [mesh.get_num_triangles(i) for i in range(mesh.get_num_lods())]
    box = mesh.get_bounds().box_extent
    _log(f"   {P.MESH}: {box.x * 2:.0f} x {box.y * 2:.0f} x {box.z * 2:.1f} cm, "
         f"LOD triangles {tris}, screen sizes "
         f"{[round(s, 3) for s in _sms().get_lod_screen_sizes(mesh)]}")
    return mesh


# ─── Verification ────────────────────────────────────────────────────────────

def _root_offsets(mesh, lod, pivots, wide, high):
    """{texel: (how far its blade's lowest point is from its pivot, its index)}."""
    found = {}
    for texel, root in blade_roots(read_lod(mesh, lod), wide, high).items():
        x, y, z, packed = pivots[texel]
        off = ((root.x - x) ** 2 + (root.y - y) ** 2 + (root.z - z) ** 2) ** 0.5
        found[texel] = (off, P.unpack_index(packed))
    return found


def _misplaced_pivots(mesh, pivot_texture):
    """Blades of the patch's LOD0 whose pivot is not where the clump's is.

    LOD0's copies are unwidened, so each blade sits as far from its pivot as
    the same blade of the clump's LOD (a reduced blade may have lost its root:
    up to 13 cm), and its index is its own texel."""
    wide, high = P.texture_size()
    clump = _root_offsets(
        _must_load(P.SOURCE), P.LODS[0].source_lod,
        texels(_must_load(P.SOURCE_PIVOT_TEXTURE), P.TEXELS_WIDE, P.TEXELS_HIGH),
        P.TEXELS_WIDE, P.TEXELS_HIGH)
    patch = _root_offsets(mesh, 0, texels(pivot_texture, wide, high), wide, high)
    blades = P.TEXELS_WIDE * P.TEXELS_HIGH
    far = []
    for texel, (off, index) in sorted(patch.items()):
        own = clump.get(texel % blades, (None,))[0]
        if own is None or abs(off - own) > PIVOT_SLACK_CM or index != texel:
            far.append(f"texel {texel}: {off:.1f} cm (clump {own}), index {index}")
    return far


def verify_grass_patch(check):
    """``check`` is the verify script's harness."""
    mesh = _eas().load_asset(P.MESH)
    check("Grass Patch Exists", bool(mesh), P.MESH)
    if not mesh:
        return
    tris = [mesh.get_num_triangles(i) for i in range(mesh.get_num_lods())]
    check("Grass Patch LODs Are Its Copies", tris == P.lod_triangles(),
          f"(expected {P.lod_triangles()}, got {tris})")
    material = mesh.get_material(0)
    parent = material.get_editor_property("parent") if material else None
    check("Grass Patch Draws The Dark Grass",
          bool(material) and material.get_path_name().split(".")[0] == P.MATERIAL
          and bool(parent) and parent.get_path_name().split(".")[0] == L.GRASS_MATERIAL,
          str(material.get_path_name() if material else None))
    pivot = MEL.get_material_instance_texture_parameter_value(material, P.PIVOT_PARAM) \
        if material else None
    axis = MEL.get_material_instance_texture_parameter_value(material, P.AXIS_PARAM) \
        if material else None
    check("Grass Patch Sways About Its Own Pivots",
          bool(pivot) and pivot.get_path_name().split(".")[0] == P.PIVOT_TEXTURE
          and bool(axis) and axis.get_path_name().split(".")[0] == P.AXIS_TEXTURE,
          f"({pivot}, {axis})")
    if pivot:
        far = _misplaced_pivots(mesh, pivot)
        check("Grass Patch Blades Bend At Their Roots", not far, str(far[:3]))
