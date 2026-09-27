import os
import unreal

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
gltf_file = os.path.join(PROJECT_DIR, "assets", "cache", "scanned", "rock_07", "rock_07_1k.gltf")

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

task = unreal.AssetImportTask()
task.filename = gltf_file
task.destination_path = "/Game/Forest/Scanned"
task.destination_name = "SM_Rock_07"
task.replace_existing = True
task.automated = True
task.save = True

asset_tools.import_asset_tasks([task])

assets = editor_asset_sub.list_assets("/Game/Forest/Scanned", recursive=True)
unreal.log_warning(f"Imported GLTF assets in /Game/Forest/Scanned: {assets}")
