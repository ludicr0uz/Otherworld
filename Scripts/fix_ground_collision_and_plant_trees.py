import math
import random
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] 1. Fixing Terrain Collision (Disable Nanite, Enable Complex Collision)...")
unreal.log_warning("==================================================")

terrain_mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
if terrain_mesh:
    # Disable Nanite on terrain so PhysX uses exact visual geometry with 0 error
    nanite = terrain_mesh.get_editor_property("nanite_settings")
    if nanite:
        nanite.set_editor_property("enabled", False)
        terrain_mesh.set_editor_property("nanite_settings", nanite)
    
    body_setup = terrain_mesh.get_editor_property("body_setup")
    if body_setup:
        body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    
    editor_asset_sub.save_loaded_asset(terrain_mesh)
    unreal.log_warning("[AGY] SM_ForestLandscape collision set to 100% exact complex mesh triangles!")

# 2. Re-compute Exact Terrain Facet Elevation Function
GRID_SIZE = 64
WORLD_SIZE = 40000.0 # 400m x 400m
STEP = WORLD_SIZE / GRID_SIZE # 625.0 cm per quad

def elev_formula(x, y):
    dist = math.sqrt(x * x + y * y)
    if dist < 4500.0:
        return 0.0
    else:
        elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
        edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
        return elevation + (edge_factor ** 2) * 1750.0

# Pre-calculate top grid vertices exactly as generated in SM_ForestLandscape.obj
grid_z = [[0.0 for _ in range(GRID_SIZE + 1)] for _ in range(GRID_SIZE + 1)]
for gi in range(GRID_SIZE + 1):
    gx = -WORLD_SIZE / 2.0 + gi * STEP
    for gj in range(GRID_SIZE + 1):
        gy = -WORLD_SIZE / 2.0 + gj * STEP
        grid_z[gi][gj] = elev_formula(gx, gy)

def get_exact_mesh_z(x, y):
    """Calculates the EXACT height of the triangular facet on SM_ForestLandscape at (x, y)"""
    half = WORLD_SIZE / 2.0
    cx = max(-half, min(half, x))
    cy = max(-half, min(half, y))
    
    u = (cx + half) / STEP
    v = (cy + half) / STEP
    
    gi = int(math.floor(u))
    gj = int(math.floor(v))
    
    gi = max(0, min(GRID_SIZE - 1, gi))
    gj = max(0, min(GRID_SIZE - 1, gj))
    
    fu = u - gi
    fv = v - gj
    
    z00 = grid_z[gi][gj]
    z01 = grid_z[gi][gj + 1]
    z11 = grid_z[gi + 1][gj + 1]
    z10 = grid_z[gi + 1][gj]
    
    if fu <= fv:
        z = z00 + fu * (z11 - z01) + fv * (z01 - z00)
    else:
        z = z00 + fu * (z10 - z00) + fv * (z11 - z10)
    
    return z

unreal.log_warning("==================================================")
unreal.log_warning("[AGY] 2. Re-planting Trees & Undergrowth firmly embedded in Terrain...")
unreal.log_warning("==================================================")

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

# Load centered tree meshes
m_island_01 = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01")
m_island_02 = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02")
m_fir_01a = editor_asset_sub.load_asset("/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0")
m_pine_a = editor_asset_sub.load_asset("/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a")
m_deciduous = editor_asset_sub.load_asset("/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02")

# Clean old tree HISM actors
for a in editor_actor_sub.get_all_level_actors():
    lbl = a.get_actor_label()
    if any(w in lbl for w in ["HISM_Tree", "HISM_Fir", "HISM_Island", "Forest_HISM_Trees"]):
        editor_actor_sub.destroy_actor(a)

def create_tree_hism(name, mesh, mats):
    actor = editor_actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    actor.set_actor_label(name)
    comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
    comp.set_static_mesh(mesh)
    actor.set_editor_property("root_component", comp)
    comp.set_collision_profile_name("BlockAll")
    comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    comp.set_editor_property("cast_shadow", True)
    for idx, mat_path in enumerate(mats):
        mat_obj = editor_asset_sub.load_asset(mat_path)
        if mat_obj:
            comp.set_material(idx, mat_obj)
    return comp

# Materials for trees
hism_island_01 = create_tree_hism("HISM_Tree_Leafy_Island_01", m_island_01, [
    "/Game/Forest/Materials/Instances/MI_IslandTree01_Trunk",
    "/Game/Forest/Materials/Instances/MI_IslandTree01_Leaves",
    "/Game/Forest/Materials/Instances/MI_IslandTree01_Branches"
])

