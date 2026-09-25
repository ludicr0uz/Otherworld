import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

actors = editor_actor_sub.get_all_level_actors()
unreal.log_warning(f"=== Actors in Lvl_Forest ({len(actors)}) ===")
for a in actors:
    lbl = a.get_actor_label()
    cls = a.get_class().get_name()
    loc = a.get_actor_location()
    unreal.log_warning(f"Actor: {lbl:<30} | Class: {cls:<25} | Loc: {loc}")
