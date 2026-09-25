import unreal

mat_path = "/Game/Forest/Materials/M_Forest_Ground_PBR"
mat = unreal.load_asset(mat_path)
mel = unreal.MaterialEditingLibrary

# Print all expressions and how many there are
exprs = mel.get_material_expressions(mat)
print(f"Number of expressions: {len(exprs)}")
for e in exprs:
    print(f"  Expr: {e.get_name()} ({e.get_class().get_name()})")

