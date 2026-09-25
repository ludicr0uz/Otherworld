import unreal

print("=== Material API Test ===")
print("MaterialEditingLibrary:", hasattr(unreal, "MaterialEditingLibrary"))
if hasattr(unreal, "MaterialEditingLibrary"):
    print("Methods:", [m for m in dir(unreal.MaterialEditingLibrary) if not m.startswith("_")])