hism_island_02 = create_tree_hism("HISM_Tree_Leafy_Island_02", m_island_02, [
    "/Game/Forest/Materials/Instances/MI_IslandTree02_Trunk",
    "/Game/Forest/Materials/Instances/MI_IslandTree02_Leaves",
    "/Game/Forest/Materials/Instances/MI_IslandTree02_Branches"
])

hism_fir = create_tree_hism("HISM_Tree_Fir_A", m_fir_01a, [
    "/Game/Forest/Materials/Instances/MI_FirTree01_Bark",
    "/Game/Forest/Materials/Instances/MI_FirTree01_TrunkA",
    "/Game/Forest/Materials/Instances/MI_FirTree01_Twig",
    "/Game/Forest/Materials/Instances/MI_FirTree01_Bark"
])

hism_pine = create_tree_hism("HISM_Tree_Pine_A", m_pine_a, [
    "/Game/Forest/Materials/Instances/MI_PineSapling_Bark",
    "/Game/Forest/Materials/Instances/MI_PineSapling_Twig"
])

hism_deciduous = create_tree_hism("HISM_Tree_Deciduous", m_deciduous, [
    "/Game/Forest/Materials/Instances/MI_TreeSmall02_Branches",
    "/Game/Forest/Materials/Instances/MI_TreeSmall02_Leaves",
    "/Game/Forest/Materials/Instances/MI_TreeSmall02_Trunk"
])

random.seed(42)

# 1. Spawn Lush Broadleaf Trees with Full Canopies (140 instances)
unreal.log_warning("[AGY] Planting 140 Broadleaf Trees with roots embedded in terrain...")
for i in range(140):
    dist = random.uniform(700.0, 16000.0)
    theta = random.uniform(0, 2 * math.pi)
    tx = dist * math.cos(theta)
    ty = dist * math.sin(theta)
    tz = get_exact_mesh_z(tx, ty)
    
    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(2.0, 3.6)
    
    # Sink root flare securely 40cm below facet surface
    sink = 40.0 * (scale_val / 2.5)
    tf = unreal.Transform(
        location=unreal.Vector(tx, ty, tz - sink),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    if random.random() < 0.5:
        hism_island_01.add_instance(tf)
    else:
        hism_island_02.add_instance(tf)

# 2. Spawn Dense Evergreen Fir Trees (180 instances)
unreal.log_warning("[AGY] Planting 180 Dense Fir Trees...")
for i in range(180):
    dist = random.uniform(650.0, 16500.0)
    theta = random.uniform(0, 2 * math.pi)
    tx = dist * math.cos(theta)
    ty = dist * math.sin(theta)
    tz = get_exact_mesh_z(tx, ty)
    
    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    scale_val = random.uniform(1.8, 3.8)
    
    sink = 45.0 * (scale_val / 2.5)
    tf = unreal.Transform(
        location=unreal.Vector(tx, ty, tz - sink),
        rotation=rot,
        scale=unreal.Vector(scale_val, scale_val, scale_val)
    )
    hism_fir.add_instance(tf)

# 3. Spawn Pine Saplings & Woodland Deciduous (140 instances)
unreal.log_warning("[AGY] Planting 140 Pines & Deciduous Trees...")
for i in range(140):
    dist = random.uniform(800.0, 16500.0)
    theta = random.uniform(0, 2 * math.pi)
    tx = dist * math.cos(theta)
    ty = dist * math.sin(theta)
    tz = get_exact_mesh_z(tx, ty)
    
    rot = unreal.Rotator(pitch=0.0, yaw=random.uniform(0.0, 360.0), roll=0.0)
    
    if random.random() < 0.6:
        scale_val = random.uniform(3.0, 5.5)
        sink = 35.0 * (scale_val / 4.0)
        tf = unreal.Transform(
            location=unreal.Vector(tx, ty, tz - sink),
            rotation=rot,
            scale=unreal.Vector(scale_val, scale_val, scale_val)
        )
        hism_pine.add_instance(tf)
    else:
        scale_val = random.uniform(2.5, 4.2)
        sink = 40.0 * (scale_val / 3.0)
        tf = unreal.Transform(
            location=unreal.Vector(tx, ty, tz - sink),
            rotation=rot,
            scale=unreal.Vector(scale_val, scale_val, scale_val)
        )
        hism_deciduous.add_instance(tf)

# Also update Terrain Actor in Level to ensure collision profile is active
for a in editor_actor_sub.get_all_level_actors():
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            smc.set_static_mesh(terrain_mesh)
            smc.set_collision_profile_name("BlockAll")
            smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            unreal.log_warning("[AGY] Forest_Terrain_Landscape collision set to BlockAll & QueryAndPhysics!")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] ALL 460 TREES FIRMLY PLANTED & TERRAIN COLLISION FIXED!")
unreal.log_warning("==================================================")
