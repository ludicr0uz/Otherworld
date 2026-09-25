"""
Otherworld - Implement Dark Green & Dark Brown Photorealistic Forest Ground PBR Material
Replaces yellowish/sandy tones with rich dark woodland soil and deep forest green moss/foliage.
"""
import os
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

SCANNED_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/downloaded_scanned_assets/textures"

# 1. Import New 2K Textures
textures_to_import = [
    ("mud_forest", "mud_forest_diff_2k.png", "T_MudForest_D", False),
    ("mud_forest", "mud_forest_nor_2k.png", "T_MudForest_N", True),
    ("mud_forest", "mud_forest_rough_2k.png", "T_MudForest_R", False),
    ("mud_forest", "mud_forest_ao_2k.png", "T_MudForest_AO", False),
    ("forest_leaves_02", "forest_leaves_02_diff_2k.png", "T_ForestLeaves02_D", False),
    ("forest_leaves_02", "forest_leaves_02_nor_2k.png", "T_ForestLeaves02_N", True),
    ("forest_leaves_02", "forest_leaves_02_rough_2k.png", "T_ForestLeaves02_R", False),
    ("forest_leaves_02", "forest_leaves_02_ao_2k.png", "T_ForestLeaves02_AO", False),
    ("forest_ground_04", "forest_ground_04_diff_2k.png", "T_ForestGround04_D", False),
    ("forest_ground_04", "forest_ground_04_nor_2k.png", "T_ForestGround04_N", True),
    ("forest_ground_04", "forest_ground_04_rough_2k.png", "T_ForestGround04_R", False),
]

unreal.log_warning("[AGY] Importing 2K Dark Forest Mud & Deep Green Foliage Ground Textures...")
for sub, fn, asset_name, is_normal in textures_to_import:
    src_path = os.path.join(SCANNED_DIR, sub, fn)
    if os.path.exists(src_path):
        task = unreal.AssetImportTask()
        task.filename = src_path
        task.destination_path = "/Game/Forest/Textures"
        task.destination_name = asset_name
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])
        
        t_obj = editor_asset_sub.load_asset(f"/Game/Forest/Textures/{asset_name}.{asset_name}")
        if t_obj and is_normal:
            t_obj.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            t_obj.set_editor_property("srgb", False)
            editor_asset_sub.save_loaded_asset(t_obj)
        elif t_obj and not is_normal:
            if "R" in asset_name or "AO" in asset_name:
                t_obj.set_editor_property("srgb", False)
            editor_asset_sub.save_loaded_asset(t_obj)
        unreal.log_warning(f"[AGY] Imported Texture: {asset_name}")

# 2. Construct Master PBR Ground Material
mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
ground_mat = editor_asset_sub.load_asset(mat_path)
if not ground_mat:
    ground_mat = asset_tools.create_asset("M_Forest_Ground_PBR", "/Game/Forest/Materials", unreal.Material, unreal.MaterialFactoryNew())

mel.delete_all_material_expressions(ground_mat)

ground_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
ground_mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
ground_mat.set_editor_property("used_with_nanite", True)
ground_mat.set_editor_property("used_with_instanced_static_meshes", True)

# Load Texture Assets
tex_dirt_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_D.T_MudForest_D") or editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_D.T_ForestFloor_D")
tex_dirt_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_N.T_MudForest_N") or editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_N.T_ForestFloor_N")
tex_dirt_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_R.T_MudForest_R") or editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_R.T_ForestFloor_R")
tex_dirt_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_AO.T_MudForest_AO")

tex_grass_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_D.T_ForestLeaves02_D") or editor_asset_sub.load_asset("/Game/Forest/Textures/T_LeafyGrass_D.T_LeafyGrass_D")
tex_grass_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_N.T_ForestLeaves02_N") or editor_asset_sub.load_asset("/Game/Forest/Textures/T_LeafyGrass_N.T_LeafyGrass_N")
tex_grass_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_R.T_ForestLeaves02_R") or editor_asset_sub.load_asset("/Game/Forest/Textures/T_LeafyGrass_R.T_LeafyGrass_R")
tex_grass_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_AO.T_ForestLeaves02_AO")

# --- UV Coordinates ---
# Micro UV (Tiling 20.0 for crisp close-up soil and moss detail)
uv_micro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1200, -300)
uv_micro.set_editor_property("u_tiling", 20.0)
uv_micro.set_editor_property("v_tiling", 20.0)

# Macro UV (Tiling 3.0 for natural organic mask variation across the forest landscape)
uv_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1200, 300)
uv_macro.set_editor_property("u_tiling", 3.0)
uv_macro.set_editor_property("v_tiling", 3.0)

# --- LAYER 1: RICH DARK BROWN WOODLAND EARTH / DIRT ---
samp_dirt_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, -400)
samp_dirt_d.set_editor_property("texture", tex_dirt_d)
mel.connect_material_expressions(uv_micro, "", samp_dirt_d, "UVs")

