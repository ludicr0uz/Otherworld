"""
Otherworld - Complete Photorealistic Ground & Grass Upgrade
1. Imports 2K PBR scanned ground textures (forest floor, leafy grass, decayed forest leaves).
2. Imports 4 new 3D photogrammetry foliage models (grass clumps, tall grass, woodland ferns, moss patches).
3. Builds an advanced PBR micro/macro blended terrain material with normal, roughness, and AO mapping.
4. Eliminates overlapping bedrock cubes (resolving all Z-fighting flicker).
5. Populates dense 3D grass, ferns, and moss using GPU instancing (HISM) with zero-drag character navigation.
"""
import math
import random
import os
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

SCANNED_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/downloaded_scanned_assets"

# -------------------------------------------------------------------------
# Step 1: Import 2K Ground Textures
# -------------------------------------------------------------------------
unreal.log("==================================================")
unreal.log("[AGY] 1. Importing 2K Scanned Ground Textures...")
unreal.log("==================================================")

texture_imports = [
    ("forest_floor", "forest_floor_Diffuse_2k.png", "T_ForestFloor_D", False),
    ("forest_floor", "forest_floor_nor_gl_2k.png", "T_ForestFloor_N", True),
    ("forest_floor", "forest_floor_Rough_2k.png", "T_ForestFloor_R", False),
    ("forest_floor", "forest_floor_AO_2k.png", "T_ForestFloor_AO", False),
    ("leafy_grass", "leafy_grass_Diffuse_2k.png", "T_LeafyGrass_D", False),
    ("leafy_grass", "leafy_grass_nor_gl_2k.png", "T_LeafyGrass_N", True),
    ("leafy_grass", "leafy_grass_Rough_2k.png", "T_LeafyGrass_R", False),
    ("leaves_forest_ground", "leaves_forest_ground_Diffuse_2k.png", "T_ForestLeaves_D", False),
]

for sub_dir, file_name, asset_name, is_normal in texture_imports:
    src_file = os.path.join(SCANNED_DIR, "textures", sub_dir, file_name)
    if os.path.exists(src_file):
        task = unreal.AssetImportTask()
        task.filename = src_file
        task.destination_path = "/Game/Forest/Textures"
        task.destination_name = asset_name
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])
        tex_asset = editor_asset_sub.load_asset(f"/Game/Forest/Textures/{asset_name}.{asset_name}")
        if tex_asset:
            editor_asset_sub.save_loaded_asset(tex_asset)
        unreal.log_warning(f"[AGY] Imported texture: {asset_name}")

# -------------------------------------------------------------------------
# Step 2: Build Advanced PBR Micro/Macro Terrain Material
# -------------------------------------------------------------------------
unreal.log("==================================================")
unreal.log("[AGY] 2. Building Photorealistic Ground Material...")
unreal.log("==================================================")

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
if editor_asset_sub.does_asset_exist(mat_path):
    editor_asset_sub.delete_asset(mat_path)

mat_factory = unreal.MaterialFactoryNew()
ground_mat = asset_tools.create_asset("M_Forest_Ground_PBR", "/Game/Forest/Materials", unreal.Material, mat_factory)

