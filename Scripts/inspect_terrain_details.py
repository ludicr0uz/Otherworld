import unreal

level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

for a in editor_actor_sub.get_all_level_actors():
    if "Forest" in a.get_actor_label() or "Terrain" in a.get_actor_label() or "Bedrock" in a.get_actor_label():
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            mesh = smc.get_editor_property("static_mesh")
            mats = [smc.get_material(i).get_name() if smc.get_material(i) else "None" for i in range(smc.get_num_materials())]
            unreal.log_warning(f"Terrain Actor: {a.get_actor_label()} | Mesh: {mesh.get_path_name() if mesh else 'None'} | Materials: {mats}")
