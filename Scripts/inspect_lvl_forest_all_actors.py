import unreal

editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
actors = editor_actor_sub.get_all_level_actors()

unreal.log_warning("=== ALL ACTORS IN LVL_FOREST ===")
for a in actors:
    lbl = a.get_actor_label()
    root = a.get_editor_property("root_component")
    comp_type = root.get_class().get_name() if root else "None"
    mesh_name = "None"
    if isinstance(root, unreal.StaticMeshComponent):
        sm = root.get_editor_property("static_mesh")
        mesh_name = sm.get_name() if sm else "None"
        num_mats = root.get_num_materials()
        mat_names = [root.get_material(i).get_name() if root.get_material(i) else "None" for i in range(num_mats)]
        unreal.log_warning(f"Actor: {lbl} ({comp_type}) -> Mesh: {mesh_name} | Mats: {mat_names}")
    else:
        unreal.log_warning(f"Actor: {lbl} ({comp_type})")
