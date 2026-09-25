import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
actors = editor_actor_sub.get_all_level_actors()

tree_count = len([a for a in actors if "RealisticTree" in a.get_actor_label()])
log_count = len([a for a in actors if "FallenLog" in a.get_actor_label()])
fern_count = len([a for a in actors if "Fern" in a.get_actor_label()])
rock_count = len([a for a in actors if "GraniteBoulder" in a.get_actor_label()])

unreal.log_warning(f"=== Photorealistic Forest Verification ===")
unreal.log_warning(f"Total Actors: {len(actors)}")
unreal.log_warning(f"Realistic Trees: {tree_count}")
unreal.log_warning(f"Fallen Mossy Logs: {log_count}")
unreal.log_warning(f"Fern Clusters: {fern_count}")
unreal.log_warning(f"Granite Boulders: {rock_count}")
