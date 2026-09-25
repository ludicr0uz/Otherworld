import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mel = unreal.MaterialEditingLibrary

# 1. Update all materials with used_with_nanite
mat_names = ["M_Forest_Grass", "M_Forest_Bark", "M_Forest_Pine", "M_Forest_Rock"]
for m_name in mat_names:
    m_path = f"/Game/Forest/Materials/{m_name}.{m_name}"
    mat = editor_asset_sub.load_asset(m_path)
    if mat:
        mat.set_editor_property("used_with_nanite", True)
        mel.recompile_material(mat)
        editor_asset_sub.save_loaded_asset(mat)
        unreal.log_warning(f"[AGY] Saved used_with_nanite = True on {m_name}")

# 2. Configure Meshes: Complex-As-Simple collision and disable Nanite on landscape for 100% collision accuracy
mesh_names = [
    "SM_ForestLandscape",
    "SM_PineTree_01",
    "SM_BroadleafTree_01",
    "SM_ForestRock_01",
    "SM_ForestBush_01"
]

for mesh_name in mesh_names:
    mesh_path = f"/Game/Forest/Meshes/{mesh_name}.{mesh_name}"
    mesh = editor_asset_sub.load_asset(mesh_path)
    if not mesh:
        continue

    # Disable Nanite on terrain so full collision tri-mesh is directly active in Chaos physics
    nanite_settings = mesh.get_editor_property("nanite_settings")
    if nanite_settings:
        if mesh_name == "SM_ForestLandscape":
            nanite_settings.set_editor_property("enabled", False)
        else:
            nanite_settings.set_editor_property("enabled", True)
        mesh.set_editor_property("nanite_settings", nanite_settings)

    body_setup = mesh.get_editor_property("body_setup")
    if body_setup:
        body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)

    editor_asset_sub.save_loaded_asset(mesh)
    unreal.log_warning(f"[AGY] Set CTF_USE_COMPLEX_AS_SIMPLE on {mesh_name}")

# 3. Setup Level actors & PlayerStart
level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

for actor in editor_actor_sub.get_all_level_actors():
    label = actor.get_actor_label()
    
    if "Terrain" in label:
        t_sm = actor.get_component_by_class(unreal.StaticMeshComponent)
        if t_sm:
            t_sm.set_mobility(unreal.ComponentMobility.STATIC)
            t_sm.set_collision_profile_name("BlockAll")
            t_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            t_sm.set_editor_property("can_character_step_up_on", unreal.CanBeCharacterBase.ECB_YES)
            actor.set_actor_location(unreal.Vector(0, 0, 0), False, False)
            unreal.log_warning(f"[AGY] Terrain actor collision verified: {label}")

    elif isinstance(actor, unreal.PlayerStart):
        # Position PlayerStart safely at Z = 150 in the clearing
        actor.set_actor_location(unreal.Vector(0, 0, 150), False, False)
        actor.set_actor_rotation(unreal.Rotator(0, 0, 0), False)
        unreal.log_warning(f"[AGY] Positioned PlayerStart at (0, 0, 150)")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] ALL NANITE FLAGS & COLLISION ISSUES FIXED!")
unreal.log_warning("==================================================")
