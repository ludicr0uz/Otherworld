"""
Otherworld - Complete Two-Sided Foliage & Bark Shading Application
Generates all Master Material Instances and binds them directly to HISM components in Lvl_Forest.
"""
import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
mel = unreal.MaterialEditingLibrary

# 1. Load Master Materials
master_foliage = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Foliage")
master_bark = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Bark")

if not master_foliage or not master_bark:
    raise RuntimeError("Master materials M_Master_Foliage and M_Master_Bark must exist!")

# 2. Build Material Instances
mic_factory = unreal.MaterialInstanceConstantFactoryNew()
pkg_mat_dir = "/Game/Forest/Materials/Instances"

def create_or_update_mic(name, parent, diff_path, norm_path, rough_path):
    mi_path = f"{pkg_mat_dir}/{name}"
    mic = editor_asset_sub.load_asset(mi_path)
    if not mic:
        mic = asset_tools.create_asset(name, pkg_mat_dir, unreal.MaterialInstanceConstant, mic_factory)
    
    if not mic:
        unreal.log_error(f"Failed to create MIC: {name}")
        return None
        
    mic.set_editor_property("parent", parent)
    
    diff_t = editor_asset_sub.load_asset(diff_path) if diff_path else None
    norm_t = editor_asset_sub.load_asset(norm_path) if norm_path else None
    rough_t = editor_asset_sub.load_asset(rough_path) if rough_path else None
    
    if diff_t:
        mel.set_material_instance_texture_parameter_value(mic, "BaseColorTexture", diff_t)
    if norm_t:
        mel.set_material_instance_texture_parameter_value(mic, "NormalTexture", norm_t)
    if rough_t:
        mel.set_material_instance_texture_parameter_value(mic, "RoughnessTexture", rough_t)
        
    mel.update_material_instance(mic)
    editor_asset_sub.save_loaded_asset(mic)
    unreal.log_warning(f"[AGY] Created/Updated MIC: {name} (Diff: {diff_t.get_name() if diff_t else 'None'})")
    return mic

# Broadleaf Island Tree 01
mi_it01_trunk = create_or_update_mic(
    "MI_IslandTree01_Trunk", master_bark,
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_diff",
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_nor_gl",
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_rough"
)
mi_it01_leaves = create_or_update_mic(
    "MI_IslandTree01_Leaves", master_foliage,
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_diff-island_tree_01_leaves_alpha",
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_nor_gl",
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_rough"
)
mi_it01_branches = create_or_update_mic(
    "MI_IslandTree01_Branches", master_bark,
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_branches_diff",
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_branches_nor_gl",
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_branches_rough"
)

# Broadleaf Island Tree 02
mi_it02_trunk = create_or_update_mic(
    "MI_IslandTree02_Trunk", master_bark,
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_diff",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_nor_gl",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_rough"
)
mi_it02_leaves = create_or_update_mic(
    "MI_IslandTree02_Leaves", master_foliage,
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_leaves_diff-island_tree_02_leaves_alpha",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_leaves_nor_gl",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_leaves_rough"
)
mi_it02_branches = create_or_update_mic(
    "MI_IslandTree02_Branches", master_bark,
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_branches_diff",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_branches_nor_gl",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/Textures/island_tree_02_branches_rough"
)

# Deciduous Tree Small 02
mi_ts02_branches = create_or_update_mic(
    "MI_TreeSmall02_Branches", master_bark,
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_branch_diff",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_branch_nor_gl",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_branch_rough"
)
mi_ts02_leaves = create_or_update_mic(
    "MI_TreeSmall02_Leaves", master_foliage,
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_leaves_diff-tree_small_02_leaves_alpha",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_leaves_nor_gl",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_leaves_rough"
)
mi_ts02_trunk = create_or_update_mic(
    "MI_TreeSmall02_Trunk", master_bark,
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_diff",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_nor_gl",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/Textures/tree_small_02_rough"
)

# Evergreen Fir Tree 01
mi_fir_bark = create_or_update_mic(
    "MI_FirTree01_Bark", master_bark,
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_bark_diff",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_bark_nor_gl",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_bark_rough"
)
mi_fir_trunk_a = create_or_update_mic(
    "MI_FirTree01_TrunkA", master_bark,
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_trunk_a_diff",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_trunk_a_nor_gl",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_trunk_a_rough"
)
mi_fir_trunk_b = create_or_update_mic(
    "MI_FirTree01_TrunkB", master_bark,
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_trunk_b_diff",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_trunk_b_nor_gl",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_trunk_b_rough"
)
mi_fir_twig = create_or_update_mic(
    "MI_FirTree01_Twig", master_foliage,
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_twig_diff-fir_tree_01_twig_alpha",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_twig_nor_gl",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/Textures/fir_tree_01_twig_rough"
)

