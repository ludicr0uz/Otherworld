import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

# Search for any existing foliage / megascans in Engine or Game
assets = editor_asset_sub.list_assets("/Engine", recursive=True)
foliage_assets = [a for a in assets if any(w in a.lower() for w in ["tree", "foliage", "rock", "megascans", "nature"])]
unreal.log_warning(f"Engine Foliage/Nature assets found: {len(foliage_assets)}")
for a in foliage_assets[:15]:
    unreal.log_warning(f"  {a}")

game_assets = editor_asset_sub.list_assets("/Game", recursive=True)
unreal.log_warning(f"Total Game assets: {len(game_assets)}")
