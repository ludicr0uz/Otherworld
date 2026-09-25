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
    unreal.log_warning(f"=== MESH: {mesh.get_name()} ===")
    for s in range(mesh.get_num_sections(0)):
        mat = mesh.get_material(s)
        if not mat:
            continue
        unreal.log_warning(f"  Slot {s}: {mat.get_name()}")
        if isinstance(mat, unreal.MaterialInstanceConstant):
            parent = mat.get_editor_property("parent")
            pname = parent.get_name() if parent else "None"
            ppath = parent.get_path_name() if parent else ""
            bpo = mat.get_editor_property("base_property_overrides")
            blend_m = bpo.get_editor_property("blend_mode") if bpo and bpo.get_editor_property("override_blend_mode") else (parent.get_editor_property("blend_mode") if parent and isinstance(parent, unreal.Material) else "Unknown")
            unreal.log_warning(f"    Parent: {pname} ({ppath}) | Effective Blend: {blend_m}")
