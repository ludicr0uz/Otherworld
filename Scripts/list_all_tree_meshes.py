import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

tree_folders = ["island_tree_01", "island_tree_02", "fir_tree_01", "tree_small_02", "pine_sapling_small"]

for f in tree_folders:
    assets = editor_asset_sub.list_assets(f"/Game/Forest/Scanned/{f}", recursive=True)
    sm_assets = [a for a in assets if ("StaticMeshes" in a or "SM_" in a) and not "Material" in a and not "Texture" in a]
    unreal.log_warning(f"=== Tree Folder: {f} meshes: ===")
    for m in sm_assets:
        unreal.log_warning(f"  {m}")
