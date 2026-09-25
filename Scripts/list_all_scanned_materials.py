import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

all_assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)

for a in all_assets:
    obj = editor_asset_sub.load_asset(a)
    if isinstance(obj, unreal.Material):
        unreal.log_warning(f"=== MAT: {obj.get_name()} | Path: {a} ===")
        unreal.log_warning(f"    BlendMode: {obj.get_editor_property('blend_mode')}")
        unreal.log_warning(f"    TwoSided: {obj.get_editor_property('two_sided')}")
        unreal.log_warning(f"    ClipValue: {obj.get_editor_property('opacity_mask_clip_value')}")
        exprs = mel.get_material_expressions(obj)
        for exp in exprs:
            if isinstance(exp, unreal.MaterialExpressionTextureSample):
                tex = exp.get_editor_property("texture")
                tname = tex.get_name() if tex else "None"
                unreal.log_warning(f"    TextureSample: {tname}")
            else:
                unreal.log_warning(f"    Expr: {exp.get_class().get_name()}")
