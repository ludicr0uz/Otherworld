import unreal

level_path = "/Game/Maps/Lvl_Forest.umap"
world = unreal.EditorLoadingAndSavingUtils.load_map(level_path)

actors = unreal.EditorLevelLibrary.get_all_level_actors()
out = []
out.append(f"[INSPECT] Total actors in level: {len(actors)}")

for actor in actors:
    name = actor.get_name()
    cls = actor.get_class().get_name()
    label = actor.get_actor_label()
    loc = actor.get_actor_location()
    scale = actor.get_actor_scale3d()
    out.append(f"\nActor: '{name}' | Label: '{label}' | Class: {cls} | Loc: {loc} | Scale: {scale}")
    
    # Check components
    for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
        comp_name = comp.get_name()
        comp_cls = comp.get_class().get_name()
        out.append(f"  Component: {comp_name} ({comp_cls})")
        if isinstance(comp, unreal.StaticMeshComponent):
            mesh = comp.static_mesh
            mesh_name = mesh.get_name() if mesh else "None"
            mesh_path = mesh.get_path_name() if mesh else "None"
            out.append(f"    StaticMesh: {mesh_name} ({mesh_path})")
            num_mats = comp.get_num_materials()
            for i in range(num_mats):
                mat = comp.get_material(i)
                mat_name = mat.get_name() if mat else "None"
                mat_path = mat.get_path_name() if mat else "None"
                out.append(f"    Comp Material[{i}]: {mat_name} ({mat_path})")
            if mesh:
                for mi, mat_slot in enumerate(mesh.static_materials):
                    m = mat_slot.material_interface
                    m_name = m.get_name() if m else "None"
                    m_path = m.get_path_name() if m else "None"
                    out.append(f"    Mesh MaterialSlot[{mi}] ({mat_slot.material_slot_name}): {m_name} ({m_path})")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/inspect_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning(f"Inspection written! Actors found: {len(actors)}")
