"""
Otherworld - Scanned Photogrammetry Nature Biome Generator
Downloads CC0 scanned 3D models (Trees, Stumps, Rocks, Shrubs, Roots) and 2K PBR textures,
imports them into Unreal Engine via Interchange, and builds a true photorealistic forest.
"""
import os
import sys
import json
import urllib.request
import ssl
import math
import random

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
DOWNLOAD_DIR = os.path.join(PROJECT_DIR, "assets", "cache", "scanned")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# SSL context
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def download_file(url, dest_path):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp, open(dest_path, 'wb') as out:
        out.write(resp.read())

def download_polyhaven_gltf(asset_id, res="1k"):
    meta_url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(meta_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        meta = json.loads(resp.read().decode())
    
    gltf_info = meta.get("gltf", {}).get(res, {}).get("gltf", {})
    if not gltf_info:
        print(f"[AGY] Error: gltf {res} not found for {asset_id}")
        return None
    
    asset_dir = os.path.join(DOWNLOAD_DIR, asset_id)
    os.makedirs(asset_dir, exist_ok=True)
    os.makedirs(os.path.join(asset_dir, "textures"), exist_ok=True)
    
    gltf_file = os.path.join(asset_dir, f"{asset_id}_{res}.gltf")
    print(f"[AGY] Downloading {asset_id} ({res})...")
    download_file(gltf_info["url"], gltf_file)
    
    for inc_name, inc_data in gltf_info.get("include", {}).items():
        inc_dest = os.path.join(asset_dir, inc_name)
        os.makedirs(os.path.dirname(inc_dest), exist_ok=True)
        download_file(inc_data["url"], inc_dest)
        
    return gltf_file

def download_polyhaven_texture(tex_id, res="2k"):
    meta_url = f"https://api.polyhaven.com/files/{tex_id}"
    req = urllib.request.Request(meta_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        meta = json.loads(resp.read().decode())

    tex_dir = os.path.join(DOWNLOAD_DIR, "textures", tex_id)
    os.makedirs(tex_dir, exist_ok=True)
    downloaded_files = {}

    for map_key in ["Diffuse", "nor_gl", "nor_dx", "Rough"]:
        if map_key in meta and res in meta[map_key]:
            fmt_dict = meta[map_key][res]
            # prefer jpg or png
            ext = "jpg" if "jpg" in fmt_dict else ("png" if "png" in fmt_dict else list(fmt_dict.keys())[0])
            url = fmt_dict[ext]["url"]
            dest = os.path.join(tex_dir, f"{tex_id}_{map_key}_{res}.{ext}")
            download_file(url, dest)
            downloaded_files[map_key] = dest

    return downloaded_files

def main():
    print("==================================================")
    print("[AGY] Step 1: Downloading Photogrammetry Scanned Nature Assets...")
    print("==================================================")

    model_ids = [
        "tree_small_02",
        "pine_sapling_small",
        "tree_stump_01",
        "tree_stump_02",
        "rock_07",
        "rock_moss_set_01",
        "shrub_01",
        "shrub_03",
        "root_cluster_01",
        "periwinkle_plant"
    ]

    gltf_paths = {}
    for mid in model_ids:
        try:
            p = download_polyhaven_gltf(mid, "1k")
            if p:
                gltf_paths[mid] = p
        except Exception as e:
            print(f"[AGY] Failed downloading {mid}: {e}")

    # Download 2K Ground Texture
    ground_tex = download_polyhaven_texture("brown_mud_leaves_01", "2k")

    # If running inside Unreal Engine
    try:
        import unreal
    except ImportError:
        print("[AGY] Download complete. Run via UnrealEditor-Cmd to build level.")
        return True

    unreal.log("==================================================")
    unreal.log("[AGY] Step 2: Importing Scanned Assets into Unreal...")
    unreal.log("==================================================")

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # 1. Import all GLTF Models
    imported_models = {}
    for mid, gpath in gltf_paths.items():
        task = unreal.AssetImportTask()
        task.filename = gpath
        task.destination_path = f"/Game/Forest/Scanned/{mid}"
        task.destination_name = f"SM_{mid}"
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])

        # Find static mesh inside destination path
        assets_in_folder = editor_asset_sub.list_assets(f"/Game/Forest/Scanned/{mid}", recursive=True)
        sm_assets = [a for a in assets_in_folder if "StaticMeshes" in a or "SM_" in a]
        if sm_assets:
            mesh_obj = editor_asset_sub.load_asset(sm_assets[0])
            if mesh_obj and isinstance(mesh_obj, unreal.StaticMesh):
                imported_models[mid] = mesh_obj
                # Set complex collision & Nanite
                body = mesh_obj.get_editor_property("body_setup")
                if body:
                    body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                nanite_s = mesh_obj.get_editor_property("nanite_settings")
                if nanite_s:
                    nanite_s.set_editor_property("enabled", True)
                    mesh_obj.set_editor_property("nanite_settings", nanite_s)
                editor_asset_sub.save_loaded_asset(mesh_obj)
                unreal.log_warning(f"[AGY] Successfully imported scanned model: {mid} -> {sm_assets[0]}")

    # 2. Import 2K Ground Textures & Build Ground Material
    ground_mat_path = "/Game/Forest/Materials/M_Forest_Ground_Scanned"
    if editor_asset_sub.does_asset_exist(ground_mat_path):
        editor_asset_sub.delete_asset(ground_mat_path)

    for tkey, tpath in ground_tex.items():
        tname = f"T_Ground_{tkey}_2k"
        task = unreal.AssetImportTask()
        task.filename = tpath
        task.destination_path = "/Game/Forest/Textures"
        task.destination_name = tname
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])

    # Build PBR Ground Material
    mat_factory = unreal.MaterialFactoryNew()
    ground_mat = asset_tools.create_asset("M_Forest_Ground_Scanned", "/Game/Forest/Materials", unreal.Material, mat_factory)
    if ground_mat:
        mel = unreal.MaterialEditingLibrary
        ground_mat.set_editor_property("used_with_nanite", True)

        diff_tex = editor_asset_sub.load_asset("/Game/Forest/Textures/T_Ground_Diffuse_2k.T_Ground_Diffuse_2k")
        nor_tex = editor_asset_sub.load_asset("/Game/Forest/Textures/T_Ground_nor_gl_2k.T_Ground_nor_gl_2k")
        rough_tex = editor_asset_sub.load_asset("/Game/Forest/Textures/T_Ground_Rough_2k.T_Ground_Rough_2k")

        if diff_tex:
            diff_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -400, -100)
            diff_node.set_editor_property("texture", diff_tex)
            mel.connect_material_property(diff_node, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)

        if nor_tex:
            nor_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -400, 100)
            nor_node.set_editor_property("texture", nor_tex)
            nor_node.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            mel.connect_material_property(nor_node, "RGB", unreal.MaterialProperty.MP_NORMAL)

        if rough_tex:
            rough_node = mel.create_material_expression(ground_mat, unreal.MaterialExpressionTextureSample, -400, 300)
            rough_node.set_editor_property("texture", rough_tex)
            mel.connect_material_property(rough_node, "R", unreal.MaterialProperty.MP_ROUGHNESS)

        mel.recompile_material(ground_mat)
        editor_asset_sub.save_asset(ground_mat_path)
        unreal.log_warning(f"[AGY] Created & Compiled Scanned 2K Ground Material: {ground_mat_path}")

    # Apply Scanned Ground Material to Terrain Mesh
    terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
    if terrain_mesh and ground_mat:
        terrain_mesh.set_material(0, ground_mat)
        editor_asset_sub.save_loaded_asset(terrain_mesh)

    # -------------------------------------------------------------
    # Step 3: Populate Lvl_Forest with Scanned Assets
    # -------------------------------------------------------------
    unreal.log("==================================================")
    unreal.log("[AGY] Step 3: Populating Level with Photogrammetry Scanned Nature...")
    unreal.log("==================================================")

    level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

    # Clean old procedural trees/props
    for a in editor_actor_sub.get_all_level_actors():
        lbl = a.get_actor_label()
        if any(w in lbl for w in ["Tree", "Rock", "Bush", "Log", "Fern", "RealisticTree", "GraniteBoulder", "FallenLog"]):
            editor_actor_sub.destroy_actor(a)

    def get_terrain_elevation(x, y):
        dist = math.sqrt(x * x + y * y)
        if dist < 4500.0:
            return 0.0
        else:
            elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
            edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
            return elevation + (edge_factor ** 2) * 1750.0

    random.seed(2026)

    # 1. Populate Scanned Trees (tree_small_02 & pine_sapling_small)
    tree_mesh_keys = [k for k in ["tree_small_02", "pine_sapling_small"] if k in imported_models]
    if not tree_mesh_keys:
        tree_mesh_keys = list(imported_models.keys())

    unreal.log_warning(f"[AGY] Spawning 150 Scanned Trees...")
    for i in range(150):
        dist = random.uniform(850.0, 15500.0)
        theta = random.uniform(0, 2 * math.pi)
        tx = dist * math.cos(theta)
        ty = dist * math.sin(theta)
        tz = get_terrain_elevation(tx, ty)

        m_key = random.choice(tree_mesh_keys)
        m_obj = imported_models[m_key]

        # Natural tree scale variation (scaled up for realistic forest height)
        base_scale = 3.5 if m_key == "tree_small_02" else 4.2
        scale_var = random.uniform(0.85, 1.4) * base_scale
        rot_yaw = random.uniform(0, 360)

        tree = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(tx, ty, tz - 12.0),
            unreal.Rotator(0.0, rot_yaw, 0.0) # 100% Vertical
        )
        tree.set_actor_label(f"Forest_ScannedTree_{i+1:03d}")
        tree.set_actor_scale3d(unreal.Vector(scale_var, scale_var, scale_var))
        t_sm = tree.get_component_by_class(unreal.StaticMeshComponent)
        if t_sm:
            t_sm.set_mobility(unreal.ComponentMobility.STATIC)
            t_sm.set_static_mesh(m_obj)
            t_sm.set_collision_profile_name("BlockAll")
            t_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 2. Populate Scanned Stumps & Roots
    stump_keys = [k for k in ["tree_stump_01", "tree_stump_02", "root_cluster_01"] if k in imported_models]
    if stump_keys:
        unreal.log_warning("[AGY] Spawning 40 Scanned Stumps & Roots...")
        for i in range(40):
            dist = random.uniform(900.0, 14000.0)
            theta = random.uniform(0, 2 * math.pi)
            sx = dist * math.cos(theta)
            sy = dist * math.sin(theta)
            sz = get_terrain_elevation(sx, sy)

            m_key = random.choice(stump_keys)
            m_obj = imported_models[m_key]
            scale_v = random.uniform(1.8, 3.2)

            stump = editor_actor_sub.spawn_actor_from_class(
                unreal.StaticMeshActor,
                unreal.Vector(sx, sy, sz - 8.0),
                unreal.Rotator(0.0, random.uniform(0, 360), 0.0)
            )
            stump.set_actor_label(f"Forest_ScannedStump_{i+1:02d}")
            stump.set_actor_scale3d(unreal.Vector(scale_v, scale_v, scale_v))
            s_sm = stump.get_component_by_class(unreal.StaticMeshComponent)
            if s_sm:
                s_sm.set_mobility(unreal.ComponentMobility.STATIC)
                s_sm.set_static_mesh(m_obj)
                s_sm.set_collision_profile_name("BlockAll")

    # 3. Populate Scanned Boulders & Mossy Rocks
    rock_keys = [k for k in ["rock_07", "rock_moss_set_01"] if k in imported_models]
    if rock_keys:
        unreal.log_warning("[AGY] Spawning 60 Scanned Rocks & Boulders...")
        for i in range(60):
            dist = random.uniform(800.0, 14500.0)
            theta = random.uniform(0, 2 * math.pi)
            rx = dist * math.cos(theta)
            ry = dist * math.sin(theta)
            rz = get_terrain_elevation(rx, ry)

            m_key = random.choice(rock_keys)
            m_obj = imported_models[m_key]
            scale_v = random.uniform(2.0, 4.5)

            rock = editor_actor_sub.spawn_actor_from_class(
                unreal.StaticMeshActor,
                unreal.Vector(rx, ry, rz - 15.0),
                unreal.Rotator(random.uniform(-5.0, 5.0), random.uniform(0, 360), random.uniform(-5.0, 5.0))
            )
            rock.set_actor_label(f"Forest_ScannedRock_{i+1:02d}")
            rock.set_actor_scale3d(unreal.Vector(scale_v, scale_v, scale_v))
            r_sm = rock.get_component_by_class(unreal.StaticMeshComponent)
            if r_sm:
                r_sm.set_mobility(unreal.ComponentMobility.STATIC)
                r_sm.set_static_mesh(m_obj)
                r_sm.set_collision_profile_name("BlockAll")
                r_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 4. Populate Scanned Shrubs & Ground Plants
    plant_keys = [k for k in ["shrub_01", "shrub_03", "periwinkle_plant"] if k in imported_models]
    if plant_keys:
        unreal.log_warning("[AGY] Spawning 90 Scanned Ground Cover & Shrubs...")
        for i in range(90):
            dist = random.uniform(600.0, 13500.0)
            theta = random.uniform(0, 2 * math.pi)
            px = dist * math.cos(theta)
            py = dist * math.sin(theta)
            pz = get_terrain_elevation(px, py)

            m_key = random.choice(plant_keys)
            m_obj = imported_models[m_key]
            scale_v = random.uniform(1.5, 3.0)

            plant = editor_actor_sub.spawn_actor_from_class(
                unreal.StaticMeshActor,
                unreal.Vector(px, py, pz),
                unreal.Rotator(0.0, random.uniform(0, 360), 0.0)
            )
            plant.set_actor_label(f"Forest_ScannedPlant_{i+1:02d}")
            plant.set_actor_scale3d(unreal.Vector(scale_v, scale_v, scale_v))
            p_sm = plant.get_component_by_class(unreal.StaticMeshComponent)
            if p_sm:
                p_sm.set_mobility(unreal.ComponentMobility.STATIC)
                p_sm.set_static_mesh(m_obj)
                p_sm.set_collision_profile_name("BlockAll")

    level_editor_sub.save_current_level()
    unreal.log_warning("==================================================")
    unreal.log_warning("[AGY] COMPLETE PHOTOGRAMMETRY SCANNED FOREST BUILT & SAVED!")
    unreal.log_warning("==================================================")
    return True

if __name__ == "__main__":
    main()
