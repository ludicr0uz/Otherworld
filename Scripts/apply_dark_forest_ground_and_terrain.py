"""
Otherworld - Full Terrain & Ground Material Overhaul
1. Re-imports SM_ForestLandscape with high-res 64x64 grid and normalized UVs.
2. Constructs M_Forest_Ground_PBR with deep dark green moss and rich dark brown woodland soil.
3. Updates Forest_Terrain_Landscape actor in Lvl_Forest.umap.
"""
import os
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
OBJ_FILE = os.path.join(PROJECT_DIR, "assets", "generated", "SM_ForestLandscape.obj")

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] 1. Re-importing SM_ForestLandscape with Clean Normalized UVs...")
unreal.log_warning("==================================================")

task = unreal.AssetImportTask()
task.filename = OBJ_FILE
task.destination_path = "/Game/Forest/Meshes"
task.destination_name = "SM_ForestLandscape"
task.replace_existing = True
task.automated = True
task.save = True
asset_tools.import_asset_tasks([task])

terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh:
    body_setup = terrain_mesh.get_editor_property("body_setup")
    if body_setup:
        body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    nanite_settings = terrain_mesh.get_editor_property("nanite_settings")
    if nanite_settings:
        nanite_settings.set_editor_property("enabled", True)
        terrain_mesh.set_editor_property("nanite_settings", nanite_settings)
    editor_asset_sub.save_loaded_asset(terrain_mesh)
    unreal.log_warning("[AGY] SM_ForestLandscape configured with complex collision & Nanite enabled.")

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] 2. Building M_Forest_Ground_PBR (Dark Green & Dark Brown)...")
unreal.log_warning("==================================================")

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
ground_mat = editor_asset_sub.load_asset(mat_path)
if not ground_mat:
    ground_mat = asset_tools.create_asset("M_Forest_Ground_PBR", "/Game/Forest/Materials", unreal.Material, unreal.MaterialFactoryNew())

mel.delete_all_material_expressions(ground_mat)

ground_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
ground_mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
ground_mat.set_editor_property("used_with_nanite", True)
ground_mat.set_editor_property("used_with_instanced_static_meshes", True)

# Textures
tex_dirt_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_D.T_MudForest_D")
tex_dirt_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_N.T_MudForest_N")
tex_dirt_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_R.T_MudForest_R")
tex_dirt_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_AO.T_MudForest_AO")

tex_grass_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_D.T_ForestLeaves02_D")
tex_grass_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_N.T_ForestLeaves02_N")
tex_grass_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_R.T_ForestLeaves02_R")
tex_grass_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_AO.T_ForestLeaves02_AO")

# UV coordinates
# Micro: 40.0 tiling (10m x 10m per tile across 400m landscape)
uv_micro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1200, -300)
uv_micro.set_editor_property("u_tiling", 40.0)
uv_micro.set_editor_property("v_tiling", 40.0)

# Macro: 2.5 tiling (160m x 160m wide organic variation)
uv_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1200, 300)
uv_macro.set_editor_property("u_tiling", 2.5)
uv_macro.set_editor_property("v_tiling", 2.5)

# --- LAYER 1: DEEP RICH DARK BROWN WOODLAND EARTH ---
samp_dirt_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, -400)
samp_dirt_d.set_editor_property("texture", tex_dirt_d)
mel.connect_material_expressions(uv_micro, "", samp_dirt_d, "UVs")

# Dark Umber Dirt Tint (0.30, 0.18, 0.10)
tint_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant3Vector, -900, -250)
tint_dirt.set_editor_property("constant", unreal.LinearColor(r=0.30, g=0.18, b=0.10, a=1.0))

mult_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -700, -350)
mel.connect_material_expressions(samp_dirt_d, "RGB", mult_dirt, "A")
mel.connect_material_expressions(tint_dirt, "", mult_dirt, "B")

# --- LAYER 2: LUSH DARK FOREST GREEN MOSS / GRASS ---
samp_grass_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, -100)
samp_grass_d.set_editor_property("texture", tex_grass_d)
mel.connect_material_expressions(uv_micro, "", samp_grass_d, "UVs")

# Dark Forest Green Tint (0.22, 0.50, 0.15)
tint_grass = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant3Vector, -900, 50)
tint_grass.set_editor_property("constant", unreal.LinearColor(r=0.22, g=0.50, b=0.15, a=1.0))

mult_grass = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -700, -50)
mel.connect_material_expressions(samp_grass_d, "RGB", mult_grass, "A")
mel.connect_material_expressions(tint_grass, "", mult_grass, "B")

# --- ORGANIC BLEND MASK ---
samp_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 250)
samp_mask.set_editor_property("texture", tex_grass_d)
mel.connect_material_expressions(uv_macro, "", samp_mask, "UVs")

lerp_base = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -450, -200)
mel.connect_material_expressions(mult_dirt, "", lerp_base, "A")   # Rich dark brown dirt
mel.connect_material_expressions(mult_grass, "", lerp_base, "B")  # Dark forest green moss
mel.connect_material_expressions(samp_mask, "R", lerp_base, "Alpha")
mel.connect_material_property(lerp_base, "", unreal.MaterialProperty.MP_BASE_COLOR)

# --- NORMAL MAP ---
if tex_dirt_n:
    samp_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 500)
    samp_n.set_editor_property("texture", tex_dirt_n)
    samp_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uv_micro, "", samp_n, "UVs")
    mel.connect_material_property(samp_n, "RGB", unreal.MaterialProperty.MP_NORMAL)

# --- ROUGHNESS (Matte soil / moss ~0.9) ---
if tex_dirt_r:
    samp_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 700)
    samp_r.set_editor_property("texture", tex_dirt_r)
    samp_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_micro, "", samp_r, "UVs")
    
    mult_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -650, 700)
    c_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -900, 850)
    c_r.set_editor_property("r", 1.2)
    mel.connect_material_expressions(samp_r, "R", mult_r, "A")
    mel.connect_material_expressions(c_r, "", mult_r, "B")
    mel.connect_material_property(mult_r, "", unreal.MaterialProperty.MP_ROUGHNESS)

# --- AMBIENT OCCLUSION ---
if tex_dirt_ao:
    samp_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 1000)
    samp_ao.set_editor_property("texture", tex_dirt_ao)
    samp_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_micro, "", samp_ao, "UVs")
    mel.connect_material_property(samp_ao, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

mel.recompile_material(ground_mat)
editor_asset_sub.save_loaded_asset(ground_mat)
unreal.log_warning("[AGY] M_Forest_Ground_PBR recompiled and saved!")

if terrain_mesh:
    terrain_mesh.set_material(0, ground_mat)
    editor_asset_sub.save_loaded_asset(terrain_mesh)

# 3. Update Level Actor
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
for a in editor_actor_sub.get_all_level_actors():
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_static_mesh(terrain_mesh)
            smc.set_material(0, ground_mat)
            smc.set_collision_profile_name("BlockAll")
            smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            unreal.log_warning("[AGY] Updated Forest_Terrain_Landscape level actor with new mesh and material!")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] COMPLETE DARK GREEN & DARK BROWN GROUND OVERHAUL SAVED!")
unreal.log_warning("==================================================")
