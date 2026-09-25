import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

asset_paths = [
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a",
    "/Game/Forest/Scanned/tree_stump_01/tree_stump_01_1k/StaticMeshes/SM_tree_stump_01.SM_tree_stump_01",
    "/Game/Forest/Scanned/tree_stump_02/tree_stump_02_1k/StaticMeshes/SM_tree_stump_02.SM_tree_stump_02",
    "/Game/Forest/Scanned/root_cluster_01/root_cluster_01_1k/StaticMeshes/SM_root_cluster_01.SM_root_cluster_01",
    "/Game/Forest/Scanned/rock_07/rock_07_1k/StaticMeshes/SM_rock_07.SM_rock_07",
    "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/StaticMeshes/rock_moss_set_01_rock01.rock_moss_set_01_rock01",
    "/Game/Forest/Scanned/shrub_01/shrub_01_1k/StaticMeshes/SM_shrub_01.SM_shrub_01",
    "/Game/Forest/Scanned/shrub_03/shrub_03_1k/StaticMeshes/shrub_03_a.shrub_03_a",
    "/Game/Forest/Scanned/periwinkle_plant/periwinkle_plant_1k/StaticMeshes/periwinkle_plant_01_LOD0.periwinkle_plant_01_LOD0"
]

for p in asset_paths:
    asset = editor_asset_sub.load_asset(p)
    if asset:
        # Check collision settings on mesh
        body_setup = asset.get_editor_property("body_setup")
        collision_trace_flag = body_setup.get_editor_property("collision_trace_flag") if body_setup else "None"
        unreal.log_warning(f"Loaded {asset.get_name()}: collision_trace={collision_trace_flag}")
        # Ensure complex collision as simple if needed or generate box/capsule
        if body_setup:
            # Set to CTF_UseComplexAsSimple so photogrammetry mesh collisions are accurate
            body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            editor_asset_sub.save_loaded_asset(asset)
    else:
        unreal.log_error(f"Failed to load {p}")
