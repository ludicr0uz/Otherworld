import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

mat = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Forest_Ground_PBR")
unreal.log_warning(f"=== INSPECTING MATERIAL CONNECTIONS FOR: {mat.get_name()} ===")

for prop in [
    unreal.MaterialProperty.MP_BASE_COLOR,
    unreal.MaterialProperty.MP_NORMAL,
    unreal.MaterialProperty.MP_ROUGHNESS,
    unreal.MaterialProperty.MP_SPECULAR,
    unreal.MaterialProperty.MP_METALLIC,
    unreal.MaterialProperty.MP_AMBIENT_OCCLUSION,
    unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    unreal.MaterialProperty.MP_OPACITY,
    unreal.MaterialProperty.MP_OPACITY_MASK
]:
    node = mel.get_material_property_input_node(mat, prop)
    output_name = mel.get_material_property_input_node_output_name(mat, prop)
    node_name = node.get_name() if node else "None"
    node_class = node.get_class().get_name() if node else "None"
    unreal.log_warning(f"Property {prop} -> Node: {node_name} ({node_class}), OutputPin: '{output_name}'")

# Also check UV coordinates on SM_ForestLandscape
mesh = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
unreal.log_warning(f"SM_ForestLandscape: {mesh.get_name()}")
