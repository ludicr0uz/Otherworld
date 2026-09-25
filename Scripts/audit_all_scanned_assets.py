import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

all_assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)

models = [
    "island_tree_01", "island_tree_02", "tree_small_02", "fir_tree_01",
    "pine_sapling_small", "pine_sapling_medium", "pine_tree_01",
    "grass_medium_01", "grass_medium_02", "fern_02", "moss_01",
    "periwinkle_plant", "shrub_01", "shrub_03", "rock_07", "rock_moss_set_01",
    "tree_stump_01", "tree_stump_02", "root_cluster_01"
]

for m in models:
    unreal.log_warning(f"\n==================== MODEL: {m} ====================")
    mesh_assets = [a for a in all_assets if f"/{m}/" in a and ("StaticMesh" in a or "SM_" in a or "_LOD" in a or "_a" in a)]
    tex_assets = [a for a in all_assets if f"/{m}/" in a and ("Texture" in a or "Textures/" in a)]
    mat_assets = [a for a in all_assets if f"/{m}/" in a and ("Material" in a or "Materials/" in a)]
    
    unreal.log_warning(f"  Meshes ({len(mesh_assets)}):")
    for ma in mesh_assets[:5]:
        unreal.log_warning(f"    {ma}")
    if len(mesh_assets) > 5:
        unreal.log_warning(f"    ... and {len(mesh_assets) - 5} more")

    unreal.log_warning(f"  Textures ({len(tex_assets)}):")
    for ta in tex_assets:
        unreal.log_warning(f"    {ta}")

    unreal.log_warning(f"  Materials ({len(mat_assets)}):")
    for mata in mat_assets:
        unreal.log_warning(f"    {mata}")
