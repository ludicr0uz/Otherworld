"""
Otherworld - Forest Starting Level Generator
Creates a clean, gorgeous level using Unreal Engine's official Template_Default,
providing authentic sky atmosphere, dynamic sunlight, clouds, and fog.
"""
import math
import sys
import unreal

def create_forest_level():
    unreal.log("==================================================")
    unreal.log("[AGY] Generating Forest Starting Level from Template_Default...")
    unreal.log("==================================================")

    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    target_map = "/Game/Maps/Lvl_Forest"
    template_map = "/Engine/Maps/Templates/Template_Default"

    # 1. Delete existing destination asset if present
    if editor_asset_sub.does_asset_exist(target_map):
        unreal.log(f"[AGY] Removing existing {target_map}...")
        editor_asset_sub.delete_asset(target_map)

    # 2. Create new level from official Template_Default
    unreal.log(f"[AGY] Creating level from {template_map}...")
    success = level_editor_sub.new_level_from_template(target_map, template_map)
    if not success:
        unreal.log_error("Failed to create level from template!")
        return False

    # 3. Load the new level
    level_editor_sub.load_level(target_map)

    # 4. Set WorldSettings GameMode
    for actor in editor_actor_sub.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            gm_class = editor_asset_sub.load_asset("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C")
            if gm_class:
                actor.set_editor_property("default_game_mode", gm_class)
            break

    # 5. Expand Floor / Terrain to large playable meadow
    floor_actors = [a for a in editor_actor_sub.get_all_level_actors() if "Floor" in a.get_actor_label() or "SM_Template_Map_Floor" in a.get_actor_label()]
    if floor_actors:
        floor_actors[0].set_actor_scale3d(unreal.Vector(150.0, 150.0, 1.0))
        floor_comp = floor_actors[0].get_component_by_class(unreal.StaticMeshComponent)
        if floor_comp:
            floor_comp.set_collision_profile_name("BlockAll")
            floor_comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 6. Add Campfire Landmark in Clearing
    cyl_mesh = editor_asset_sub.load_asset("/Game/LevelPrototyping/Meshes/SM_Cylinder.SM_Cylinder")
    chamfer_mesh = editor_asset_sub.load_asset("/Game/LevelPrototyping/Meshes/SM_ChamferCube.SM_ChamferCube")
    mat_dark = editor_asset_sub.load_asset("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark.MI_PrototypeGrid_TopDark")
    mat_gray = editor_asset_sub.load_asset("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray.MI_PrototypeGrid_Gray")

    # Campfire Point Light
    fire_light = editor_actor_sub.spawn_actor_from_class(
        unreal.PointLight,
        unreal.Vector(0, 0, 70),
        unreal.Rotator(0, 0, 0)
    )
    fire_light.set_actor_label("Forest_Campfire_Light")
    fl_comp = fire_light.get_component_by_class(unreal.PointLightComponent)
    if fl_comp:
        fl_comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        fl_comp.set_editor_property("intensity", 5000.0)
        fl_comp.set_editor_property("attenuation_radius", 1400.0)
        fl_comp.set_editor_property("use_temperature", True)
        fl_comp.set_editor_property("temperature", 2400.0)

    # Stone Circle
    for s_i in range(8):
        s_rad = (2 * math.pi / 8) * s_i
        sx = 180.0 * math.cos(s_rad)
        sy = 180.0 * math.sin(s_rad)
        stone = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(sx, sy, 20),
            unreal.Rotator(0, math.degrees(s_rad), 0)
        )
        stone.set_actor_label(f"Forest_CampfireStone_{s_i:02d}")
        s_sm = stone.get_component_by_class(unreal.StaticMeshComponent)
        if s_sm:
            s_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if chamfer_mesh:
                s_sm.set_static_mesh(chamfer_mesh)
            if mat_gray:
                s_sm.set_material(0, mat_gray)
            stone.set_actor_scale3d(unreal.Vector(0.5, 0.5, 0.4))

    # Log Benches
    for b_i, angle_deg in enumerate([45, 135, 225, 315]):
        b_rad = math.radians(angle_deg)
        bx = 350.0 * math.cos(b_rad)
        by = 350.0 * math.sin(b_rad)
        bench = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(bx, by, 30),
            unreal.Rotator(0, angle_deg + 90, 90)
        )
        bench.set_actor_label(f"Forest_Bench_{b_i:02d}")
        b_sm = bench.get_component_by_class(unreal.StaticMeshComponent)
        if b_sm:
            b_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if cyl_mesh:
                b_sm.set_static_mesh(cyl_mesh)
            if mat_dark:
                b_sm.set_material(0, mat_dark)
            bench.set_actor_scale3d(unreal.Vector(0.4, 0.4, 1.8))

    # 7. Position PlayerStart
    ps_actors = [a for a in editor_actor_sub.get_all_level_actors() if isinstance(a, unreal.PlayerStart)]
    if ps_actors:
        ps_actors[0].set_actor_location(unreal.Vector(-450, 0, 120), False, False)
        ps_actors[0].set_actor_rotation(unreal.Rotator(0, 0, 0), False)

    # 8. Save Level
    level_editor_sub.save_current_level()
    unreal.log("==================================================")
    unreal.log(f"[AGY] Lvl_Forest created successfully from Template_Default with perfect sky and saved to {target_map}!")
    unreal.log("==================================================")
    return True

if __name__ == "__main__":
    create_forest_level()
