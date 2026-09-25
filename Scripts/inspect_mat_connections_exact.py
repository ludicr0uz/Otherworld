import unreal

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
mat = unreal.load_asset(mat_path)
out = []
mel = unreal.MaterialEditingLibrary

# Inspect all connections
# How does UE expose material input connections in Python?
# Let's inspect get_material_property_input_node or similar, or iterate all expressions and see who outputs to what

out.append(f"Material: {mat.get_name()}")
out.append(f"BlendMode: {mat.get_editor_property('blend_mode')}")
out.append(f"ShadingModel: {mat.get_editor_property('shading_model')}")
out.append(f"TwoSided: {mat.get_editor_property('two_sided')}")

for exp in mel.get_material_expressions(mat):
    out.append(f"\nExpression: {exp.get_name()} ({exp.get_class().get_name()})")
    for prop in dir(exp):
        if any(prop.startswith(k) for k in ["coordinates", "a", "b", "alpha", "input", "texture", "constant", "sampler"]):
            try:
                val = exp.get_editor_property(prop)
                if val is not None and not str(val).startswith("<unreal.ExpressionInput"):
                    out.append(f"  {prop} = {val}")
                elif str(val).startswith("<unreal.ExpressionInput"):
                    # Inspect ExpressionInput struct
                    expr_conn = val.expression
                    if expr_conn:
                        out.append(f"  {prop} -> {expr_conn.get_name()} (output_index={val.output_index})")
            except Exception as e:
                pass

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/mat_conn_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning("Done mat conn inspection")
