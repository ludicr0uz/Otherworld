import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
actors = editor_actor_sub.get_all_level_actors()

tree_count = len([a for a in actors if "Tree" in a.get_actor_label()])
rock_count = len([a for a in actors if "Rock" in a.get_actor_label()])
bush_count = len([a for a in actors if "Bush" in a.get_actor_label()])
terrain_count = len([a for a in actors if "Terrain" in a.get_actor_label()])
ps_count = len([a for a in actors if isinstance(a, unreal.PlayerStart)])

unreal.log_warning(f"=== Lvl_Forest Verification ===")
unreal.log_warning(f"Total Actors: {len(actors)}")
unreal.log_warning(f"3D Trees: {tree_count}")
unreal.log_warning(f"Rock Boulders: {rock_count}")
unreal.log_warning(f"Bushes: {bush_count}")
unreal.log_warning(f"Terrain Landscape: {terrain_count}")
unreal.log_warning(f"Player Start: {ps_count}")
