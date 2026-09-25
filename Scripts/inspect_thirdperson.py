"""
Inspect actors in Lvl_ThirdPerson
"""
import unreal

def inspect_third_person():
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    
    level_editor_sub.load_level("/Game/ThirdPerson/Lvl_ThirdPerson")
    actors = editor_actor_sub.get_all_level_actors()
    unreal.log("================ ACTORS IN THIRD PERSON MAP ================")
    for a in actors:
        unreal.log(f"Actor: {a.get_actor_label()} ({type(a).__name__}) - Location: {a.get_actor_location()}")

if __name__ == "__main__":
    inspect_third_person()
