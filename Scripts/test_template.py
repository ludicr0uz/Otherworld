"""
Test creating level from Template_Default
"""
import unreal

def test_template():
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    
    target = "/Game/Maps/Lvl_Forest"
    template = "/Engine/Maps/Templates/Template_Default"
    
    unreal.log(f"[TEST] Creating {target} from template {template}...")
    success = level_editor_sub.new_level_from_template(target, template)
    unreal.log(f"[TEST] Result: {success}")
    
    if success:
        level_editor_sub.save_current_level()
        unreal.log(f"[TEST] Saved {target} successfully!")

if __name__ == "__main__":
    test_template()
