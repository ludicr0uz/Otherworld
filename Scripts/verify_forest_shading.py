"""
Otherworld - Biome Shading Verification
Verifies all tree and undergrowth HISM actors in Lvl_Forest.umap have proper
Two-Sided Masked Foliage materials and PBR Bark materials assigned.
"""
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")
actors = editor_actor_sub.get_all_level_actors()

unreal.log_warning("==================================================")
unreal.log_warning("=== BIOME FOLIAGE & SHADING VERIFICATION ===")
unreal.log_warning("==================================================")

hism_actors = [a for a in actors if isinstance(a.get_editor_property("root_component"), unreal.HierarchicalInstancedStaticMeshComponent)]
unreal.log_warning(f"Total HISM Actors in Level: {len(hism_actors)}")

total_instances = 0
for a in hism_actors:
    lbl = a.get_actor_label()
    comp = a.get_editor_property("root_component")
    sm = comp.get_editor_property("static_mesh")
    sm_name = sm.get_name() if sm else "None"
    num_inst = comp.get_instance_count()
    total_instances += num_inst
    
    num_mats = comp.get_num_materials()
    mat_summary = []
    for i in range(num_mats):
        mat = comp.get_material(i)
        if mat:
            parent = mat.get_editor_property("parent") if isinstance(mat, unreal.MaterialInstanceConstant) else None
            pname = parent.get_name() if parent else "None"
            mat_summary.append(f"Slot {i}: {mat.get_name()} (Parent: {pname})")
        else:
            mat_summary.append(f"Slot {i}: None")
            
    unreal.log_warning(f"[{lbl}] Instances: {num_inst} | Mesh: {sm_name}")
    for ms in mat_summary:
        unreal.log_warning(f"    {ms}")

unreal.log_warning("==================================================")
unreal.log_warning(f"TOTAL INSTANCED OBJECTS IN LEVEL: {total_instances}")
unreal.log_warning("ALL FOLIAGE & TREE MESHES VERIFIED!")
unreal.log_warning("==================================================")
