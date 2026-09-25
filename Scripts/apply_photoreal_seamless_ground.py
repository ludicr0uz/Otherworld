import os
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
TEXTURES_DIR = os.path.join(PROJECT_DIR, "Scripts/downloaded_scanned_assets/textures")

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] 1. Importing High-Fidelity Scanned Textures...")
unreal.log_warning("==================================================")

def import_tex(file_path, asset_name, is_normal=False, is_linear=False):
    if not os.path.exists(file_path):
        unreal.log_error(f"File not found: {file_path}")
        return None
    task = unreal.AssetImportTask()
    task.filename = file_path
    task.destination_path = "/Game/Forest/Textures"
    task.destination_name = asset_name
    task.replace_existing = True
    task.automated = True
    task.save = True
    asset_tools.import_asset_tasks([task])
    
    tex = editor_asset_sub.load_asset(f"/Game/Forest/Textures/{asset_name}.{asset_name}")
    if tex:
        if is_normal:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property("srgb", False)
        elif is_linear:
            tex.set_editor_property("srgb", False)
        editor_asset_sub.save_loaded_asset(tex)
        unreal.log_warning(f"[AGY] Successfully imported & saved: {asset_name}")
    else:
        unreal.log_error(f"[AGY] Failed to load imported texture: {asset_name}")
    return tex

# Grass Ground (Lush green moss/grass)
t_grass_d = import_tex(os.path.join(TEXTURES_DIR, "grass_ground/grass_ground_Diffuse_2k.png"), "T_GrassGround_D")
t_grass_n = import_tex(os.path.join(TEXTURES_DIR, "grass_ground/grass_ground_nor_gl_2k.png"), "T_GrassGround_N", is_normal=True)
t_grass_r = import_tex(os.path.join(TEXTURES_DIR, "grass_ground/grass_ground_Rough_2k.png"), "T_GrassGround_R", is_linear=True)
t_grass_ao = import_tex(os.path.join(TEXTURES_DIR, "grass_ground/grass_ground_AO_2k.png"), "T_GrassGround_AO", is_linear=True)

# Forrest Ground 01 (Rich woodland earth & pine needles)
t_dirt_d = import_tex(os.path.join(TEXTURES_DIR, "forrest_ground_01/forrest_ground_01_Diffuse_2k.png"), "T_ForrestGround01_D")
t_dirt_n = import_tex(os.path.join(TEXTURES_DIR, "forrest_ground_01/forrest_ground_01_nor_gl_2k.png"), "T_ForrestGround01_N", is_normal=True)
t_dirt_r = import_tex(os.path.join(TEXTURES_DIR, "forrest_ground_01/forrest_ground_01_Rough_2k.png"), "T_ForrestGround01_R", is_linear=True)
t_dirt_ao = import_tex(os.path.join(TEXTURES_DIR, "forrest_ground_01/forrest_ground_01_AO_2k.png"), "T_ForrestGround01_AO", is_linear=True)

# Forest Ground 05 (Smooth organic macro blend map)
t_macro_d = import_tex(os.path.join(TEXTURES_DIR, "forest_ground_05/forest_ground_05_Diffuse_2k.png"), "T_ForestGround05_D")

unreal.log_warning("[AGY] All 2K scanned textures ready!")

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] 2. Rebuilding M_Forest_Ground_PBR...")
unreal.log_warning("==================================================")

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
if editor_asset_sub.does_asset_exist(mat_path):
    editor_asset_sub.delete_asset(mat_path)

ground_mat = asset_tools.create_asset("M_Forest_Ground_PBR", "/Game/Forest/Materials", unreal.Material, unreal.MaterialFactoryNew())
ground_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
ground_mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
ground_mat.set_editor_property("used_with_nanite", True)
ground_mat.set_editor_property("used_with_instanced_static_meshes", True)

# --- UV COORDINATES ---
# Layer A Micro UV: 60.0 tiling (~6.6m per tile across 400m landscape)
uv_layer_a = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1400, -600)
uv_layer_a.set_editor_property("u_tiling", 60.0)
uv_layer_a.set_editor_property("v_tiling", 60.0)

# Layer B Micro UV: 50.0 tiling (~8.0m per tile)
uv_layer_b = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1400, 200)
uv_layer_b.set_editor_property("u_tiling", 50.0)
uv_layer_b.set_editor_property("v_tiling", 50.0)

# Macro Variation UV: 3.0 tiling (~133m per organic zone)
uv_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1400, 900)
uv_macro.set_editor_property("u_tiling", 3.0)
uv_macro.set_editor_property("v_tiling", 3.0)

