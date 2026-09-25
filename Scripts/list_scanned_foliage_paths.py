import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

for f in ["grass_medium_01", "grass_medium_02", "fern_02", "moss_01"]:
    assets = editor_asset_sub.list_assets(f"/Game/Forest/Scanned/{f}", recursive=True)
    unreal.log_warning(f"=== Folder /Game/Forest/Scanned/{f} assets: ===")
    for a in assets:
        unreal.log_warning(f"  {a}")
