import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

mesh_paths = [
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0"
]

for mp in mesh_paths:
    mesh = editor_asset_sub.load_asset(mp)
    if not mesh:
        unreal.log_warning(f"Could NOT load mesh: {mp}")
        continue
    unreal.log_warning(f"==================================================")
    unreal.log_warning(f"MESH: {mesh.get_name()}")
    num_sections = mesh.get_num_sections(0)
    for s in range(num_sections):
        mat = mesh.get_material(s)
        mat_name = mat.get_name() if mat else "None"
        unreal.log_warning(f"  Slot {s}: {mat_name} (Class: {mat.get_class().get_name() if mat else 'None'})")
        if mat and isinstance(mat, unreal.Material):
            blend = mat.get_editor_property("blend_mode")
            two_sided = mat.get_editor_property("two_sided")
            clip_val = mat.get_editor_property("opacity_mask_clip_value")
            unreal.log_warning(f"    BlendMode: {blend}, TwoSided: {two_sided}, ClipVal: {clip_val}")
            exprs = mel.get_material_expressions(mat)
            for exp in exprs:
                if isinstance(exp, unreal.MaterialExpressionTextureSample):
                    tex = exp.get_editor_property("texture")
                    tname = tex.get_name() if tex else "None"
                    unreal.log_warning(f"    TextureSample: {tname}")
                    if tex:
                        unreal.log_warning(f"      Size: {tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()}, Compression: {tex.get_editor_property('compression_settings')}")
                elif isinstance(exp, unreal.MaterialExpressionTextureCoordinate):
                    unreal.log_warning(f"    TexCoord: UTiling={exp.get_editor_property('u_tiling')}, VTiling={exp.get_editor_property('v_tiling')}")
                else:
                    unreal.log_warning(f"    Expr: {exp.get_class().get_name()}")