# Pine saplings
mi_pine_bark = create_or_update_mic(
    "MI_PineSapling_Bark", master_bark,
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_bark_diff",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_bark_nor_gl",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_bark_rough"
)
mi_pine_twig = create_or_update_mic(
    "MI_PineSapling_Twig", master_foliage,
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_twig_diff",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_twig_nor_gl",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/Textures/pine_sapling_small_twig_rough"
)

# Grasses & Undergrowth
mi_grass01 = create_or_update_mic(
    "MI_GrassMedium01", master_foliage,
    "/Game/Forest/Scanned/grass_medium_01/grass_medium_01_1k/Textures/grass_medium_01_diff-grass_medium_01_alpha",
    "/Game/Forest/Scanned/grass_medium_01/grass_medium_01_1k/Textures/grass_medium_01_nor_gl",
    "/Game/Forest/Scanned/grass_medium_01/grass_medium_01_1k/Textures/grass_medium_01_rough"
)
mi_grass02 = create_or_update_mic(
    "MI_GrassMedium02", master_foliage,
    "/Game/Forest/Scanned/grass_medium_02/grass_medium_02_1k/Textures/grass_medium_02_diff-grass_medium_02_alpha",
    "/Game/Forest/Scanned/grass_medium_02/grass_medium_02_1k/Textures/grass_medium_02_nor_gl",
    "/Game/Forest/Scanned/grass_medium_02/grass_medium_02_1k/Textures/grass_medium_02_rough"
)
mi_fern02 = create_or_update_mic(
    "MI_Fern02", master_foliage,
    "/Game/Forest/Scanned/fern_02/fern_02_1k/Textures/fern_02_diff-fern_02_alpha",
    "/Game/Forest/Scanned/fern_02/fern_02_1k/Textures/fern_02_nor_gl",
    "/Game/Forest/Scanned/fern_02/fern_02_1k/Textures/fern_02_rough"
)
mi_moss01 = create_or_update_mic(
    "MI_Moss01", master_foliage,
    "/Game/Forest/Scanned/moss_01/moss_01_1k/Textures/moss_01_diff-moss_01_alpha",
    "/Game/Forest/Scanned/moss_01/moss_01_1k/Textures/moss_01_nor_gl",
    "/Game/Forest/Scanned/moss_01/moss_01_1k/Textures/moss_01_rough"
)
mi_periwinkle = create_or_update_mic(
    "MI_Periwinkle", master_foliage,
    "/Game/Forest/Scanned/periwinkle_plant/periwinkle_plant_1k/Textures/periwinkle_plant_diff-periwinkle_plant_opacity",
    "/Game/Forest/Scanned/periwinkle_plant/periwinkle_plant_1k/Textures/periwinkle_plant_nor_gl",
    "/Game/Forest/Scanned/periwinkle_plant/periwinkle_plant_1k/Textures/periwinkle_plant_rough"
)
mi_shrub01 = create_or_update_mic(
    "MI_Shrub01", master_foliage,
    "/Game/Forest/Scanned/shrub_01/shrub_01_1k/Textures/shrub_01_diff",
    "/Game/Forest/Scanned/shrub_01/shrub_01_1k/Textures/shrub_01_nor_gl",
    "/Game/Forest/Scanned/shrub_01/shrub_01_1k/Textures/shrub_01_rough"
)
mi_shrub03 = create_or_update_mic(
    "MI_Shrub03", master_foliage,
    "/Game/Forest/Scanned/shrub_03/shrub_03_1k/Textures/shrub_03_diff",
    "/Game/Forest/Scanned/shrub_03/shrub_03_1k/Textures/shrub_03_nor_gl",
    "/Game/Forest/Scanned/shrub_03/shrub_03_1k/Textures/shrub_03_rough"
)
mi_rock07 = create_or_update_mic(
    "MI_Rock07", master_bark,
    "/Game/Forest/Scanned/rock_07/rock_07_1k/Textures/rock_07_diff",
    "/Game/Forest/Scanned/rock_07/rock_07_1k/Textures/rock_07_nor_gl",
    "/Game/Forest/Scanned/rock_07/rock_07_1k/Textures/rock_07_rough"
)
mi_rock_moss = create_or_update_mic(
    "MI_RockMossSet", master_bark,
    "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/Textures/rock_moss_set_01_diff",
    "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/Textures/rock_moss_set_01_nor_gl",
    "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/Textures/rock_moss_set_01_rough"
)
mi_stump01 = create_or_update_mic(
    "MI_TreeStump01", master_bark,
    "/Game/Forest/Scanned/tree_stump_01/tree_stump_01_1k/Textures/tree_stump_01_diff",
    "/Game/Forest/Scanned/tree_stump_01/tree_stump_01_1k/Textures/tree_stump_01_nor_gl",
    "/Game/Forest/Scanned/tree_stump_01/tree_stump_01_1k/Textures/tree_stump_01_rough"
)
mi_stump02 = create_or_update_mic(
    "MI_TreeStump02", master_bark,
    "/Game/Forest/Scanned/tree_stump_02/tree_stump_02_1k/Textures/tree_stump_02_diff",
    "/Game/Forest/Scanned/tree_stump_02/tree_stump_02_1k/Textures/tree_stump_02_nor_gl",
    "/Game/Forest/Scanned/tree_stump_02/tree_stump_02_1k/Textures/tree_stump_02_rough"
)
mi_root_cluster = create_or_update_mic(
    "MI_RootCluster01", master_bark,
    "/Game/Forest/Scanned/root_cluster_01/root_cluster_01_1k/Textures/root_cluster_01_diff",
    "/Game/Forest/Scanned/root_cluster_01/root_cluster_01_1k/Textures/root_cluster_01_nor_gl",
    "/Game/Forest/Scanned/root_cluster_01/root_cluster_01_1k/Textures/root_cluster_01_rough"
)

