"""In the editor: the impostor -- its textures imported, its material, and
the cards that are the mesh's last LOD.

One master material (M_Impostor) serves every mesh built into a folder; each
mesh has an instance of it holding its two textures. The material is masked,
two-sided and lit as foliage, like the leaves it stands in for: a card lit
from behind passes ``Subsurface`` of its colour through.
"""

import unreal

from mesh_lod import asset, paths, planes

MEL = unreal.MaterialEditingLibrary
MP = unreal.MaterialProperty
GS_EDITS = unreal.GeometryScript_MeshEdits
DEFAULT_COLOUR = "/Engine/EngineResources/DefaultTexture"
DEFAULT_NORMAL = "/Engine/EngineMaterials/DefaultNormal"


def _split(path):
    folder, name = path.rsplit("/", 1)
    return folder, name


def _import_texture(file, path, normal):
    folder, name = _split(path)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", file)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = asset.load(path)
    if normal:
        texture.set_editor_property("compression_settings",
                                    unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
    else:
        texture.set_editor_property("srgb", True)
    texture.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
    unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)
    return texture


def _node(material, cls, y, **props):
    node = MEL.create_material_expression(material, cls, -700, y)
    for key, value in props.items():
        node.set_editor_property(key, value)
    return node


def ensure_master(path):
    """M_Impostor: BaseColor (alpha is the mask) and Normal textures, and the
    Brightness, Subsurface and Roughness scalars."""
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return asset.load(path)
    folder, name = _split(path)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("shading_model",
                                 unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    material.set_editor_property("used_with_instanced_static_meshes", True)
    colour = _node(material, unreal.MaterialExpressionTextureSampleParameter2D, 0,
                   parameter_name="BaseColor", texture=asset.load(DEFAULT_COLOUR))
    normal = _node(material, unreal.MaterialExpressionTextureSampleParameter2D, 300,
                   parameter_name="Normal", texture=asset.load(DEFAULT_NORMAL),
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)

    def scalar(name, value, y):
        return _node(material, unreal.MaterialExpressionScalarParameter, y,
                     parameter_name=name, default_value=value)

    def times(a, b, y):
        node = _node(material, unreal.MaterialExpressionMultiply, y)
        MEL.connect_material_expressions(a, "RGB" if a is colour else "", node, "A")
        MEL.connect_material_expressions(b, "", node, "B")
        return node

    lit = times(colour, scalar("Brightness", 1.0, 600), 100)
    MEL.connect_material_property(lit, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(times(colour, scalar("Subsurface", 0.4, 750), 200), "",
                                  MP.MP_SUBSURFACE_COLOR)
    MEL.connect_material_property(colour, "A", MP.MP_OPACITY_MASK)
    MEL.connect_material_property(normal, "RGB", MP.MP_NORMAL)
    MEL.connect_material_property(scalar("Roughness", 0.9, 900), "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(scalar("Specular", 0.1, 1050), "", MP.MP_SPECULAR)
    MEL.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    return material


def ensure_instance(job, textures):
    """The mesh's own instance of the master, holding its textures."""
    master = ensure_master(job.master_path)
    if unreal.EditorAssetLibrary.does_asset_exist(job.material_path):
        instance = asset.load(job.material_path)
    else:
        folder, name = _split(job.material_path)
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    spec = job.spec
    MEL.set_material_instance_parent(instance, master)
    MEL.set_material_instance_texture_parameter_value(instance, "BaseColor", textures["BC"])
    MEL.set_material_instance_texture_parameter_value(instance, "Normal", textures["N"])
    MEL.set_material_instance_scalar_parameter_value(
        instance, "Subsurface", spec.impostor_subsurface)
    overrides = instance.get_editor_property("base_property_overrides")
    overrides.set_editor_property("override_opacity_mask_clip_value", True)
    overrides.set_editor_property("opacity_mask_clip_value", spec.impostor_mask_clip)
    instance.set_editor_property("base_property_overrides", overrides)
    MEL.update_material_instance(instance)
    unreal.EditorAssetLibrary.save_loaded_asset(instance, only_if_is_dirty=False)
    return instance


def cards(spec, frame, slot):
    """The cards as geometry: two triangles a plane, all in material ``slot``."""
    dm = unreal.DynamicMesh()
    unreal.GeometryScript_Materials.enable_material_i_ds(dm)
    unreal.GeometryScript_UVs.set_num_uv_sets(dm, 1)
    for plane in range(spec.impostor_planes):
        corners = planes.quad(plane, spec.impostor_planes, frame, spec.atlas_px)
        ids = [GS_EDITS.add_vertex_to_mesh(dm, unreal.Vector(*position))[1]
               for position, _uv in corners]
        for a, b, c in ((0, 1, 2), (0, 2, 3)):
            _, triangle = GS_EDITS.add_triangle_to_mesh(
                dm, unreal.IntVector(ids[a], ids[b], ids[c]))
            uvs = unreal.GeometryScriptUVTriangle()
            for field, corner in zip(("uv0", "uv1", "uv2"), (a, b, c)):
                uvs.set_editor_property(field, unreal.Vector2D(*corners[corner][1]))
            unreal.GeometryScript_UVs.set_mesh_triangle_u_vs(dm, 0, triangle, uvs)
            unreal.GeometryScript_Materials.set_triangle_material_id(dm, triangle, slot)
    unreal.GeometryScript_Normals.set_per_face_normals(dm)
    return dm


def build(mesh, job, frame):
    """Import the atlases, make the material and add the cards as the LOD
    after the mesh LODs."""
    name, spec = job.asset_name, job.spec
    textures = {kind: _import_texture(paths.atlas_png(name, kind), job.texture_path(kind),
                                      normal=(kind == "N"))
                for kind in ("BC", "N")}
    instance = ensure_instance(job, textures)
    slot = asset.impostor_slot(mesh, instance)
    mesh.set_num_source_models(spec.mesh_lods + 1)
    asset.write_lod(mesh, cards(spec, frame, slot), spec.mesh_lods, tangents=True)
    return instance