if ground_mat:
    ground_mat.set_editor_property("used_with_nanite", True)

    tex_ff_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_D.T_ForestFloor_D")
    tex_ff_n = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_N.T_ForestFloor_N")
    tex_ff_r = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_R.T_ForestFloor_R")
    tex_ff_ao = editor_asset_sub.load_asset("/Game/Forest/Textures/T_ForestFloor_AO.T_ForestFloor_AO")
    tex_lg_d = editor_asset_sub.load_asset("/Game/Forest/Textures/T_LeafyGrass_D.T_LeafyGrass_D")

    # 1. Micro UV Coordinates (Tiling for close-up crisp detail: scale 0.006)
    coord_micro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -800, -200)
    coord_micro.set_editor_property("u_tiling", 24.0)
    coord_micro.set_editor_property("v_tiling", 24.0)

    # 2. Macro UV Coordinates (Large scale for distance variation: scale 0.0006)
    coord_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureCoordinate, -800, 100)
    coord_macro.set_editor_property("u_tiling", 2.5)
    coord_macro.set_editor_property("v_tiling", 2.5)

    # Micro Diffuse Sample (Forest Floor)
    diff_micro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -500, -200)
    diff_micro.set_editor_property("texture", tex_ff_d)
    mel.connect_material_expressions(coord_micro, "", diff_micro, "UVs")

    # Macro Diffuse Sample (Leafy Grass)
    diff_macro = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -500, 100)
    diff_macro.set_editor_property("texture", tex_lg_d)
    mel.connect_material_expressions(coord_macro, "", diff_macro, "UVs")

    # Linear Interpolate Micro + Macro to break tiling repetition
    lerp_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionLinearInterpolate, -250, -100)
    mel.connect_material_expressions(diff_micro, "RGB", lerp_node, "A")
    mel.connect_material_expressions(diff_macro, "RGB", lerp_node, "B")

    # Blend weight constant (0.35 macro leafy grass over rich forest loam)
    alpha_const = mel.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -400, 0)
    alpha_const.set_editor_property("r", 0.35)
    mel.connect_material_expressions(alpha_const, "", lerp_node, "Alpha")

    mel.connect_material_property(lerp_node, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # Normal Map Sample
    if tex_ff_n:
        nor_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -500, 300)
        nor_node.set_editor_property("texture", tex_ff_n)
        nor_node.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        mel.connect_material_expressions(coord_micro, "", nor_node, "UVs")
        mel.connect_material_property(nor_node, "RGB", unreal.MaterialProperty.MP_NORMAL)

    # Roughness Sample
    if tex_ff_r:
        rough_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -500, 500)
        rough_node.set_editor_property("texture", tex_ff_r)
        mel.connect_material_expressions(coord_micro, "", rough_node, "UVs")
        mel.connect_material_property(rough_node, "R", unreal.MaterialProperty.MP_ROUGHNESS)

    # Ambient Occlusion Sample
    if tex_ff_ao:
        ao_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -500, 700)
        ao_node.set_editor_property("texture", tex_ff_ao)
        mel.connect_material_expressions(coord_micro, "", ao_node, "UVs")
        mel.connect_material_property(ao_node, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    mel.recompile_material(ground_mat)
    editor_asset_sub.save_asset(mat_path)
    unreal.log_warning("[AGY] Created & Compiled Master PBR Ground Material!")

# Apply to terrain mesh asset
terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh and ground_mat:
    terrain_mesh.set_material(0, ground_mat)
    editor_asset_sub.save_loaded_asset(terrain_mesh)

# -------------------------------------------------------------------------
# Step 3: Import 4 New Photogrammetry Foliage Models
# -------------------------------------------------------------------------
unreal.log("==================================================")
unreal.log("[AGY] 3. Importing Scanned Foliage & Grass Models...")
unreal.log("==================================================")

new_models = ["grass_medium_01", "grass_medium_02", "fern_02", "moss_01"]
imported_foliage_meshes = {}

for mid in new_models:
    gltf_file = os.path.join(SCANNED_DIR, mid, f"{mid}_1k.gltf")
    if os.path.exists(gltf_file):
        dest_folder = f"/Game/Forest/Scanned/{mid}"
        task = unreal.AssetImportTask()
        task.filename = gltf_file
        task.destination_path = dest_folder
        task.destination_name = f"SM_{mid}"
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])

        assets = editor_asset_sub.list_assets(dest_folder, recursive=True)
        sm_assets = [a for a in assets if "StaticMeshes" in a or "SM_" in a]
        if sm_assets:
            mesh_obj = editor_asset_sub.load_asset(sm_assets[0])
            if mesh_obj and isinstance(mesh_obj, unreal.StaticMesh):
                imported_foliage_meshes[mid] = mesh_obj
                nanite_s = mesh_obj.get_editor_property("nanite_settings")
                if nanite_s:
                    nanite_s.set_editor_property("enabled", True)
                    mesh_obj.set_editor_property("nanite_settings", nanite_s)
                editor_asset_sub.save_loaded_asset(mesh_obj)
                unreal.log_warning(f"[AGY] Imported 3D foliage mesh: {mid} -> {sm_assets[0]}")

