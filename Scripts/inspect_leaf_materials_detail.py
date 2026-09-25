import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

mat_names = [
    "island_tree_01_leaves",
    "island_tree_02_leaves",
    "tree_small_02_leaves",
    "fir_tree_01_twig",
    "pine_sapling_small_twig"
]

all_assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)

for name in mat_names:
    matches = [a for a in all_assets if name == a.split("/")[-1].split(".")[0]]
    for mpath in matches:
        mat = editor_asset_sub.load_asset(mpath)
        if isinstance(mat, unreal.Material):
            unreal.log_warning(f"=== MATERIAL: {mat.get_name()} ({mpath}) ===")
            unreal.log_warning(f"  blend_mode: {mat.get_editor_property('blend_mode')}")
            unreal.log_warning(f"  two_sided: {mat.get_editor_property('two_sided')}")
            unreal.log_warning(f"  opacity_mask_clip_value: {mat.get_editor_property('opacity_mask_clip_value')}")
            unreal.log_warning(f"  shading_model: {mat.get_editor_property('shading_model')}")
            
            exprs = mel.get_material_expressions(mat)
            unreal.log_warning(f"  Expressions count: {len(exprs)}")
            for exp in exprs:
                exp_class = exp.get_class().get_name()
                if isinstance(exp, unreal.MaterialExpressionTextureSample):
                    tex = exp.get_editor_property("texture")
                    tname = tex.get_name() if tex else "None"
                    tpath = tex.get_path_name() if tex else "None"
                    unreal.log_warning(f"    TextureSample: {tname} (path: {tpath})")
                else:
                    unreal.log_warning(f"    Expr: {exp_class} ({exp.get_name()})")
