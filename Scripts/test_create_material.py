import unreal

def test_mat_creation():
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    mat_path = "/Game/Forest/Materials"
    mat_name = "M_Forest_Grass"
    full_path = f"{mat_path}/{mat_name}"

    if editor_asset_sub.does_asset_exist(full_path):
        editor_asset_sub.delete_asset(full_path)

    # Create Material Asset
    mat_factory = unreal.MaterialFactoryNew()
    mat = asset_tools.create_asset(mat_name, mat_path, unreal.Material, mat_factory)
    if not mat:
        unreal.log_error(f"Failed to create material {full_path}")
        return

    # Add Texture Sample Expression
    tex_path = "/Game/Forest/Textures/T_Forest_Grass_D.T_Forest_Grass_D"
    tex_asset = editor_asset_sub.load_asset(tex_path)

    if hasattr(unreal, "MaterialEditingLibrary"):
        mel = unreal.MaterialEditingLibrary
        if tex_asset:
            tex_node = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -300, 0)
            tex_node.set_editor_property("texture", tex_asset)
            mel.connect_material_property(tex_node, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        else:
            # Fallback constant 3 vector (lush green)
            vec_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, 0)
            vec_node.set_editor_property("constant", unreal.LinearColor(0.12, 0.38, 0.08, 1.0))
            mel.connect_material_property(vec_node, "", unreal.MaterialProperty.MP_BASE_COLOR)

        # Roughness constant
        rough_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 150)
        rough_node.set_editor_property("r", 0.85)
        mel.connect_material_property(rough_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

        mel.recompile_material(mat)
        mel.update_material_after_graph_change(mat)

    editor_asset_sub.save_asset(full_path)
    unreal.log(f"[AGY] Successfully created and saved material: {full_path}")

test_mat_creation()
