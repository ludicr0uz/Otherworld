import unreal

methods = [m for m in dir(unreal.MaterialEditingLibrary) if not m.startswith("_")]
unreal.log(f"MEL_METHODS: {', '.join(methods)}")
