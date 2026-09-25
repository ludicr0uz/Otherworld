import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
assets = editor_asset_sub.list_assets("/Game/Forest", recursive=True)
for a in assets:
    unreal.log_warning(f"ASSET: {a}")
