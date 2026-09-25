import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)
for a in assets:
    if "Material" in a:
        mat = editor_asset_sub.load_asset(a)
        if mat and isinstance(mat, unreal.Material):
            blend_mode = mat.get_editor_property("blend_mode")
            two_sided = mat.get_editor_property("two_sided")
            unreal.log_warning(f"Material: {mat.get_name()} | BlendMode: {blend_mode} | TwoSided: {two_sided}")