# -------------------------------------------------------------------------
# Step 4: Populate Lvl_Forest with Upgraded Ground & 3D Grass
# -------------------------------------------------------------------------
unreal.log("==================================================")
unreal.log("[AGY] 4. Updating Lvl_Forest: Eliminating Flicker & Populating 3D Biome...")
unreal.log("==================================================")

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

# Clean existing props and bedrock to eliminate Z-fighting
for a in editor_actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    if any(w in lbl for w in ["Bedrock", "HISM_", "Tree", "Rock", "Bush", "Log", "Fern", "Stump", "Plant", "Scanned"]):
        unreal.log(f"[AGY] Removing old/overlapping actor: {lbl}")
        editor_actor_sub.destroy_actor(a)

# Ensure Forest_Terrain_Landscape is solid, correctly positioned, and has M_Forest_Ground_PBR
for a in editor_actor_sub.get_all_level_actors():
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc and ground_mat:
            smc.set_material(0, ground_mat)
            smc.set_collision_profile_name("BlockAll")
            smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            a.set_actor_location(unreal.Vector(0, 0, 0), False, False)
            unreal.log_warning("[AGY] Applied M_Forest_Ground_PBR directly to Forest_Terrain_Landscape actor!")

def get_terrain_elevation(x, y):
    dist = math.sqrt(x * x + y * y)
    if dist < 4500.0:
        return 0.0
    else:
        elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
        edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
        return elevation + (edge_factor ** 2) * 1750.0

# Master catalog of meshes to instantiate
hism_configs = {
    "Tree_Pine": {
        "path": "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a",
        "collision": True, "shadows": True
    },
    "Tree_Deciduous": {
        "path": "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
        "collision": True, "shadows": True
    },
    "Stump_01": {
        "path": "/Game/Forest/Scanned/tree_stump_01/tree_stump_01_1k/StaticMeshes/SM_tree_stump_01.SM_tree_stump_01",
        "collision": True, "shadows": True
    },
    "Stump_02": {
        "path": "/Game/Forest/Scanned/tree_stump_02/tree_stump_02_1k/StaticMeshes/SM_tree_stump_02.SM_tree_stump_02",
        "collision": True, "shadows": True
    },
    "Root_Cluster": {
        "path": "/Game/Forest/Scanned/root_cluster_01/root_cluster_01_1k/StaticMeshes/SM_root_cluster_01.SM_root_cluster_01",
        "collision": True, "shadows": True
    },
    "Rock_Granite": {
        "path": "/Game/Forest/Scanned/rock_07/rock_07_1k/StaticMeshes/SM_rock_07.SM_rock_07",
        "collision": True, "shadows": True
    },
    "Rock_Moss": {
        "path": "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/StaticMeshes/rock_moss_set_01_rock01.rock_moss_set_01_rock01",
        "collision": True, "shadows": True
    },
    "Shrub_01": {
        "path": "/Game/Forest/Scanned/shrub_01/shrub_01_1k/StaticMeshes/SM_shrub_01.SM_shrub_01",
        "collision": False, "shadows": True
    },
    "Shrub_03": {
        "path": "/Game/Forest/Scanned/shrub_03/shrub_03_1k/StaticMeshes/shrub_03_a.shrub_03_a",
        "collision": False, "shadows": True
    },
    "Flowers": {
        "path": "/Game/Forest/Scanned/periwinkle_plant/periwinkle_plant_1k/StaticMeshes/periwinkle_plant_01_LOD0.periwinkle_plant_01_LOD0",
        "collision": False, "shadows": False
    },
    "Grass_Medium": {
        "path": "/Game/Forest/Scanned/grass_medium_01/grass_medium_01_1k/StaticMeshes/grass_medium_01_large_a_LOD0.grass_medium_01_large_a_LOD0",
        "collision": False, "shadows": False
    },
    "Grass_Tall": {
        "path": "/Game/Forest/Scanned/grass_medium_02/grass_medium_02_1k/StaticMeshes/grass_medium_02_a.grass_medium_02_a",
        "collision": False, "shadows": False
    },
    "Ferns": {
        "path": "/Game/Forest/Scanned/fern_02/fern_02_1k/StaticMeshes/fern_02_a.fern_02_a",
        "collision": False, "shadows": False
    },
    "Moss_Patch": {
        "path": "/Game/Forest/Scanned/moss_01/moss_01_1k/StaticMeshes/moss_01_a_LOD0.moss_01_a_LOD0",
        "collision": False, "shadows": False
    }
}