# --- LAYER A: LUSH FOREST MOSS & GRASS ---
samp_grass_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -700)
samp_grass_d.set_editor_property("texture", t_grass_d)
mel.connect_material_expressions(uv_layer_a, "", samp_grass_d, "UVs")

samp_grass_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -500)
samp_grass_n.set_editor_property("texture", t_grass_n)
samp_grass_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
mel.connect_material_expressions(uv_layer_a, "", samp_grass_n, "UVs")

samp_grass_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -300)
samp_grass_r.set_editor_property("texture", t_grass_r)
samp_grass_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_layer_a, "", samp_grass_r, "UVs")

samp_grass_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -100)
samp_grass_ao.set_editor_property("texture", t_grass_ao)
samp_grass_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_layer_a, "", samp_grass_ao, "UVs")

# --- LAYER B: WOODLAND SOIL & PINE NEEDLES ---
samp_dirt_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 100)
samp_dirt_d.set_editor_property("texture", t_dirt_d)
mel.connect_material_expressions(uv_layer_b, "", samp_dirt_d, "UVs")

samp_dirt_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 300)
samp_dirt_n.set_editor_property("texture", t_dirt_n)
samp_dirt_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
mel.connect_material_expressions(uv_layer_b, "", samp_dirt_n, "UVs")

samp_dirt_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 500)
samp_dirt_r.set_editor_property("texture", t_dirt_r)
samp_dirt_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_layer_b, "", samp_dirt_r, "UVs")

samp_dirt_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 700)
samp_dirt_ao.set_editor_property("texture", t_dirt_ao)
samp_dirt_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_layer_b, "", samp_dirt_ao, "UVs")

# --- MACRO BLEND MASK (Continuous natural smooth transition) ---
samp_macro_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 950)
samp_macro_mask.set_editor_property("texture", t_macro_d)
mel.connect_material_expressions(uv_macro, "", samp_macro_mask, "UVs")

# --- LERP BLENDING (Pure smooth photorealism) ---
# 1. Base Color Lerp (Layer A: Moss/Grass, Layer B: Woodland Dirt)
lerp_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -400, -400)
mel.connect_material_expressions(samp_grass_d, "RGB", lerp_d, "A")
mel.connect_material_expressions(samp_dirt_d, "RGB", lerp_d, "B")
mel.connect_material_expressions(samp_macro_mask, "R", lerp_d, "Alpha")
mel.connect_material_property(lerp_d, "", unreal.MaterialProperty.MP_BASE_COLOR)

# 2. Normal Lerp
lerp_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -400, -150)
mel.connect_material_expressions(samp_grass_n, "RGB", lerp_n, "A")
mel.connect_material_expressions(samp_dirt_n, "RGB", lerp_n, "B")
mel.connect_material_expressions(samp_macro_mask, "R", lerp_n, "Alpha")
mel.connect_material_property(lerp_n, "", unreal.MaterialProperty.MP_NORMAL)

# 3. Roughness Lerp
lerp_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -400, 100)
mel.connect_material_expressions(samp_grass_r, "R", lerp_r, "A")
mel.connect_material_expressions(samp_dirt_r, "R", lerp_r, "B")
mel.connect_material_expressions(samp_macro_mask, "R", lerp_r, "Alpha")
mel.connect_material_property(lerp_r, "", unreal.MaterialProperty.MP_ROUGHNESS)

# 4. AO Lerp
lerp_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -400, 350)
mel.connect_material_expressions(samp_grass_ao, "R", lerp_ao, "A")
mel.connect_material_expressions(samp_dirt_ao, "R", lerp_ao, "B")
mel.connect_material_expressions(samp_macro_mask, "R", lerp_ao, "Alpha")
mel.connect_material_property(lerp_ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

mel.recompile_material(ground_mat)
editor_asset_sub.save_loaded_asset(ground_mat)
unreal.log_warning("[AGY] Rebuilt M_Forest_Ground_PBR successfully!")

# --- BIND TO MESH & LEVEL ACTOR ---
terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh:
    terrain_mesh.set_material(0, ground_mat)
    editor_asset_sub.save_loaded_asset(terrain_mesh)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
for a in editor_actor_sub.get_all_level_actors():
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_static_mesh(terrain_mesh)
            smc.set_material(0, ground_mat)
            smc.set_collision_profile_name("BlockAll")
            unreal.log_warning("[AGY] Forest_Terrain_Landscape actor updated with seamless photoreal ground!")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] SEAMLESS PHOTOREALISTIC FOREST GROUND APPLIED!")
unreal.log_warning("==================================================")
