import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

master_foliage = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Master_Foliage")
unreal.log_warning(f"Master foliage loaded: {master_foliage.get_name()}")

mi_name = "MI_IslandTree01_Leaves"
pkg_path = "/Game/Forest/Materials"
mi_path = f"{pkg_path}/{mi_name}"

factory = unreal.MaterialInstanceConstantFactoryNew()
mic = asset_tools.create_asset(mi_name, pkg_path, unreal.MaterialInstanceConstant, factory)
if mic:
    mic.set_editor_property("parent", master_foliage)
    
    diff_tex = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_diff-island_tree_01_leaves_alpha")
    norm_tex = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_nor_gl")
    rough_tex = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_rough")
    
    mel.set_material_instance_texture_parameter_value(mic, "BaseColorTexture", diff_tex)
    mel.set_material_instance_texture_parameter_value(mic, "NormalTexture", norm_tex)
    mel.set_material_instance_texture_parameter_value(mic, "RoughnessTexture", rough_tex)
    
    mel.update_material_instance(mic)
    editor_asset_sub.save_loaded_asset(mic)
    unreal.log_warning(f"[AGY] Created and configured {mi_name} successfully!")

    # Assign to SM_island_tree_01 slot 1
    mesh = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/StaticMeshes/SM_island_tree_01.SM_island_tree_01")
    if mesh:
        mesh.set_material(1, mic)
        editor_asset_sub.save_loaded_asset(mesh)
        unreal.log_warning(f"[AGY] Assigned {mi_name} to SM_island_tree_01 slot 1!")
