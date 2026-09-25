import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

# Remove any existing bedrock actor
for a in editor_actor_sub.get_all_level_actors():
    if "Bedrock" in a.get_actor_label():
        editor_actor_sub.destroy_actor(a)

# Spawn 500m x 500m Solid Bedrock Floor Slab
cube_mesh = editor_asset_sub.load_asset("/Engine/BasicShapes/Cube.Cube")
mat_grass = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Forest_Grass.M_Forest_Grass")

bedrock = editor_actor_sub.spawn_actor_from_class(
    unreal.StaticMeshActor,
    unreal.Vector(0, 0, -50),
    unreal.Rotator(0, 0, 0)
)
bedrock.set_actor_label("Forest_Bedrock_Floor")
bedrock.set_actor_scale3d(unreal.Vector(500.0, 500.0, 1.0)) # 500m x 500m x 1m

b_sm = bedrock.get_component_by_class(unreal.StaticMeshComponent)
if b_sm:
    b_sm.set_mobility(unreal.ComponentMobility.STATIC)
    if cube_mesh:
        b_sm.set_static_mesh(cube_mesh)
    if mat_grass:
        b_sm.set_material(0, mat_grass)
    b_sm.set_collision_profile_name("BlockAll")
    b_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    b_sm.set_editor_property("can_character_step_up_on", unreal.CanBeCharacterBase.ECB_YES)

# Position PlayerStart safely
for a in editor_actor_sub.get_all_level_actors():
    if isinstance(a, unreal.PlayerStart):
        a.set_actor_location(unreal.Vector(0, 0, 120), False, False)
        a.set_actor_rotation(unreal.Rotator(0, 0, 0), False)
        unreal.log_warning("[AGY] Positioned PlayerStart at (0, 0, 120)")

level_editor_sub.save_current_level()
unreal.log_warning("==================================================")
unreal.log_warning("[AGY] SOLID BEDROCK FOUNDATION ADDED & SAVED!")
unreal.log_warning("==================================================")
