import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

all_assets = editor_asset_sub.list_assets("/Game/Forest", recursive=True)

unreal.log_warning("=== INSPECTING ALL FOREST MATERIALS ===")
for a in all_assets:
    obj = editor_asset_sub.load_asset(a)
    if isinstance(obj, unreal.Material):
        unreal.log_warning(f"\n--- MATERIAL: {obj.get_name()} ({a}) ---")
        unreal.log_warning(f"  blend_mode: {obj.get_editor_property('blend_mode')}")
        unreal.log_warning(f"  two_sided: {obj.get_editor_property('two_sided')}")
        unreal.log_warning(f"  opacity_clip: {obj.get_editor_property('opacity_mask_clip_value')}")
        exprs = mel.get_material_expressions(obj)
        for exp in exprs:
            if isinstance(exp, unreal.MaterialExpressionTextureSample):
                tex = exp.get_editor_property("texture")
                tname = tex.get_name() if tex else "None"
                unreal.log_warning(f"    TextureSample: {tname}")
            else:
                unreal.log_warning(f"    Expr: {exp.get_class().get_name()}")
