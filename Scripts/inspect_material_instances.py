import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

mesh_paths = [
    "/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01",
    "/Game/Forest/Scanned/island_tree_02/island_tree_02_1k/StaticMeshes/SM_island_tree_02.SM_island_tree_02",
    "/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02",
    "/Game/Forest/Scanned/fir_tree_01/fir_tree_01_1k/StaticMeshes/fir_tree_01_a_LOD0.fir_tree_01_a_LOD0",
    "/Game/Forest/Scanned/pine_sapling_small/pine_sapling_small_1k/StaticMeshes/pine_sapling_small_a.pine_sapling_small_a"
]

for mp in mesh_paths:
    mesh = editor_asset_sub.load_asset(mp)
    if not mesh:
        continue
    unreal.log_warning(f"\n==================================================")
    unreal.log_warning(f"MESH: {mesh.get_name()}")
    num_sections = mesh.get_num_sections(0)
    for s in range(num_sections):
        mat = mesh.get_material(s)
        if not mat:
            unreal.log_warning(f"  Slot {s}: None")
            continue
        unreal.log_warning(f"  Slot {s}: {mat.get_name()} ({mat.get_class().get_name()})")
        if isinstance(mat, unreal.MaterialInstanceConstant):
            parent = mat.get_editor_property("parent")
            unreal.log_warning(f"    Parent: {parent.get_name() if parent else 'None'} ({parent.get_path_name() if parent else ''})")
            
            # Check texture params
            tex_params = mat.get_editor_property("texture_parameter_values")
            for tp in tex_params:
                pname = tp.get_editor_property("parameter_info").get_editor_property("name")
                pval = tp.get_editor_property("parameter_value")
                unreal.log_warning(f"    TexParam: {pname} = {pval.get_name() if pval else 'None'}")
                if pval:
                    unreal.log_warning(f"      Size: {pval.blueprint_get_size_x()}x{pval.blueprint_get_size_y()}, Compression: {pval.get_editor_property('compression_settings')}")

            # Check scalar params
            scalar_params = mat.get_editor_property("scalar_parameter_values")
            for sp in scalar_params:
                pname = sp.get_editor_property("parameter_info").get_editor_property("name")
                pval = sp.get_editor_property("parameter_value")
                unreal.log_warning(f"    ScalarParam: {pname} = {pval}")

            # Check base property overrides
            bpo = mat.get_editor_property("base_property_overrides")
            if bpo:
                unreal.log_warning(f"    Override BlendMode: {bpo.get_editor_property('override_blend_mode')}, BlendMode: {bpo.get_editor_property('blend_mode')}")
                unreal.log_warning(f"    Override TwoSided: {bpo.get_editor_property('override_two_sided')}, TwoSided: {bpo.get_editor_property('two_sided')}")
                unreal.log_warning(f"    Override OpacityClip: {bpo.get_editor_property('override_opacity_mask_clip_value')}, ClipVal: {bpo.get_editor_property('opacity_mask_clip_value')}")
