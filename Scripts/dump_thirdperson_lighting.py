"""
Dump all lighting, atmosphere, and environment actors from Lvl_ThirdPerson
"""
import unreal

def dump_lighting():
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    
    level_editor_sub.load_level("/Game/ThirdPerson/Lvl_ThirdPerson")
    actors = editor_actor_sub.get_all_level_actors()
    
    unreal.log("================ ALL ACTORS IN LVL_THIRDPERSON ================")
    for a in actors:
        label = a.get_actor_label()
        cls_name = type(a).__name__
        loc = a.get_actor_location()
        rot = a.get_actor_rotation()
        scale = a.get_actor_scale3d()
        unreal.log(f"[{cls_name}] '{label}' at Loc={loc}, Rot={rot}, Scale={scale}")
        for comp in a.get_components_by_class(unreal.ActorComponent):
            comp_name = type(comp).__name__
            unreal.log(f"    -> Component: {comp_name} ({comp.get_name()})")

if __name__ == "__main__":
    dump_lighting()
