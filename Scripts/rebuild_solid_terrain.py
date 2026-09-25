import os
import math
import struct
import unreal

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
GENERATED_DIR = os.path.join(SCRIPTS_DIR, "generated_assets")

def generate_solid_terrain_obj(filepath):
    """
    Generates a solid 3D sculpted landscape terrain with:
    1. Correct upward (+Z) normal winding on all surface triangles.
    2. Solid side skirts and flat bottom base (Z = -600) so it is a closed 3D solid mesh.
    """
    verts, uvs, norms, faces = [], [], [], []
    grid_size = 36
    world_size = 40000.0 # 400m x 400m
    step = world_size / grid_size
    base_z = -600.0

    # Top surface vertices
    top_grid = []
    for gi in range(grid_size + 1):
        row = []
        x = -world_size / 2.0 + gi * step
        for gj in range(grid_size + 1):
            y = -world_size / 2.0 + gj * step
            dist = math.sqrt(x * x + y * y)

            if dist < 4500.0:
                z = 0.0
            else:
                elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
                edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
                z = elevation + (edge_factor ** 2) * 1750.0

            idx = len(verts) + 1 # 1-based index
            verts.append((x, y, z))
            uvs.append((gi / grid_size * 25.0, gj / grid_size * 25.0))
            norms.append((0.0, 0.0, 1.0))
            row.append(idx)
        top_grid.append(row)

    # Top surface faces (Counter-Clockwise for upward normal +Z)
    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = top_grid[gi][gj]         # (x, y)
            p2 = top_grid[gi][gj + 1]     # (x, y+1)
            p3 = top_grid[gi + 1][gj + 1] # (x+1, y+1)
            p4 = top_grid[gi + 1][gj]     # (x+1, y)

            # Tri 1: p1 -> p3 -> p2 (normal +Z)
            faces.append((p1, p3, p2))
            # Tri 2: p1 -> p4 -> p3 (normal +Z)
            faces.append((p1, p4, p3))

    # Bottom surface vertices & faces for closed solid volume
    bot_grid = []
    for gi in range(grid_size + 1):
        row = []
        x = -world_size / 2.0 + gi * step
        for gj in range(grid_size + 1):
            y = -world_size / 2.0 + gj * step
            idx = len(verts) + 1
            verts.append((x, y, base_z))
            uvs.append((gi / grid_size * 5.0, gj / grid_size * 5.0))
            norms.append((0.0, 0.0, -1.0))
            row.append(idx)
        bot_grid.append(row)

    # Bottom faces (downward normal -Z)
    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = bot_grid[gi][gj]
            p2 = bot_grid[gi][gj + 1]
            p3 = bot_grid[gi + 1][gj + 1]
            p4 = bot_grid[gi + 1][gj]
            faces.append((p1, p2, p3))
            faces.append((p1, p3, p4))

    # Side wall skirts
    # Side 1: gi = 0 (x = -world_size/2, along gj)
    for gj in range(grid_size):
        t1, t2 = top_grid[0][gj], top_grid[0][gj + 1]
        b1, b2 = bot_grid[0][gj], bot_grid[0][gj + 1]
        faces.append((t1, b1, b2))
        faces.append((t1, b2, t2))

    # Side 2: gi = grid_size (x = +world_size/2, along gj)
    for gj in range(grid_size):
        t1, t2 = top_grid[grid_size][gj], top_grid[grid_size][gj + 1]
        b1, b2 = bot_grid[grid_size][gj], bot_grid[grid_size][gj + 1]
        faces.append((t1, b2, b1))
        faces.append((t1, t2, b2))

    # Side 3: gj = 0 (y = -world_size/2, along gi)
    for gi in range(grid_size):
        t1, t2 = top_grid[gi][0], top_grid[gi + 1][0]
        b1, b2 = bot_grid[gi][0], bot_grid[gi + 1][0]
        faces.append((t1, b2, b1))
        faces.append((t1, t2, b2))

    # Side 4: gj = grid_size (y = +world_size/2, along gi)
    for gi in range(grid_size):
        t1, t2 = top_grid[gi][grid_size], top_grid[gi + 1][grid_size]
        b1, b2 = bot_grid[gi][grid_size], bot_grid[gi + 1][grid_size]
        faces.append((t1, b1, b2))
        faces.append((t1, b2, t2))

    with open(filepath, "w") as f:
        f.write("# Solid Closed Landscape Mesh\n")
        f.write("o SM_ForestLandscape\n")
        for v in verts:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        for vt in uvs:
            f.write(f"vt {vt[0]:.4f} {vt[1]:.4f}\n")
        for vn in norms:
            f.write(f"vn {vn[0]:.4f} {vn[1]:.4f} {vn[2]:.4f}\n")
        f.write("usemtl M_Forest_Grass\n")
        for face in faces:
            f.write(f"f {face[0]}/{face[0]}/{face[0]} {face[1]}/{face[1]}/{face[1]} {face[2]}/{face[2]}/{face[2]}\n")

