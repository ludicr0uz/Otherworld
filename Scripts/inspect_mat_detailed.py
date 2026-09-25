import unreal

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
mat = unreal.load_asset(mat_path)
out = []
out.append(f"Material: {mat.get_name()}")

mel = unreal.MaterialEditingLibrary

# Check expressions in material
expressions = mel.get_material_expressions(mat)
out.append(f"Total expressions: {len(expressions)}")
for exp in expressions:
    exp_cls = exp.get_class().get_name()
    desc = exp.get_editor_property("desc") if hasattr(exp, "desc") else ""
    out.append(f"Expression: {exp.get_name()} ({exp_cls}) desc='{desc}'")
    if isinstance(exp, unreal.MaterialExpressionTextureSample):
        tex = exp.get_editor_property("texture")
        sampler_type = exp.get_editor_property("sampler_type")
        tex_path = tex.get_path_name() if tex else "None"
        out.append(f"  Texture: {tex_path}, SamplerType: {sampler_type}")
    elif isinstance(exp, unreal.MaterialExpressionTextureSampleParameter2D):
        param_name = exp.get_editor_property("parameter_name")
        tex = exp.get_editor_property("texture")
        out.append(f"  ParamName: {param_name}, Texture: {tex.get_path_name() if tex else 'None'}")
    elif isinstance(exp, unreal.MaterialExpressionVectorParameter):
        param_name = exp.get_editor_property("parameter_name")
        val = exp.get_editor_property("default_value")
        out.append(f"  VectorParam: {param_name} = {val}")
    elif isinstance(exp, unreal.MaterialExpressionScalarParameter):
        param_name = exp.get_editor_property("parameter_name")
        val = exp.get_editor_property("default_value")
        out.append(f"  ScalarParam: {param_name} = {val}")
    elif isinstance(exp, unreal.MaterialExpressionConstant3Vector):
        val = exp.get_editor_property("constant")
        out.append(f"  Constant3Vector: {val}")
    elif isinstance(exp, unreal.MaterialExpressionConstant):
        val = exp.get_editor_property("r")
        out.append(f"  Constant: {val}")
    elif isinstance(exp, unreal.MaterialExpressionTextureCoordinate):
        ut = exp.get_editor_property("u_tiling")
        vt = exp.get_editor_property("v_tiling")
        out.append(f"  TexCoord: UTiling={ut}, VTiling={vt}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/mat_inspect_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("Done detailed mat inspection")
