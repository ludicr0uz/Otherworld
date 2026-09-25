import unreal

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
mat = unreal.load_asset(mat_path)
mel = unreal.MaterialEditingLibrary

out = [f"=== M_Forest_Ground_PBR ==="]
out.append(f"BlendMode: {mat.get_editor_property('blend_mode')}")
out.append(f"ShadingModel: {mat.get_editor_property('shading_model')}")

for exp in mel.get_material_expressions(mat):
    cls_name = exp.get_class().get_name()
    name = exp.get_name()
    line = f"{name} ({cls_name}): "
    if isinstance(exp, unreal.MaterialExpressionTextureSample):
        tex = exp.get_editor_property("texture")
        st = exp.get_editor_property("sampler_type")
        line += f"tex={tex.get_name() if tex else 'None'} ({st})"
    elif isinstance(exp, unreal.MaterialExpressionConstant3Vector):
        val = exp.get_editor_property("constant")
        line += f"RGB=({val.r:.2f}, {val.g:.2f}, {val.b:.2f})"
    elif isinstance(exp, unreal.MaterialExpressionConstant):
        val = exp.get_editor_property("r")
        line += f"val={val}"
    elif isinstance(exp, unreal.MaterialExpressionTextureCoordinate):
        u = exp.get_editor_property("u_tiling")
        v = exp.get_editor_property("v_tiling")
        line += f"Tiling=({u}, {v})"
    out.append(line)

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/new_mat_details.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("Done new mat inspection")