def rebuild_terrain_and_level():
    p_terrain = os.path.join(GENERATED_DIR, "SM_ForestLandscape.obj")
    generate_solid_terrain_obj(p_terrain)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # Re-import SM_ForestLandscape
    task = unreal.AssetImportTask()
    task.filename = p_terrain
    task.destination_path = "/Game/Forest/Meshes"
    task.destination_name = "SM_ForestLandscape"
    task.replace_existing = True
    task.automated = True
    task.save = True
    asset_tools.import_asset_tasks([task])

    # Configure mesh collision & Nanite
    mesh_terrain = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
    if mesh_terrain:
        nanite_settings = mesh_terrain.get_editor_property("nanite_settings")
        if nanite_settings:
            nanite_settings.set_editor_property("enabled", False)
            mesh_terrain.set_editor_property("nanite_settings", nanite_settings)

        body_setup = mesh_terrain.get_editor_property("body_setup")
        if body_setup:
            body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)

        mat_grass = editor_asset_sub.load_asset("/Game/Forest/Materials/M_Forest_Grass.M_Forest_Grass")
        if mat_grass:
            mesh_terrain.set_material(0, mat_grass)

        editor_asset_sub.save_loaded_asset(mesh_terrain)
        unreal.log_warning("[AGY] SM_ForestLandscape re-imported as closed solid volume with upward normals and complex collision.")

    # Load level and update actors
    level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

    # Update terrain actor
    for actor in editor_actor_sub.get_all_level_actors():
        if "Terrain" in actor.get_actor_label():
            actor.set_actor_location(unreal.Vector(0, 0, 0), False, False)
            actor.set_actor_rotation(unreal.Rotator(0, 0, 0), False)
            t_sm = actor.get_component_by_class(unreal.StaticMeshComponent)
            if t_sm:
                t_sm.set_mobility(unreal.ComponentMobility.STATIC)
                if mesh_terrain:
                    t_sm.set_static_mesh(mesh_terrain)
                t_sm.set_collision_profile_name("BlockAll")
                t_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
                t_sm.set_editor_property("can_character_step_up_on", unreal.CanBeCharacterBase.ECB_YES)

        elif isinstance(actor, unreal.PlayerStart):
            # Position PlayerStart at (0, 0, 100) exactly above ground at Z=0
            actor.set_actor_location(unreal.Vector(0, 0, 100), False, False)
            actor.set_actor_rotation(unreal.Rotator(0, 0, 0), False)

    level_editor_sub.save_current_level()
    unreal.log_warning("==================================================")
    unreal.log_warning("[AGY] LEVEL AND SOLID TERRAIN COLLISION FULLY REBUILT & SAVED!")
    unreal.log_warning("==================================================")

if __name__ == "__main__":
    rebuild_terrain_and_level()