# 3. Open Level and apply to HISM actors
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
actors = editor_actor_sub.get_all_level_actors()

hism_material_mapping = {
    # Broadleaf Trees
    "HISM_Tree_Leafy_Island_01": [mi_it01_trunk, mi_it01_leaves, mi_it01_branches],
    "HISM_Tree_Leafy_Island_02": [mi_it02_trunk, mi_it02_leaves, mi_it02_branches],
    "HISM_Tree_Deciduous": [mi_ts02_branches, mi_ts02_leaves, mi_ts02_trunk],
    # Firs
    "HISM_Tree_Fir_A": [mi_fir_bark, mi_fir_trunk_a, mi_fir_twig, mi_fir_bark],
    "HISM_Tree_Fir_B": [mi_fir_bark, mi_fir_trunk_b, mi_fir_twig, mi_fir_bark],
    "HISM_Tree_Fir_C": [mi_fir_bark, mi_fir_twig, mi_fir_bark, mi_fir_trunk_b],
    # Pines
    "HISM_Tree_Pine_A": [mi_pine_bark, mi_pine_twig],
    "HISM_Tree_Pine_B": [mi_pine_bark, mi_pine_twig],
    "HISM_Tree_Pine_C": [mi_pine_bark, mi_pine_twig],
    # Grass & Foliage
    "HISM_MeadowGrass": [mi_grass01],
    "HISM_TallGrass": [mi_grass02],
    "HISM_WoodlandFerns": [mi_fern02],
    "HISM_MossPatch": [mi_moss01],
    "HISM_Periwinkle": [mi_periwinkle],
    "HISM_Shrub01": [mi_shrub01],
    "HISM_Shrub03": [mi_shrub03],
    # Rocks & Stumps
    "HISM_GraniteBoulders": [mi_rock07],
    "HISM_MossyBoulders": [mi_rock_moss],
    "HISM_AncientStump": [mi_stump01],
    "HISM_MossyStump": [mi_stump02],
    "HISM_RootCluster": [mi_root_cluster],
}

count_updated = 0
for actor in actors:
    lbl = actor.get_actor_label()
    if lbl in hism_material_mapping:
        mats = hism_material_mapping[lbl]
        root = actor.get_editor_property("root_component")
        if isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
            for s_idx, mat in enumerate(mats):
                if mat:
                    root.set_material(s_idx, mat)
            unreal.log_warning(f"[AGY] Bound {len(mats)} material slots to HISM actor: {lbl}")
            count_updated += 1

level_editor_sub.save_current_level()
unreal.log_warning(f"[AGY] ALL {count_updated} HISM ACTORS SUCCESSFULLY BOUND WITH TWO-SIDED FOLIAGE MATERIALS AND LEVEL SAVED!")
