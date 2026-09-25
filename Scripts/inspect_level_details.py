import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

unreal.log_warning("=== INSPECTING LEVEL ACTORS & COLLISION ===")

terrain_actor = None
for a in editor_actor_sub.get_all_level_actors():
    if "Terrain" in a.get_actor_label():
        terrain_actor = a
        break

if terrain_actor:
    loc = terrain_actor.get_actor_location()
    bounds = terrain_actor.get_actor_bounds(False)
    sm = terrain_actor.get_component_by_class(unreal.StaticMeshComponent)
    unreal.log_warning(f"Terrain Actor Location: {loc}")
    unreal.log_warning(f"Terrain Bounds Origin: {bounds[0]}, Extent: {bounds[1]}")
    if sm:
        unreal.log_warning(f"Component Collision Profile: {sm.get_collision_profile_name()}")
        unreal.log_warning(f"Component Collision Enabled: {sm.get_collision_enabled()}")
        unreal.log_warning(f"Static Mesh: {sm.get_editor_property('static_mesh')}")
        mesh = sm.get_editor_property('static_mesh')
        if mesh:
            body = mesh.get_editor_property("body_setup")
            unreal.log_warning(f"Mesh BodySetup: {body}")
            if body:
                unreal.log_warning(f"Trace Flag: {body.get_editor_property('collision_trace_flag')}")

ps_actors = [a for a in editor_actor_sub.get_all_level_actors() if isinstance(a, unreal.PlayerStart)]
for ps in ps_actors:
    unreal.log_warning(f"PlayerStart Location: {ps.get_actor_location()}")

# Check Character Blueprint
char_bp = editor_asset_sub.load_asset("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter")
unreal.log_warning(f"Character BP loaded: {char_bp}")

# Check World Settings GameMode
ws = editor_actor_sub.get_all_level_actors()
for a in ws:
    if isinstance(a, unreal.WorldSettings):
        unreal.log_warning(f"WorldSettings DefaultGameMode: {a.get_editor_property('default_game_mode')}")