# Dark Earth / Chocolate Brown Tint to eliminate any sandy/yellow tone: (0.45, 0.32, 0.20)
tint_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant3Vector, -900, -250)
tint_dirt.set_editor_property("constant", unreal.LinearColor(r=0.45, g=0.32, b=0.20, a=1.0))

mult_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -700, -350)
mel.connect_material_expressions(samp_dirt_d, "RGB", mult_dirt, "A")
mel.connect_material_expressions(tint_dirt, "", mult_dirt, "B")

# --- LAYER 2: DEEP DARK FOREST GREEN MOSS & UNDERGROWTH ---
samp_grass_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, -100)
samp_grass_d.set_editor_property("texture", tex_grass_d)
mel.connect_material_expressions(uv_micro, "", samp_grass_d, "UVs")

# Lush Dark Forest Green Tint (0.35, 0.65, 0.22)
tint_grass = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant3Vector, -900, 50)
tint_grass.set_editor_property("constant", unreal.LinearColor(r=0.35, g=0.65, b=0.22, a=1.0))

mult_grass = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -700, -50)
mel.connect_material_expressions(samp_grass_d, "RGB", mult_grass, "A")
mel.connect_material_expressions(tint_grass, "", mult_grass, "B")

# --- ORGANIC BLEND MASK ---
# Sample Macro Texture to produce natural woodland patches of moss/grass vs dirt paths
samp_blend_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 250)
samp_blend_mask.set_editor_property("texture", tex_grass_d)
mel.connect_material_expressions(uv_macro, "", samp_blend_mask, "UVs")

# Contrast / Balance the blend mask
add_blend = mel.create_material_expression(ground_mat, unreal.MaterialExpressionAdd, -700, 250)
mel.connect_material_expressions(samp_blend_mask, "R", add_blend, "A")
const_offset = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -900, 400)
const_offset.set_editor_property("r", -0.15)
mel.connect_material_expressions(const_offset, "", add_blend, "B")

clamp_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionClamp, -550, 250)
clamp_mask.set_editor_property("min_default", 0.0)
clamp_mask.set_editor_property("max_default", 1.0)
mel.connect_material_expressions(add_blend, "", clamp_mask, "")

# --- FINAL BASE COLOR LERP ---
lerp_base = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -400, -200)
mel.connect_material_expressions(mult_dirt, "", lerp_base, "A") # Dark Brown Dirt in low mask areas
mel.connect_material_expressions(mult_grass, "", lerp_base, "B") # Dark Green Moss in high mask areas
mel.connect_material_expressions(clamp_mask, "", lerp_base, "Alpha")
mel.connect_material_property(lerp_base, "", unreal.MaterialProperty.MP_BASE_COLOR)

# --- NORMAL MAP ---
if tex_dirt_n:
    samp_dirt_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 550)
    samp_dirt_n.set_editor_property("texture", tex_dirt_n)
    samp_dirt_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uv_micro, "", samp_dirt_n, "UVs")
    mel.connect_material_property(samp_dirt_n, "RGB", unreal.MaterialProperty.MP_NORMAL)

# --- ROUGHNESS ---
if tex_dirt_r:
    samp_dirt_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 750)
    samp_dirt_r.set_editor_property("texture", tex_dirt_r)
    samp_dirt_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_micro, "", samp_dirt_r, "UVs")
    
    # Scale roughness slightly higher for rich matte soil
    mult_rough = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -650, 750)
    const_r_scale = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -900, 900)
    const_r_scale.set_editor_property("r", 1.15)
    mel.connect_material_expressions(samp_dirt_r, "R", mult_rough, "A")
    mel.connect_material_expressions(const_r_scale, "", mult_rough, "B")
    mel.connect_material_property(mult_rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

# --- AMBIENT OCCLUSION ---
if tex_dirt_ao:
    samp_dirt_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 1050)
    samp_dirt_ao.set_editor_property("texture", tex_dirt_ao)
    samp_dirt_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_micro, "", samp_dirt_ao, "UVs")
    mel.connect_material_property(samp_dirt_ao, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

mel.recompile_material(ground_mat)
editor_asset_sub.save_loaded_asset(ground_mat)
unreal.log_warning("[AGY] Recompiled & Saved M_Forest_Ground_PBR (Dark Green & Dark Brown Soil)")

# 3. Apply to SM_ForestLandscape & Forest_Terrain_Landscape actor in Lvl_Forest
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh:
    terrain_mesh.set_material(0, ground_mat)
    editor_asset_sub.save_loaded_asset(terrain_mesh)
    unreal.log_warning("[AGY] Assigned M_Forest_Ground_PBR to SM_ForestLandscape static mesh asset!")

actors = editor_actor_sub.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_material(0, ground_mat)
            unreal.log_warning("[AGY] Bound M_Forest_Ground_PBR to Forest_Terrain_Landscape level actor!")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] DARK FOREST GREEN & DARK BROWN GROUND UPGRADE SAVED!")
unreal.log_warning("==================================================")
