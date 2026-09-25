import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

actors = editor_actor_sub.get_all_level_actors()
unreal.log_warning(f"=== Total level actors: {len(actors)} ===")

total_instances = 0
for a in actors:
    lbl = a.get_actor_label()
    comp = a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
    if comp:
        cnt = comp.get_instance_count()
        mesh = comp.get_editor_property("static_mesh")
        mesh_name = mesh.get_name() if mesh else "None"
        total_instances += cnt
        unreal.log_warning(f"Actor: {lbl:<22} | Mesh: {mesh_name:<30} | Instances: {cnt} | Collision: {comp.get_collision_enabled()}")
    elif isinstance(a, unreal.PlayerStart):
        unreal.log_warning(f"PlayerStart at {a.get_actor_location()} rot={a.get_actor_rotation()}")
    elif isinstance(a, (unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere, unreal.ExponentialHeightFog, unreal.PostProcessVolume)):
        unreal.log_warning(f"Atmospheric Actor: {a.get_name()} ({a.get_class().get_name()})")

unreal.log_warning(f"=== Total Instanced Photogrammetry Objects: {total_instances} across {len([a for a in actors if a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)])} draw calls ===")
