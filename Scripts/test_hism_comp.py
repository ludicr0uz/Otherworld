import unreal

editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = editor_actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
comp = actor.add_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent, False, unreal.Transform(), False)
unreal.log_warning(f"Created HISM component: {comp}")
editor_actor_sub.destroy_actor(actor)