hism_components = {}

for name, cfg in hism_configs.items():
    mesh = editor_asset_sub.load_asset(cfg["path"])
    if not mesh:
        # Fallback search if path differed slightly
        pkg_path = cfg["path"].rsplit("/", 2)[0]
        found = editor_asset_sub.list_assets(pkg_path, recursive=True)
        sm_f = [a for a in found if ("StaticMeshes" in a or "SM_" in a) and not "Material" in a]
        if sm_f:
            mesh = editor_asset_sub.load_asset(sm_f[0])

    if not mesh:
        unreal.log_error(f"[AGY] Failed to load static mesh for {name}")
        continue

    unreal.log_warning(f"[AGY] Loaded mesh for {name}: {mesh.get_name()}")

    actor = editor_actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    actor.set_actor_label(f"HISM_{name}")

    comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
    comp.set_static_mesh(mesh)
    actor.set_editor_property("root_component", comp)

    if cfg["collision"]:
        comp.set_collision_profile_name("BlockAll")
        comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    else:
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)

    comp.set_editor_property("cast_shadow", cfg["shadows"])
    hism_components[name] = comp

random.seed(2026)

# 1. Scanned Trees (Strict 100% Vertical Alignment)
unreal.log_warning("[AGY] Placing 160 Scanned Trees...")
for i in range(160):
    dist = random.uniform(850.0, 16500.0)
    theta = random.uniform(0, 2 * math.pi)
    tx = dist * math.cos(theta)
    ty = dist * math.sin(theta)
    tz = get_terrain_elevation(tx, ty)

    yaw = random.uniform(0.0, 360.0)
    rot = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)

    if random.random() < 0.65 and "Tree_Pine" in hism_components:
        scale_val = random.uniform(3.8, 5.8)
        tf = unreal.Transform(
            location=unreal.Vector(tx, ty, tz - 12.0),
            rotation=rot,
            scale=unreal.Vector(scale_val, scale_val, scale_val)
        )
        hism_components["Tree_Pine"].add_instance(tf)
    elif "Tree_Deciduous" in hism_components:
        scale_val = random.uniform(3.2, 4.8)
        tf = unreal.Transform(
            location=unreal.Vector(tx, ty, tz - 12.0),
            rotation=rot,
            scale=unreal.Vector(scale_val, scale_val, scale_val)
        )
        hism_components["Tree_Deciduous"].add_instance(tf)

