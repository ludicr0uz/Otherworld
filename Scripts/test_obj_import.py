"""
Test importing an OBJ mesh and texture into Unreal Engine
"""
import os
import unreal

def test_import():
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    # 1. Create a test obj file on disk
    obj_content = """# Test Mesh
v -50.0 0.0 -50.0
v 50.0 0.0 -50.0
v 50.0 0.0 50.0
v -50.0 0.0 50.0
vt 0.0 0.0
vt 1.0 0.0
vt 1.0 1.0
vt 0.0 1.0
vn 0.0 1.0 0.0
f 1/1/1 2/2/1 3/3/1
f 1/1/1 3/3/1 4/4/1
"""
    test_obj_path = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/test_quad.obj"
    with open(test_obj_path, "w") as f:
        f.write(obj_content)

    # 2. Import into Unreal
    import_task = unreal.AssetImportTask()
    import_task.filename = test_obj_path
    import_task.destination_path = "/Game/Forest/Test"
    import_task.destination_name = "SM_TestQuad"
    import_task.replace_existing = True
    import_task.automated = True
    import_task.save = True

    asset_tools.import_asset_tasks([import_task])
    
    imported_obj = editor_asset_sub.load_asset("/Game/Forest/Test/SM_TestQuad")
    unreal.log(f"[TEST IMPORT] Loaded imported mesh: {imported_obj} ({type(imported_obj)})")
    return imported_obj is not None

if __name__ == "__main__":
    test_import()
