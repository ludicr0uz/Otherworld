import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] ROOT CAUSE FIX: Ground Textures, Shaders, Exposure & Lighting")
unreal.log_warning("==================================================")

# 1. FORCE NEVER_STREAM = TRUE ON ALL GROUND TEXTURES
tex_names = [
    "T_GrassGround_D", "T_GrassGround_N", "T_GrassGround_R", "T_GrassGround_AO",
    "T_ForrestGround01_D", "T_ForrestGround01_N", "T_ForrestGround01_R", "T_ForrestGround01_AO",
    "T_ForestGround05_D", "T_ForestLeaves02_D", "T_MudForest_D", "T_MudForest_N"
]

for tn in tex_names:
    t = editor_asset_sub.load_asset(f"/Game/Forest/Textures/{tn}.{tn}")
    if t:
        t.set_editor_property("never_stream", True)
        t.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
        editor_asset_sub.save_loaded_asset(t)
        unreal.log_warning(f"[AGY] Texture {tn} set to NeverStream=True (Full 2K resolution guaranteed)")

# 2. REBUILD M_Forest_Ground_PBR WITH CRISP PBR DEFINITION
mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
if editor_asset_sub.does_asset_exist(mat_path):
    editor_asset_sub.delete_asset(mat_path)

ground_mat = asset_tools.create_asset("M_Forest_Ground_PBR", "/Game/Forest/Materials", unreal.Material, unreal.MaterialFactoryNew())
ground_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
ground_mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
ground_mat.set_editor_property("used_with_nanite", True)
ground_mat.set_editor_property("used_with_instanced_static_meshes", True)

t_grass_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_GrassGround_D.T_GrassGround_D")
t_grass_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_GrassGround_N.T_GrassGround_N")
t_grass_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_GrassGround_R.T_GrassGround_R")
t_grass_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_GrassGround_AO.T_GrassGround_AO")

t_dirt_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForrestGround01_D.T_ForrestGround01_D")
t_dirt_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForrestGround01_N.T_ForrestGround01_N")
t_dirt_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForrestGround01_R.T_ForrestGround01_R")
t_dirt_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForrestGround01_AO.T_ForrestGround01_AO")

t_macro_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestGround05_D.T_ForestGround05_D")

# UV coordinates
# Grass/Moss Micro UV: 40.0 tiling (10m x 10m per tile across 400m landscape = ~5mm/pixel detail)
uv_grass = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1400, -600)
uv_grass.set_editor_property("u_tiling", 40.0)
uv_grass.set_editor_property("v_tiling", 40.0)

# Dirt/Needles Micro UV: 35.0 tiling (11.4m per tile)
uv_dirt = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1400, 200)
uv_dirt.set_editor_property("u_tiling", 35.0)
uv_dirt.set_editor_property("v_tiling", 35.0)

# Macro Variation UV: 2.5 tiling (160m wide organic zones)
uv_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -1400, 900)
uv_macro.set_editor_property("u_tiling", 2.5)
uv_macro.set_editor_property("v_tiling", 2.5)

# --- LAYER A: LUSH MOSS & WOODLAND GRASS ---
samp_grass_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -700)
samp_grass_d.set_editor_property("texture", t_grass_d)
mel.connect_material_expressions(uv_grass, "", samp_grass_d, "UVs")

samp_grass_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -500)
samp_grass_n.set_editor_property("texture", t_grass_n)
samp_grass_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
mel.connect_material_expressions(uv_grass, "", samp_grass_n, "UVs")

samp_grass_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -300)
samp_grass_r.set_editor_property("texture", t_grass_r)
samp_grass_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_grass, "", samp_grass_r, "UVs")

samp_grass_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, -100)
samp_grass_ao.set_editor_property("texture", t_grass_ao)
samp_grass_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_grass, "", samp_grass_ao, "UVs")

# --- LAYER B: DARK WOODLAND EARTH & PINE NEEDLES ---
samp_dirt_d = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 100)
samp_dirt_d.set_editor_property("texture", t_dirt_d)
mel.connect_material_expressions(uv_dirt, "", samp_dirt_d, "UVs")

samp_dirt_n = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 300)
samp_dirt_n.set_editor_property("texture", t_dirt_n)
samp_dirt_n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
mel.connect_material_expressions(uv_dirt, "", samp_dirt_n, "UVs")

samp_dirt_r = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 500)
samp_dirt_r.set_editor_property("texture", t_dirt_r)
samp_dirt_r.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_dirt, "", samp_dirt_r, "UVs")

samp_dirt_ao = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 700)
samp_dirt_ao.set_editor_property("texture", t_dirt_ao)
samp_dirt_ao.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
mel.connect_material_expressions(uv_dirt, "", samp_dirt_ao, "UVs")

# --- MACRO BLEND MASK ---
samp_macro_mask = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -1000, 950)
samp_macro_mask.set_editor_property("texture", t_macro_d)
mel.connect_material_expressions(uv_macro, "", samp_macro_mask, "UVs")

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

# 3. CONFIGURE SM_ForestLandscape STATIC MESH
terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh:
    terrain_mesh.set_material(0, ground_mat)
    editor_asset_sub.save_loaded_asset(terrain_mesh)

# 4. UPDATE LEVEL, LIGHTING & POST PROCESS VOLUME
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

for a in editor_actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    
    # A. Terrain Actor
    if lbl == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_static_mesh(terrain_mesh)
            smc.set_material(0, ground_mat)
            smc.set_collision_profile_name("BlockAll")
            unreal.log_warning("[AGY] Forest_Terrain_Landscape updated!")
    
    # B. PostProcessVolume - Fix Camera Overexposure!
    elif lbl == "PostProcessVolume_Forest" or isinstance(a, unreal.PostProcessVolume):
        a.set_editor_property("unbound", True)
        settings = a.get_editor_property("settings")
        # Standard daylight forest exposure: MinEV100 = 8.0, MaxEV100 = 14.0, Bias = 0.0
        settings.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
        settings.set_editor_property("auto_exposure_min_brightness", 8.0)
        settings.set_editor_property("auto_exposure_max_brightness", 14.0)
        settings.set_editor_property("auto_exposure_bias", 0.0)
        a.set_editor_property("settings", settings)
        unreal.log_warning("[AGY] PostProcessVolume auto exposure calibrated to realistic daylight EV100 (8.0 to 14.0)!")
    
    # C. Directional Light
    elif isinstance(a, unreal.DirectionalLight):
        comp = a.get_component_by_class(unreal.DirectionalLightComponent)
        if comp:
            comp.set_editor_property("intensity", 6.0) # Realistic sun lux ratio
            comp.set_editor_property("light_color", unreal.Color(r=255, g=248, b=235, a=255))
            comp.set_editor_property("cast_shadows", True)
            comp.set_editor_property("dynamic_shadow_distance_movable_light", 15000.0)
            unreal.log_warning("[AGY] DirectionalLight configured with realistic daylight intensity (6.0) and warm sunlight color.")
    
    # D. SkyLight
    elif isinstance(a, unreal.SkyLight):
        comp = a.get_component_by_class(unreal.SkyLightComponent)
        if comp:
            comp.set_editor_property("intensity", 1.2)
            comp.set_editor_property("real_time_capture", True)
            comp.set_editor_property("light_color", unreal.Color(r=200, g=225, b=255, a=255))
            unreal.log_warning("[AGY] SkyLight configured with real-time capture and soft ambient bounce.")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] ROOT CAUSE FIX COMPLETE & LEVEL SAVED!")
unreal.log_warning("==================================================")
