import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

unreal.log_warning("=== INSPECTING ALL SCANNED STATIC MESHES AND MATERIALS ===")

assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)
meshes = [a for a in assets if "SM_" in a or "fir_tree" in a or "pine" in a or "tree" in a]

for a in assets:
    obj = editor_asset_sub.load_asset(a)
    if isinstance(obj, unreal.StaticMesh):
        unreal.log_warning(f"\n--- MESH: {obj.get_name()} ({a}) ---")
        num_mats = obj.get_num_sections(0)
        unreal.log_warning(f"  Sections (LOD0): {num_mats}")
        for i in range(num_mats):
            mat_interface = obj.get_material(i)
            mat_name = mat_interface.get_name() if mat_interface else "None"
            unreal.log_warning(f"  Slot {i}: {mat_name}")
            if mat_interface and isinstance(mat_interface, unreal.Material):
                blend = mat_interface.get_editor_property("blend_mode")
                two_sided = mat_interface.get_editor_property("two_sided")
                clip_val = mat_interface.get_editor_property("opacity_mask_clip_value")
                unreal.log_warning(f"    BlendMode: {blend}, TwoSided: {two_sided}, Clip: {clip_val}")
                exprs = mel.get_material_expressions(mat_interface)
                for exp in exprs:
                    if isinstance(exp, unreal.MaterialExpressionTextureSample):
                        tex = exp.get_editor_property("texture")
                        tname = tex.get_name() if tex else "None"
                        unreal.log_warning(f"    TextureSample: {tname}")
    elif isinstance(obj, unreal.Material):
        unreal.log_warning(f"\n--- MATERIAL: {obj.get_name()} ({a}) ---")
        blend = obj.get_editor_property("blend_mode")
        two_sided = obj.get_editor_property("two_sided")
        clip_val = obj.get_editor_property("opacity_mask_clip_value")
        unreal.log_warning(f"  BlendMode: {blend}, TwoSided: {two_sided}, Clip: {clip_val}")
        exprs = mel.get_material_expressions(obj)
        for exp in exprs:
            if isinstance(exp, unreal.MaterialExpressionTextureSample):
                tex = exp.get_editor_property("texture")
                tname = tex.get_name() if tex else "None"
                unreal.log_warning(f"  TextureSample: {tname}")

unreal.log_warning("=== INSPECTION COMPLETE ===")
