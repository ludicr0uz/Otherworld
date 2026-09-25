import unreal

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
mat = unreal.load_asset(mat_path)
mel = unreal.MaterialEditingLibrary

exprs = mel.get_material_expressions(mat)
out = [f"Material: {mat.get_name()}, Total expressions: {len(exprs)}"]
for e in exprs:
    out.append(f"  Expr: {e.get_name()} ({e.get_class().get_name()})")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/verify_mat_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning(f"Verification done: {len(exprs)} expressions")
