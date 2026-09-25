import unreal

mel = unreal.MaterialEditingLibrary

unreal.log_warning("=== MATERIAL EDITING LIBRARY METHODS ===")
for m in dir(mel):
    if not m.startswith("_"):
        unreal.log_warning(f"  {m}")

unreal.log_warning("\n=== MATERIAL INSTANCE CONSTANT PROPERTIES ===")
mic = unreal.MaterialInstanceConstant()
for p in dir(mic):
    if not p.startswith("_"):
        unreal.log_warning(f"  {p}")
