"""
Otherworld - High-Performance GPU-Instanced Photorealistic Forest Biome
Constructs HISM actors with 100% vertical tree alignment and optimized draw calls for macOS Metal.
"""
import math
import random
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

unreal.log("==================================================")
unreal.log("[AGY] Cleaning old actors...")
unreal.log("==================================================")
for a in editor_actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    if any(w in lbl for w in ["Tree", "Rock", "Bush", "Log", "Fern", "Stump", "Plant", "Scanned", "HISM"]):
        editor_actor_sub.destroy_actor(a)

def get_terrain_elevation(x, y):
    dist = math.sqrt(x * x + y * y)
    if dist < 4500.0:
        return 0.0
    else:
        elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
        edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
        return elevation + (edge_factor ** 2) * 1750.0

# Asset dictionary with mesh paths and configuration
assets_config = {
    "Tree_Pine": {
        "path": "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a",
        "collision": True,
        "shadows": True,
    },
    "Tree_Deciduous": {
        "path": "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
        "collision": True,
        "shadows": True,
    },
    "Stump_01": {
        "path": "/Game/Forest/Scanned/tree_stump_01/tree_stump_01_1k/StaticMeshes/SM_tree_stump_01.SM_tree_stump_01",
        "collision": True,
        "shadows": True,
    },
    "Stump_02": {
        "path": "/Game/Forest/Scanned/tree_stump_02/tree_stump_02_1k/StaticMeshes/SM_tree_stump_02.SM_tree_stump_02",
        "collision": True,
        "shadows": True,
    },
    "Root_Cluster": {
        "path": "/Game/Forest/Scanned/root_cluster_01/root_cluster_01_1k/StaticMeshes/SM_root_cluster_01.SM_root_cluster_01",
        "collision": True,
        "shadows": True,
    },
    "Rock_Granite": {
        "path": "/Game/Forest/Scanned/rock_07/rock_07_1k/StaticMeshes/SM_rock_07.SM_rock_07",
        "collision": True,
        "shadows": True,
    },
    "Rock_Moss": {
        "path": "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/StaticMeshes/rock_moss_set_01_rock01.rock_moss_set_01_rock01",
        "collision": True,
        "shadows": True,
    },
    "Shrub_01": {
        "path": "/Game/Forest/Scanned/shrub_01/shrub_01_1k/StaticMeshes/SM_shrub_01.SM_shrub_01",
        "collision": False,
        "shadows": True,
    },
    "Shrub_03": {
        "path": "/Game/Forest/Scanned/shrub_03/shrub_03_1k/StaticMeshes/shrub_03_a.shrub_03_a",
        "collision": False,
        "shadows": True,
    },
    "Flowers": {
        "path": "/Game/Forest/Scanned/periwinkle_plant/periwinkle_plant_1k/StaticMeshes/periwinkle_plant_01_LOD0.periwinkle_plant_01_LOD0",
        "collision": False,
        "shadows": False,
    }
}

hism_components = {}

for name, cfg in assets_config.items():
    mesh = editor_asset_sub.load_asset(cfg["path"])
    if not mesh:
        unreal.log_error(f"Could not load mesh: {cfg['path']}")
        continue

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

# 1. Spawn Photorealistic Scanned Trees (Strict 100% Vertical Rotations)
unreal.log_warning("[AGY] Placing Scanned Trees with 100% Vertical Alignment (Pitch=0, Roll=0)...")
for i in range(160):
    dist = random.uniform(850.0, 16500.0)
    theta = random.uniform(0, 2 * math.pi)
    tx = dist * math.cos(theta)
    ty = dist * math.sin(theta)
    tz = get_terrain_elevation(tx, ty)

    yaw = random.uniform(0.0, 360.0)
    # Strictly Vertical Rotator
    rot = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)

    is_pine = random.random() < 0.65
    if is_pine and "Tree_Pine" in hism_components:
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

# 2. Spawn Boulders & Rocks
unreal.log_warning("[AGY] Placing Scanned Rocks & Boulders...")
for i in range(80):
    dist = random.uniform(800.0, 15500.0)
    theta = random.uniform(0, 2 * math.pi)
    rx = dist * math.cos(theta)
    ry = dist * math.sin(theta)
    rz = get_terrain_elevation(rx, ry)

    yaw = random.uniform(0.0, 360.0)
    # Rocks can have slight natural tilt
    rot = unreal.Rotator(pitch=random.uniform(-5.0, 5.0), yaw=yaw, roll=random.uniform(-5.0, 5.0))
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

# 3. Spawn Woodland Tree Stumps & Roots
unreal.log_warning("[AGY] Placing Scanned Tree Stumps & Roots...")
for i in range(60):
    dist = random.uniform(900.0, 15000.0)
    theta = random.uniform(0, 2 * math.pi)
    sx = dist * math.cos(theta)
    sy = dist * math.sin(theta)
    sz = get_terrain_elevation(sx, sy)

    yaw = random.uniform(0.0, 360.0)
    rot = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
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

# 4. Spawn Shrubs, Bushes & Flowers
unreal.log_warning("[AGY] Placing Scanned Shrubs & Flowering Plants...")
for i in range(140):
    dist = random.uniform(600.0, 14500.0)
    theta = random.uniform(0, 2 * math.pi)
    px = dist * math.cos(theta)
    py = dist * math.sin(theta)
    pz = get_terrain_elevation(px, py)

    yaw = random.uniform(0.0, 360.0)
    rot = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    scale_val = random.uniform(1.8, 3.2)

    tf = unreal.Transform(
        location=unreal.Vector(px, py, pz - 4.0),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    rnd = random.random()
    if rnd < 0.35 and "Shrub_01" in hism_components:
        hism_components["Shrub_01"].add_instance(tf)
    elif rnd < 0.70 and "Shrub_03" in hism_components:
        hism_components["Shrub_03"].add_instance(tf)
    elif "Flowers" in hism_components:
        hism_components["Flowers"].add_instance(tf)

# Position PlayerStart safely
for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.PlayerStart):
        a.set_actor_location(unreal.Vector(0, 0, 120), False, False)
        a.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0), False)

# Save level
level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] FOREST GENERATION COMPLETE AND LEVEL SAVED!")
unreal.log_warning("==================================================")
