import math
import random
import unreal

editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

def get_terrain_elevation(x, y):
    """Calculates exact mathematical Z elevation of the terrain at (x, y)."""
    dist = math.sqrt(x * x + y * y)
    if dist < 4500.0:
        return 0.0
    else:
        elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
        edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
        return elevation + (edge_factor ** 2) * 1750.0

random.seed(42)

all_actors = editor_actor_sub.get_all_level_actors()
tree_count = 0
rock_count = 0
bush_count = 0

for actor in all_actors:
    label = actor.get_actor_label()

    # 1. Trees: 100% Vertical (Pitch = 0, Roll = 0, Yaw = random)
    if "Tree" in label:
        loc = actor.get_actor_location()
        tz = get_terrain_elevation(loc.x, loc.y)
        # Plant trunk base 15 units into the ground
        actor.set_actor_location(unreal.Vector(loc.x, loc.y, tz - 15.0), False, False)
        yaw = random.uniform(0.0, 360.0)
        actor.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0), False)
        tree_count += 1

    # 2. Rock Boulders
    elif "Rock" in label:
        loc = actor.get_actor_location()
        rz = get_terrain_elevation(loc.x, loc.y)
        actor.set_actor_location(unreal.Vector(loc.x, loc.y, rz - 10.0), False, False)
        actor.set_actor_rotation(unreal.Rotator(
            pitch=random.uniform(-4.0, 4.0),
            yaw=random.uniform(0.0, 360.0),
            roll=random.uniform(-4.0, 4.0)
        ), False)
        rock_count += 1

    # 3. Bushes
    elif "Bush" in label:
        loc = actor.get_actor_location()
        bz = get_terrain_elevation(loc.x, loc.y)
        actor.set_actor_location(unreal.Vector(loc.x, loc.y, bz), False, False)
        actor.set_actor_rotation(unreal.Rotator(
            pitch=0.0,
            yaw=random.uniform(0.0, 360.0),
            roll=0.0
        ), False)
        bush_count += 1

level_editor_sub.save_current_level()
unreal.log_warning(f"[AGY] Fixed {tree_count} trees to be 100% vertically upright!")
unreal.log_warning(f"[AGY] Adjusted {rock_count} rocks and {bush_count} bushes.")
unreal.log_warning("[AGY] Lvl_Forest saved successfully!")
