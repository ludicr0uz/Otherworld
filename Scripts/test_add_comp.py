import unreal

editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = editor_actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))

mesh = unreal.load_asset("/Game/Forest/Scanned/tree_small_02/tree_small_02_1k/StaticMeshes/SM_tree_small_02.SM_tree_small_02")

comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
comp.set_static_mesh(mesh)
actor.set_editor_property("root_component", comp)

# Add an instance
tf = unreal.Transform(location=unreal.Vector(100, 100, 50), rotation=unreal.Rotator(pitch=0, yaw=45, roll=0), scale=unreal.Vector(1, 1, 1))
idx = comp.add_instance(tf)
unreal.log_warning(f"Added instance index: {idx}, Instance count: {comp.get_instance_count()}")

editor_actor_sub.destroy_actor(actor)
unreal.log_warning("SUCCESSFULLY tested HISM actor creation!")
