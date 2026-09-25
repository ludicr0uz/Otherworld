import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"

# 1. Delete old material asset completely to avoid stale nodes
if editor_asset_sub.does_asset_exist(mat_path):
    unreal.log_warning("[AGY] Deleting existing M_Forest_Ground_PBR...")
    editor_asset_sub.delete_asset(mat_path)

# 2. Create fresh Material
unreal.log_warning("[AGY] Creating brand new clean M_Forest_Ground_PBR...")
ground_mat = asset_tools.create_asset("M_Forest_Ground_PBR", "/Game/Forest/Materials", unreal.Material, unreal.MaterialFactoryNew())

ground_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
ground_mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
ground_mat.set_editor_property("used_with_nanite", True)
ground_mat.set_editor_property("used_with_instanced_static_meshes", True)

# Textures
tex_dirt_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_D.T_MudForest_D")
tex_dirt_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_N.T_MudForest_N")
tex_dirt_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_R.T_MudForest_R")
tex_dirt_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_MudForest_AO.T_MudForest_AO")

tex_moss_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestLeaves02_D.T_ForestLeaves02_D")

# UV coordinates
# Micro UV: 30.0 tiling (~13m repetition)
uv_micro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1200, -300)
uv_micro.set_editor_property("u_tiling", 30.0)
uv_micro.set_editor_property("v_tiling", 30.0)

# Macro UV: 2.0 tiling (~200m organic patches)
uv_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1200, 300)
uv_macro.set_editor_property("u_tiling", 2.0)
uv_macro.set_editor_property("v_tiling", 2.0)

# --- LAYER 1: RICH DARK BROWN WOODLAND SOIL ---
samp_dirt_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, -400)
samp_dirt_d.set_editor_property("texture", tex_dirt_d)
mel.connect_material_expressions(uv_micro, "", samp_dirt_d, "UVs")

# Dark Earth Umber Tint (0.25, 0.15, 0.08)
tint_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant3Vector, -900, -250)
tint_dirt.set_editor_property("constant", unreal.LinearColor(r=0.25, g=0.15, b=0.08, a=1.0))

mult_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -700, -350)
mel.connect_material_expressions(samp_dirt_d, "RGB", mult_dirt, "A")
mel.connect_material_expressions(tint_dirt, "", mult_dirt, "B")

# --- LAYER 2: DEEP FOREST GREEN MOSS ---
samp_moss_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, -100)
samp_moss_d.set_editor_property("texture", tex_moss_d)
mel.connect_material_expressions(uv_micro, "", samp_moss_d, "UVs")

# Deep Pine & Moss Green Tint (0.12, 0.45, 0.08)
tint_moss = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant3Vector, -900, 50)
tint_moss.set_editor_property("constant", unreal.LinearColor(r=0.12, g=0.45, b=0.08, a=1.0))

mult_moss = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -700, -50)
mel.connect_material_expressions(samp_moss_d, "RGB", mult_moss, "A")
mel.connect_material_expressions(tint_moss, "", mult_moss, "B")

# --- MACRO BLEND MASK (Organic Moss Coverage) ---
samp_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -900, 250)
samp_mask.set_editor_property("texture", tex_moss_d)
mel.connect_material_expressions(uv_macro, "", samp_mask, "UVs")

# Add a contrast / bias to make moss patches dominant (~60% green moss, 40% dark soil)
c_bias = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -700, 250)
c_bias.set_editor_property("r", 0.2)

add_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionAdd, -550, 200)
mel.connect_material_expressions(samp_mask, "R", add_mask, "A")
mel.connect_material_expressions(c_bias, "", add_mask, "B")

clamp_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionClamp, -420, 200)
mel.connect_material_expressions(add_mask, "", clamp_mask, "Input")

# Blend Dirt (A) and Moss (B) using Macro Mask (Alpha)
lerp_base = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -250, -200)
mel.connect_material_expressions(mult_dirt, "", lerp_base, "A")
mel.connect_material_expressions(mult_moss, "", lerp_base, "B")
mel.connect_material_expressions(clamp_mask, "", lerp_base, "Alpha")

# Connect to Material Base Color
mel.connect_material_property(lerp_base, "", unreal.MaterialProperty.MP_BASE_COLOR)

# --- NORMAL MAP ---
if tex_dirt_n:
    samp_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -600, 400)
    samp_n.set_editor_property("texture", tex_dirt_n)
    samp_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uv_micro, "", samp_n, "UVs")
    mel.connect_material_property(samp_n, "RGB", unreal.MaterialProperty.MP_NORMAL)

# --- ROUGHNESS (0.92 matte soil/moss) ---
if tex_dirt_r:
    samp_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -600, 600)
    samp_r.set_editor_property("texture", tex_dirt_r)
    samp_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_micro, "", samp_r, "UVs")
    
    c_rough = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -600, 750)
    c_rough.set_editor_property("r", 1.1)
    
    mult_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionMultiply, -400, 600)
    mel.connect_material_expressions(samp_r, "R", mult_r, "A")
    mel.connect_material_expressions(c_rough, "", mult_r, "B")
    mel.connect_material_property(mult_r, "", unreal.MaterialProperty.MP_ROUGHNESS)

# --- AMBIENT OCCLUSION ---
if tex_dirt_ao:
    samp_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -600, 900)
    samp_ao.set_editor_property("texture", tex_dirt_ao)
    samp_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_expressions(uv_micro, "", samp_ao, "UVs")
    mel.connect_material_property(samp_ao, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

mel.recompile_material(ground_mat)
editor_asset_sub.save_loaded_asset(ground_mat)
unreal.log_warning("[AGY] M_Forest_Ground_PBR recompiled and saved!")

# 3. Assign to SM_ForestLandscape Static Mesh
terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh:
    terrain_mesh.set_material(0, ground_mat)
    editor_asset_sub.save_loaded_asset(terrain_mesh)
    unreal.log_warning("[AGY] SM_ForestLandscape mesh material set to M_Forest_Ground_PBR!")

# 4. Assign to Level Actor
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
actors = editor_actor_sub.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_static_mesh(terrain_mesh)
            smc.set_material(0, ground_mat)
            smc.set_collision_profile_name("BlockAll")
            unreal.log_warning("[AGY] Forest_Terrain_Landscape actor updated with ground_mat!")

level_editor_sub.save_current_level()
unreal.log_warning("[AGY] Lvl_Forest saved successfully!")
