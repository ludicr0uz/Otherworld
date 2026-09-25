import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

all_assets = editor_asset_sub.list_assets("/Game/Forest", recursive=True)
texs = [a for a in all_assets if "Texture" in a or "T_" in a or "diff" in a or "nor" in a or "rough" in a]

unreal.log_warning(f"=== TOTAL TEXTURES IN /Game/Forest: {len(texs)} ===")
for t in sorted(texs):
    obj = editor_asset_sub.load_asset(t)
    if isinstance(obj, unreal.Texture):
        unreal.log_warning(f"TEX: {obj.get_name()} -> {t}")
