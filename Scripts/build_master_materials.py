import unreal

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
mel = unreal.MaterialEditingLibrary

def build_master_foliage():
    mat_path = "/Game/Forest/Materials/M_Master_Foliage"
    mat_name = "M_Master_Foliage"
    pkg_path = "/Game/Forest/Materials"
    
    mat = editor_asset_sub.load_asset(mat_path)
    if not mat:
        mat = asset_tools.create_asset(mat_name, pkg_path, unreal.Material, unreal.MaterialFactoryNew())
    
    mel.delete_all_material_expressions(mat)
    
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("opacity_mask_clip_value", 0.33)
    mat.set_editor_property("used_with_nanite", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    
    # 1. BaseColor & Opacity Mask Texture Parameter
    tex_base = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, -100)
    tex_base.set_editor_property("parameter_name", "BaseColorTexture")
    # Default texture
    def_tex = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_diff-island_tree_01_leaves_alpha")
    if def_tex:
        tex_base.set_editor_property("texture", def_tex)
    mel.connect_material_property(tex_base, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(tex_base, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    
    # Subsurface Color: multiply BaseColor by foliage tint (0.75, 0.9, 0.45)
    tint = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 150)
    tint.set_editor_property("constant", unreal.LinearColor(r=0.75, g=0.95, b=0.45, a=1.0))
    mult = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 100)
    mel.connect_material_expressions(tex_base, "RGB", mult, "A")
    mel.connect_material_expressions(tint, "", mult, "B")
    mel.connect_material_property(mult, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    
    # 2. Normal Map Texture Parameter
    tex_norm = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, 300)
    tex_norm.set_editor_property("parameter_name", "NormalTexture")
    tex_norm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    def_norm = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_nor_gl")
    if def_norm:
        tex_norm.set_editor_property("texture", def_norm)
    mel.connect_material_property(tex_norm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    
    # 3. Roughness Texture Parameter
    tex_rough = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, 500)
    tex_rough.set_editor_property("parameter_name", "RoughnessTexture")
    tex_rough.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    def_rough = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_leaves_rough")
    if def_rough:
        tex_rough.set_editor_property("texture", def_rough)
    mel.connect_material_property(tex_rough, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    
    mel.recompile_material(mat)
    editor_asset_sub.save_loaded_asset(mat)
    unreal.log_warning("[AGY] M_Master_Foliage built and saved successfully!")
    return mat

def build_master_bark():
    mat_path = "/Game/Forest/Materials/M_Master_Bark"
    mat_name = "M_Master_Bark"
    pkg_path = "/Game/Forest/Materials"
    
    mat = editor_asset_sub.load_asset(mat_path)
    if not mat:
        mat = asset_tools.create_asset(mat_name, pkg_path, unreal.Material, unreal.MaterialFactoryNew())
    
    mel.delete_all_material_expressions(mat)
    
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("used_with_nanite", True)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    
    # 1. BaseColor
    tex_base = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, -100)
    tex_base.set_editor_property("parameter_name", "BaseColorTexture")
    def_tex = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_diff")
    if def_tex:
        tex_base.set_editor_property("texture", def_tex)
    mel.connect_material_property(tex_base, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    
    # 2. Normal Map
    tex_norm = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, 150)
    tex_norm.set_editor_property("parameter_name", "NormalTexture")
    tex_norm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    def_norm = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_nor_gl")
    if def_norm:
        tex_norm.set_editor_property("texture", def_norm)
    mel.connect_material_property(tex_norm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    
    # 3. Roughness
    tex_rough = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -400, 400)
    tex_rough.set_editor_property("parameter_name", "RoughnessTexture")
    tex_rough.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    def_rough = editor_asset_sub.load_asset("/Game/Forest/Scanned/island_tree_01/island_tree_01_1k/Textures/island_tree_01_rough")
    if def_rough:
        tex_rough.set_editor_property("texture", def_rough)
    mel.connect_material_property(tex_rough, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    
    mel.recompile_material(mat)
    editor_asset_sub.save_loaded_asset(mat)
    unreal.log_warning("[AGY] M_Master_Bark built and saved successfully!")
    return mat

build_master_foliage()
build_master_bark()
