import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

out = ["=== Level HISM Actors & Instances ==="]
actors = editor_actor_sub.get_all_level_actors()

total_instances = 0
for a in actors:
    lbl = a.get_actor_label()
    comp = a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
    if comp:
        cnt = comp.get_instance_count()
        total_instances += cnt
        m = comp.static_mesh
        m_name = m.get_name() if m else "None"
        num_mats = comp.get_num_materials()
        mat_names = [comp.get_material(i).get_name() if comp.get_material(i) else "None" for i in range(num_mats)]
        out.append(f"HISM '{lbl}': {cnt} instances | Mesh: {m_name} | Mats: {mat_names}")

out.append(f"\nTotal Instanced Objects: {total_instances}")

# Check Terrain
for a in actors:
    if a.get_actor_label() == "Forest_Terrain_Landscape":
        smc = a.get_component_by_class(unreal.StaticMeshComponent)
        if smc:
            m = smc.static_mesh
            bs = m.get_editor_property("body_setup")
            nanite = m.get_editor_property("nanite_settings")
            out.append(f"\nTerrain Actor: Mesh={m.get_name()}, Nanite={nanite.get_editor_property('enabled') if nanite else 'N/A'}, CollisionTrace={bs.get_editor_property('collision_trace_flag') if bs else 'N/A'}")

with open("/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/hism_verification_out.txt", "w") as f:
    f.write("\n".join(out))

unreal.log_warning(f"Verification complete: {total_instances} instances across {len(actors)} actors")