# 2. Scanned Rocks & Boulders
unreal.log_warning("[AGY] Placing 80 Scanned Rocks & Boulders...")
for i in range(80):
    dist = random.uniform(800.0, 15500.0)
    theta = random.uniform(0, 2 * math.pi)
    rx = dist * math.cos(theta)
    ry = dist * math.sin(theta)
    rz = get_terrain_elevation(rx, ry)

    rot = unreal.Rotator(pitch=random.uniform(-5.0, 5.0), yaw=random.uniform(0.0, 360.0), roll=random.uniform(-5.0, 5.0))
    scale_val = random.uniform(2.2, 4.5)

    tf = unreal.Transform(
        location=unreal.Vector(rx, ry, rz - 15.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    if random.random() < 0.5 and "Rock_Granite" in hism_components:
        hism_components["Rock_Granite"].add_instance(tf)
    elif "Rock_Moss" in hism_components:
        hism_components["Rock_Moss"].add_instance(tf)

# 3. Scanned Stumps & Roots
unreal.log_warning("[AGY] Placing 60 Scanned Stumps & Roots...")
for i in range(60):
    dist = random.uniform(900.0, 15000.0)
    theta = random.uniform(0, 2 * math.pi)
    sx = dist * math.cos(theta)
    sy = dist * math.sin(theta)
    sz = get_terrain_elevation(sx, sy)

    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(2.0, 3.5)

    tf = unreal.Transform(
        location=unreal.Vector(sx, sy, sz - 10.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    rnd = random.random()
    if rnd < 0.35 and "Stump_01" in hism_components:
        hism_components["Stump_01"].add_instance(tf)
    elif rnd < 0.70 and "Stump_02" in hism_components:
        hism_components["Stump_02"].add_instance(tf)
    elif "Root_Cluster" in hism_components:
        hism_components["Root_Cluster"].add_instance(tf)

# 4. Dense 3D Grass Clumps & Tall Grass (Clearing & Undergrowth)
unreal.log_warning("[AGY] Placing 450 Photorealistic 3D Grass Clumps & Moss Patches...")
for i in range(250):
    dist = random.uniform(300.0, 14000.0)
    theta = random.uniform(0, 2 * math.pi)
    gx = dist * math.cos(theta)
    gy = dist * math.sin(theta)
    gz = get_terrain_elevation(gx, gy)

    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(1.6, 3.2)

    tf = unreal.Transform(
        location=unreal.Vector(gx, gy, gz - 3.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    if "Grass_Medium" in hism_components:
        hism_components["Grass_Medium"].add_instance(tf)

for i in range(160):
    dist = random.uniform(400.0, 15000.0)
    theta = random.uniform(0, 2 * math.pi)
    gx = dist * math.cos(theta)
    gy = dist * math.sin(theta)
    gz = get_terrain_elevation(gx, gy)

    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(1.8, 3.5)

    tf = unreal.Transform(
        location=unreal.Vector(gx, gy, gz - 4.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    if "Grass_Tall" in hism_components:
        hism_components["Grass_Tall"].add_instance(tf)

# 5. Woodland Ferns & Moss Clusters
for i in range(90):
    dist = random.uniform(700.0, 14500.0)
    theta = random.uniform(0, 2 * math.pi)
    fx = dist * math.cos(theta)
    fy = dist * math.sin(theta)
    fz = get_terrain_elevation(fx, fy)

    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(1.5, 2.8)

    tf = unreal.Transform(
        location=unreal.Vector(fx, fy, fz - 4.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    if "Ferns" in hism_components:
        hism_components["Ferns"].add_instance(tf)

for i in range(70):
    dist = random.uniform(600.0, 14000.0)
    theta = random.uniform(0, 2 * math.pi)
    mx = dist * math.cos(theta)
    my = dist * math.sin(theta)
    mz = get_terrain_elevation(mx, my)

    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(2.0, 4.0)

    tf = unreal.Transform(
        location=unreal.Vector(mx, my, mz - 2.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    if "Moss_Patch" in hism_components:
        hism_components["Moss_Patch"].add_instance(tf)

# 6. Shrubs & Wildflowers
for i in range(120):
    dist = random.uniform(600.0, 14000.0)
    theta = random.uniform(0, 2 * math.pi)
    px = dist * math.cos(theta)
    py = dist * math.sin(theta)
    pz = get_terrain_elevation(px, py)

    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(1.8, 3.0)

    tf = unreal.Transform(
        location=unreal.Vector(px, py, pz - 4.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    rnd = random.random()
    if rnd < 0.4 and "Shrub_01" in hism_components:
        hism_components["Shrub_01"].add_instance(tf)
    elif rnd < 0.75 and "Shrub_03" in hism_components:
        hism_components["Shrub_03"].add_instance(tf)
    elif "Flowers" in hism_components:
        hism_components["Flowers"].add_instance(tf)

# Position PlayerStart safely at (0, 0, 120)
for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.PlayerStart):
        a.set_actor_location(unreal.Vector(0, 0, 120), False, False)
        a.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0), False)

# Save the level
level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] PHOTOREALISTIC GROUND & 3D GRASS UPGRADE COMPLETE!")
unreal.log_warning("==================================================")
