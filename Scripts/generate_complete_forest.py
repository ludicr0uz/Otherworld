"""
Otherworld - Complete 3D Forest Biome Generator
Generates realistic 3D tree models (Pine & Broadleaf), rocks, terrain, bushes,
seamless textures, materials, and populates Lvl_Forest automatically.
"""
import os
import math
import random
import struct

# Directory paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
GENERATED_DIR = os.path.join(SCRIPTS_DIR, "generated_assets")
os.makedirs(GENERATED_DIR, exist_ok=True)

# -------------------------------------------------------------
# 1. Procedural 3D OBJ Geometry Generation (Multi-material sections)
# -------------------------------------------------------------

def write_obj_mesh(filepath, obj_name, sections):
    """
    Writes an OBJ file as a single named object with multiple material sections.
    """
    with open(filepath, "w") as f:
        f.write(f"# Object: {obj_name}\n")
        f.write(f"o {obj_name}\n")

        # 1. Write all vertices, uvs, normals
        for s in sections:
            for v in s["vertices"]:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            for vt in s["uvs"]:
                f.write(f"vt {vt[0]:.4f} {vt[1]:.4f}\n")
            for vn in s["normals"]:
                f.write(f"vn {vn[0]:.4f} {vn[1]:.4f} {vn[2]:.4f}\n")

        # 2. Write faces per material section
        running_v = 0
        running_vt = 0
        running_vn = 0
        for s in sections:
            f.write(f"usemtl {s['material']}\n")
            for face in s["faces"]:
                v1 = face[0] + running_v
                v2 = face[1] + running_v
                v3 = face[2] + running_v
                vt1 = face[0] + running_vt
                vt2 = face[1] + running_vt
                vt3 = face[2] + running_vt
                vn1 = face[0] + running_vn
                vn2 = face[1] + running_vn
                vn3 = face[2] + running_vn
                f.write(f"f {v1}/{vt1}/{vn1} {v2}/{vt2}/{vn2} {v3}/{vt3}/{vn3}\n")
            running_v += len(s["vertices"])
            running_vt += len(s["uvs"])
            running_vn += len(s["normals"])

def generate_pine_tree_obj(filepath):
    """Generates a Pine Tree 3D mesh (Trunk section + 4 Needle Tiers section)."""
    # 1. Trunk
    trunk_verts, trunk_uvs, trunk_norms, trunk_faces = [], [], [], []
    segs = 12
    height = 1400.0
    r_bot = 48.0
    r_top = 16.0

    for i in range(segs):
        ang = (2 * math.pi / segs) * i
        trunk_verts.append((r_bot * math.cos(ang), r_bot * math.sin(ang), 0.0))
        trunk_uvs.append((i / segs, 0.0))
        trunk_norms.append((math.cos(ang), math.sin(ang), 0.0))

    for i in range(segs):
        ang = (2 * math.pi / segs) * i
        trunk_verts.append((r_top * math.cos(ang), r_top * math.sin(ang), height))
        trunk_uvs.append((i / segs, 5.0))
        trunk_norms.append((math.cos(ang), math.sin(ang), 0.0))

    for i in range(segs):
        next_i = (i + 1) % segs
        b1, b2 = i + 1, next_i + 1
        t1, t2 = segs + i + 1, segs + next_i + 1
        trunk_faces.append((b1, b2, t2))
        trunk_faces.append((b1, t2, t1))

    # 2. Foliage (4 Tiers)
    fol_verts, fol_uvs, fol_norms, fol_faces = [], [], [], []
    tiers = [
        {"z_base": 320.0, "radius": 340.0, "height": 480.0, "segs": 14},
        {"z_base": 620.0, "radius": 280.0, "height": 450.0, "segs": 12},
        {"z_base": 920.0, "radius": 200.0, "height": 420.0, "segs": 10},
        {"z_base": 1220.0, "radius": 130.0, "height": 380.0, "segs": 8},
    ]

    for tier in tiers:
        v_offset = len(fol_verts)
        z_b = tier["z_base"]
        r = tier["radius"]
        h = tier["height"]
        t_segs = tier["segs"]

        # Base skirt circle with organic wobble
        for i in range(t_segs):
            ang = (2 * math.pi / t_segs) * i
            wobble = 1.0 + 0.12 * math.sin(i * 3.5)
            vx = r * math.cos(ang) * wobble
            vy = r * math.sin(ang) * wobble
            vz = z_b + 25.0 * math.cos(i * 2.0)
            fol_verts.append((vx, vy, vz))
            fol_uvs.append((i / t_segs, 0.0))
            fol_norms.append((math.cos(ang) * 0.7, math.sin(ang) * 0.7, 0.5))

        # Peak vertex
        peak_idx = len(fol_verts) + 1
        fol_verts.append((0.0, 0.0, z_b + h))
        fol_uvs.append((0.5, 1.0))
        fol_norms.append((0.0, 0.0, 1.0))

        # Cone side faces
        for i in range(t_segs):
            next_i = (i + 1) % t_segs
            p1 = v_offset + i + 1
            p2 = v_offset + next_i + 1
            fol_faces.append((p1, p2, peak_idx))

        # Underside skirt face
        center_idx = len(fol_verts) + 1
        fol_verts.append((0.0, 0.0, z_b + 60.0))
        fol_uvs.append((0.5, 0.5))
        fol_norms.append((0.0, 0.0, -1.0))
        for i in range(t_segs):
            next_i = (i + 1) % t_segs
            p1 = v_offset + i + 1
            p2 = v_offset + next_i + 1
            fol_faces.append((p2, p1, center_idx))

    sections = [
        {"material": "M_Forest_Bark", "vertices": trunk_verts, "uvs": trunk_uvs, "normals": trunk_norms, "faces": trunk_faces},
        {"material": "M_Forest_Pine", "vertices": fol_verts, "uvs": fol_uvs, "normals": fol_norms, "faces": fol_faces}
    ]
    write_obj_mesh(filepath, "SM_PineTree_01", sections)

def generate_broadleaf_tree_obj(filepath):
    """Generates an Oak / Birch style tree with trunk and canopy dome clusters."""
    # 1. Trunk
    trunk_verts, trunk_uvs, trunk_norms, trunk_faces = [], [], [], []
    segs = 12
    height = 750.0
    r_bot = 60.0
    r_top = 38.0

    for i in range(segs):
        ang = (2 * math.pi / segs) * i
        trunk_verts.append((r_bot * math.cos(ang), r_bot * math.sin(ang), 0.0))
        trunk_uvs.append((i / segs, 0.0))
        trunk_norms.append((math.cos(ang), math.sin(ang), 0.0))

    for i in range(segs):
        ang = (2 * math.pi / segs) * i
        bend_x = 25.0 * math.sin(i * 0.5)
        trunk_verts.append((r_top * math.cos(ang) + bend_x, r_top * math.sin(ang), height))
        trunk_uvs.append((i / segs, 3.0))
        trunk_norms.append((math.cos(ang), math.sin(ang), 0.0))

    for i in range(segs):
        next_i = (i + 1) % segs
        b1, b2 = i + 1, next_i + 1
        t1, t2 = segs + i + 1, segs + next_i + 1
        trunk_faces.append((b1, b2, t2))
        trunk_faces.append((b1, t2, t1))

    # 2. Canopy Foliage Clusters (3 overlapping organic domes)
    fol_verts, fol_uvs, fol_norms, fol_faces = [], [], [], []
    sphere_clusters = [
        {"center": (0, 0, 1000.0), "radius": 360.0},
        {"center": (-150.0, 120.0, 850.0), "radius": 280.0},
        {"center": (160.0, -110.0, 900.0), "radius": 300.0},
    ]

    for cluster in sphere_clusters:
        v_offset = len(fol_verts)
        cx, cy, cz = cluster["center"]
        rad = cluster["radius"]
        lat_count = 7
        lon_count = 11

        for lat in range(lat_count + 1):
            theta = (math.pi / lat_count) * lat
            sin_t = math.sin(theta)
            cos_t = math.cos(theta)

            for lon in range(lon_count):
                phi = (2 * math.pi / lon_count) * lon
                nx = sin_t * math.cos(phi)
                ny = sin_t * math.sin(phi)
                nz = cos_t

                bump = 1.0 + 0.15 * math.sin(lat * 3 + lon * 2)
                vx = cx + rad * nx * bump
                vy = cy + rad * ny * bump
                vz = cz + rad * nz * bump

                fol_verts.append((vx, vy, vz))
                fol_uvs.append((lon / lon_count * 2.0, lat / lat_count * 2.0))
                fol_norms.append((nx, ny, nz))

        for lat in range(lat_count):
            for lon in range(lon_count):
                next_lon = (lon + 1) % lon_count
                p1 = v_offset + lat * lon_count + lon + 1
                p2 = v_offset + lat * lon_count + next_lon + 1
                p3 = v_offset + (lat + 1) * lon_count + next_lon + 1
                p4 = v_offset + (lat + 1) * lon_count + lon + 1
                fol_faces.append((p1, p2, p3))
                fol_faces.append((p1, p3, p4))

    sections = [
        {"material": "M_Forest_Bark", "vertices": trunk_verts, "uvs": trunk_uvs, "normals": trunk_norms, "faces": trunk_faces},
        {"material": "M_Forest_Grass", "vertices": fol_verts, "uvs": fol_uvs, "normals": fol_norms, "faces": fol_faces}
    ]
    write_obj_mesh(filepath, "SM_BroadleafTree_01", sections)

def generate_rock_obj(filepath):
    """Generates an organic faceted rock boulder."""
    verts, uvs, norms, faces = [], [], [], []
    lat_count = 6
    lon_count = 8
    rx, ry, rz = 200.0, 160.0, 120.0

    random.seed(101)
    for lat in range(lat_count + 1):
        theta = (math.pi / lat_count) * lat
        sin_t = math.sin(theta)
        cos_t = math.cos(theta)

        for lon in range(lon_count):
            phi = (2 * math.pi / lon_count) * lon
            nx = sin_t * math.cos(phi)
            ny = sin_t * math.sin(phi)
            nz = cos_t

            noise = random.uniform(0.75, 1.25)
            vx = rx * nx * noise
            vy = ry * ny * noise
            vz = rz * nz * noise if nz >= 0 else rz * nz * 0.35

            verts.append((vx, vy, vz))
            uvs.append((lon / lon_count, lat / lat_count))
            norms.append((nx, ny, nz))

    for lat in range(lat_count):
        for lon in range(lon_count):
            next_lon = (lon + 1) % lon_count
            p1 = lat * lon_count + lon + 1
            p2 = lat * lon_count + next_lon + 1
            p3 = (lat + 1) * lon_count + next_lon + 1
            p4 = (lat + 1) * lon_count + lon + 1
            faces.append((p1, p2, p3))
            faces.append((p1, p3, p4))

    sections = [
        {"material": "M_Forest_Rock", "vertices": verts, "uvs": uvs, "normals": norms, "faces": faces}
    ]
    write_obj_mesh(filepath, "SM_ForestRock_01", sections)

def generate_terrain_landscape_obj(filepath):
    """Generates a solid 3D sculpted organic terrain mesh with upward normal winding and closed base."""
    verts, uvs, norms, faces = [], [], [], []
    grid_size = 36
    world_size = 40000.0
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

            idx = len(verts) + 1
            verts.append((x, y, z))
            uvs.append((gi / grid_size * 25.0, gj / grid_size * 25.0))
            norms.append((0.0, 0.0, 1.0))
            row.append(idx)
        top_grid.append(row)

    # Top surface faces (Counter-Clockwise for upward normal +Z)
    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = top_grid[gi][gj]
            p2 = top_grid[gi][gj + 1]
            p3 = top_grid[gi + 1][gj + 1]
            p4 = top_grid[gi + 1][gj]
            faces.append((p1, p3, p2))
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

    # Bottom faces
    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = bot_grid[gi][gj]
            p2 = bot_grid[gi][gj + 1]
            p3 = bot_grid[gi + 1][gj + 1]
            p4 = bot_grid[gi + 1][gj]
            faces.append((p1, p2, p3))
            faces.append((p1, p3, p4))

    # Side walls
    for gj in range(grid_size):
        t1, t2 = top_grid[0][gj], top_grid[0][gj + 1]
        b1, b2 = bot_grid[0][gj], bot_grid[0][gj + 1]
        faces.append((t1, b1, b2))
        faces.append((t1, b2, t2))

    for gj in range(grid_size):
        t1, t2 = top_grid[grid_size][gj], top_grid[grid_size][gj + 1]
        b1, b2 = bot_grid[grid_size][gj], bot_grid[grid_size][gj + 1]
        faces.append((t1, b2, b1))
        faces.append((t1, t2, b2))

    for gi in range(grid_size):
        t1, t2 = top_grid[gi][0], top_grid[gi + 1][0]
        b1, b2 = bot_grid[gi][0], bot_grid[gi + 1][0]
        faces.append((t1, b2, b1))
        faces.append((t1, t2, b2))

    for gi in range(grid_size):
        t1, t2 = top_grid[gi][grid_size], top_grid[gi + 1][grid_size]
        b1, b2 = bot_grid[gi][grid_size], bot_grid[gi + 1][grid_size]
        faces.append((t1, b1, b2))
        faces.append((t1, b2, t2))

    sections = [
        {"material": "M_Forest_Grass", "vertices": verts, "uvs": uvs, "normals": norms, "faces": faces}
    ]
    write_obj_mesh(filepath, "SM_ForestLandscape", sections)

def generate_bush_obj(filepath):
    """Generates a small forest undergrowth shrub/bush."""
    verts, uvs, norms, faces = [], [], [], []
    sphere_clusters = [
        {"center": (0, 0, 70.0), "radius": 90.0},
        {"center": (-40.0, 30.0, 50.0), "radius": 70.0},
        {"center": (40.0, -25.0, 55.0), "radius": 75.0},
    ]
    for cluster in sphere_clusters:
        v_offset = len(verts)
        cx, cy, cz = cluster["center"]
        rad = cluster["radius"]
        lat_count = 5
        lon_count = 8

        for lat in range(lat_count + 1):
            theta = (math.pi / lat_count) * lat
            sin_t = math.sin(theta)
            cos_t = math.cos(theta)
            for lon in range(lon_count):
                phi = (2 * math.pi / lon_count) * lon
                nx = sin_t * math.cos(phi)
                ny = sin_t * math.sin(phi)
                nz = cos_t
                bump = 1.0 + 0.2 * math.sin(lat * 2 + lon * 3)
                vx = cx + rad * nx * bump
                vy = cy + rad * ny * bump
                vz = max(0.0, cz + rad * nz * bump)
                verts.append((vx, vy, vz))
                uvs.append((lon / lon_count, lat / lat_count))
                norms.append((nx, ny, nz))

        for lat in range(lat_count):
            for lon in range(lon_count):
                next_lon = (lon + 1) % lon_count
                p1 = v_offset + lat * lon_count + lon + 1
                p2 = v_offset + lat * lon_count + next_lon + 1
                p3 = v_offset + (lat + 1) * lon_count + next_lon + 1
                p4 = v_offset + (lat + 1) * lon_count + lon + 1
                faces.append((p1, p2, p3))
                faces.append((p1, p3, p4))

    sections = [
        {"material": "M_Forest_Grass", "vertices": verts, "uvs": uvs, "normals": norms, "faces": faces}
    ]
    write_obj_mesh(filepath, "SM_ForestBush_01", sections)

# -------------------------------------------------------------
# 2. Procedural Texture BMP Generation (Pure Python)
# -------------------------------------------------------------

def write_bmp(filepath, width, height, rgb_data):
    """Writes an uncompressed 24-bit RGB BMP file."""
    row_padding = (4 - (width * 3) % 4) % 4
    image_size = (width * 3 + row_padding) * height
    file_size = 54 + image_size

    header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 54)
    dib = struct.pack('<IIIHHIIIIII', 40, width, height, 1, 24, 0, image_size, 2835, 2835, 0, 0)

    with open(filepath, 'wb') as f:
        f.write(header)
        f.write(dib)
        for y in reversed(range(height)):
            row = bytearray()
            for x in range(width):
                idx = (y * width + x) * 3
                r = rgb_data[idx]
                g = rgb_data[idx + 1]
                b = rgb_data[idx + 2]
                row.extend([b, g, r]) # BGR order
            row.extend(b'\x00' * row_padding)
            f.write(row)

def create_textures():
    """Generates procedural texture files for grass, bark, pine foliage, and stone."""
    w, h = 256, 256

    # 1. Grass Texture
    grass_data = []
    random.seed(42)
    for y in range(h):
        for x in range(w):
            noise = random.randint(-18, 18)
            r = max(0, min(255, 36 + noise // 2))
            g = max(0, min(255, 118 + noise))
            b = max(0, min(255, 28 + noise // 3))
            grass_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Forest_Grass_D.bmp"), w, h, grass_data)

    # 2. Bark Texture
    bark_data = []
    for y in range(h):
        for x in range(w):
            n = random.randint(-12, 12) + int(math.sin(x / 4.0) * 14)
            r = max(0, min(255, 72 + n))
            g = max(0, min(255, 45 + n // 2))
            b = max(0, min(255, 24 + n // 3))
            bark_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Forest_Bark_D.bmp"), w, h, bark_data)

    # 3. Pine Foliage Texture
    pine_data = []
    for y in range(h):
        for x in range(w):
            n = random.randint(-22, 22)
            r = max(0, min(255, 16 + n // 3))
            g = max(0, min(255, 72 + n))
            b = max(0, min(255, 22 + n // 2))
            pine_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Forest_Pine_D.bmp"), w, h, pine_data)

    # 4. Rock Texture
    rock_data = []
    for y in range(h):
        for x in range(w):
            n = random.randint(-20, 20)
            val = max(0, min(255, 115 + n))
            rock_data.extend([val, val, int(val * 0.96)])
    write_bmp(os.path.join(GENERATED_DIR, "T_Forest_Rock_D.bmp"), w, h, rock_data)

# -------------------------------------------------------------
# 3. Main Builder Function (Unreal Editor Python Execution)
# -------------------------------------------------------------

def build_complete_forest():
    print("[AGY] Step 1: Generating 3D Models & Textures on disk...")
    p_pine = os.path.join(GENERATED_DIR, "SM_PineTree_01.obj")
    p_oak = os.path.join(GENERATED_DIR, "SM_BroadleafTree_01.obj")
    p_rock = os.path.join(GENERATED_DIR, "SM_ForestRock_01.obj")
    p_terrain = os.path.join(GENERATED_DIR, "SM_ForestLandscape.obj")
    p_bush = os.path.join(GENERATED_DIR, "SM_ForestBush_01.obj")

    generate_pine_tree_obj(p_pine)
    generate_broadleaf_tree_obj(p_oak)
    generate_rock_obj(p_rock)
    generate_terrain_landscape_obj(p_terrain)
    generate_bush_obj(p_bush)
    create_textures()

    # If running inside Unreal Engine
    try:
        import unreal
    except ImportError:
        print("[AGY] Assets generated on disk. Run via UnrealEditor-Cmd to import into project.")
        return True

    unreal.log("==================================================")
    unreal.log("[AGY] Step 2: Importing Textures and Creating Materials...")
    unreal.log("==================================================")

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # Clean old invalid meshes if any
    for old_name in ["Trunk", "Foliage"]:
        old_p = f"/Game/Forest/Meshes/{old_name}"
        if editor_asset_sub.does_asset_exist(old_p):
            editor_asset_sub.delete_asset(old_p)

    # Import Textures (.bmp)
    tex_configs = [
        ("T_Forest_Grass_D.bmp", "T_Forest_Grass_D"),
        ("T_Forest_Bark_D.bmp", "T_Forest_Bark_D"),
        ("T_Forest_Pine_D.bmp", "T_Forest_Pine_D"),
        ("T_Forest_Rock_D.bmp", "T_Forest_Rock_D")
    ]
    for t_file, t_name in tex_configs:
        t_path = os.path.join(GENERATED_DIR, t_file)
        task = unreal.AssetImportTask()
        task.filename = t_path
        task.destination_path = "/Game/Forest/Textures"
        task.destination_name = t_name
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])
        unreal.log(f"[AGY] Imported Texture: /Game/Forest/Textures/{t_name}")

    # Create & Compile Forest Materials
    mat_configs = [
        ("M_Forest_Grass", "/Game/Forest/Textures/T_Forest_Grass_D.T_Forest_Grass_D", unreal.LinearColor(0.14, 0.45, 0.11, 1.0), 0.85),
        ("M_Forest_Bark", "/Game/Forest/Textures/T_Forest_Bark_D.T_Forest_Bark_D", unreal.LinearColor(0.28, 0.18, 0.10, 1.0), 0.90),
        ("M_Forest_Pine", "/Game/Forest/Textures/T_Forest_Pine_D.T_Forest_Pine_D", unreal.LinearColor(0.06, 0.28, 0.10, 1.0), 0.75),
        ("M_Forest_Rock", "/Game/Forest/Textures/T_Forest_Rock_D.T_Forest_Rock_D", unreal.LinearColor(0.42, 0.42, 0.44, 1.0), 0.70),
    ]

    materials_map = {}
    for mat_name, tex_asset_path, fallback_color, roughness in mat_configs:
        mat_path = f"/Game/Forest/Materials/{mat_name}"
        if editor_asset_sub.does_asset_exist(mat_path):
            editor_asset_sub.delete_asset(mat_path)

        mat_factory = unreal.MaterialFactoryNew()
        mat = asset_tools.create_asset(mat_name, "/Game/Forest/Materials", unreal.Material, mat_factory)
        if mat and hasattr(unreal, "MaterialEditingLibrary"):
            mel = unreal.MaterialEditingLibrary
            tex_asset = editor_asset_sub.load_asset(tex_asset_path)
            if tex_asset:
                tex_node = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -350, 0)
                tex_node.set_editor_property("texture", tex_asset)
                mel.connect_material_property(tex_node, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
            else:
                col_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -350, 0)
                col_node.set_editor_property("constant", fallback_color)
                mel.connect_material_property(col_node, "", unreal.MaterialProperty.MP_BASE_COLOR)

            r_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -350, 150)
            r_node.set_editor_property("r", roughness)
            mel.connect_material_property(r_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

            mel.recompile_material(mat)
            editor_asset_sub.save_asset(mat_path)
            materials_map[mat_name] = mat
            unreal.log(f"[AGY] Created & Compiled Material: {mat_path}")

    # Import Meshes
    unreal.log("==================================================")
    unreal.log("[AGY] Step 3: Importing 3D Meshes into Unreal...")
    unreal.log("==================================================")
    mesh_files = [
        (p_pine, "SM_PineTree_01"),
        (p_oak, "SM_BroadleafTree_01"),
        (p_rock, "SM_ForestRock_01"),
        (p_terrain, "SM_ForestLandscape"),
        (p_bush, "SM_ForestBush_01")
    ]
    for m_path, m_name in mesh_files:
        task = unreal.AssetImportTask()
        task.filename = m_path
        task.destination_path = "/Game/Forest/Meshes"
        task.destination_name = m_name
        task.replace_existing = True
        task.automated = True
        task.save = True
        asset_tools.import_asset_tasks([task])
        unreal.log(f"[AGY] Imported Mesh: /Game/Forest/Meshes/{m_name}")

    # Load Static Meshes
    mesh_pine = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_PineTree_01.SM_PineTree_01")
    mesh_oak = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_BroadleafTree_01.SM_BroadleafTree_01")
    mesh_rock = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestRock_01.SM_ForestRock_01")
    mesh_terrain = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")
    mesh_bush = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestBush_01.SM_ForestBush_01")

    all_meshes = [mesh_pine, mesh_oak, mesh_rock, mesh_terrain, mesh_bush]
    for m in all_meshes:
        if m:
            body_setup = m.get_editor_property("body_setup")
            if body_setup:
                body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            editor_asset_sub.save_loaded_asset(m)

    # Assign Materials to Meshes
    mat_grass = materials_map.get("M_Forest_Grass")
    mat_bark = materials_map.get("M_Forest_Bark")
    mat_pine = materials_map.get("M_Forest_Pine")
    mat_rock = materials_map.get("M_Forest_Rock")

    if mesh_pine:
        mesh_pine.set_material(0, mat_bark)
        mesh_pine.set_material(1, mat_pine)
        editor_asset_sub.save_loaded_asset(mesh_pine)
    if mesh_oak:
        mesh_oak.set_material(0, mat_bark)
        mesh_oak.set_material(1, mat_grass)
        editor_asset_sub.save_loaded_asset(mesh_oak)
    if mesh_rock:
        mesh_rock.set_material(0, mat_rock)
        editor_asset_sub.save_loaded_asset(mesh_rock)
    if mesh_terrain:
        mesh_terrain.set_material(0, mat_grass)
        editor_asset_sub.save_loaded_asset(mesh_terrain)
    if mesh_bush:
        mesh_bush.set_material(0, mat_grass)
        editor_asset_sub.save_loaded_asset(mesh_bush)

    # -------------------------------------------------------------
    # Step 4: Build Level (Lvl_Forest)
    # -------------------------------------------------------------
    target_level = "/Game/Maps/Lvl_Forest"
    template_level = "/Engine/Maps/Templates/Template_Default"

    unreal.log(f"[AGY] Creating level {target_level} from template {template_level}...")
    if editor_asset_sub.does_asset_exist(target_level):
        editor_asset_sub.delete_asset(target_level)

    level_editor_sub.new_level_from_template(target_level, template_level)
    level_editor_sub.load_level(target_level)

    # Clean old template floor & gym props
    for actor in editor_actor_sub.get_all_level_actors():
        label = actor.get_actor_label()
        if any(w in label for w in ["Floor", "SM_Template_Map_Floor", "Ramp", "Cylinder", "Chamfer"]):
            editor_actor_sub.destroy_actor(actor)

    # 1. Spawn Sculpted Terrain Landscape
    terrain_actor = editor_actor_sub.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(0, 0, 0),
        unreal.Rotator(0, 0, 0)
    )
    terrain_actor.set_actor_label("Forest_Terrain_Landscape")
    t_sm = terrain_actor.get_component_by_class(unreal.StaticMeshComponent)
    if t_sm:
        t_sm.set_mobility(unreal.ComponentMobility.STATIC)
        if mesh_terrain:
            t_sm.set_static_mesh(mesh_terrain)
        if mat_grass:
            t_sm.set_material(0, mat_grass)
        t_sm.set_collision_profile_name("BlockAll")
        t_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 2. Populate 140+ 3D Trees
    unreal.log("[AGY] Populating 140+ 3D Trees across forest biome...")
    random.seed(2026)
    num_trees = 140
    tree_count = 0

    for i in range(num_trees):
        r = random.uniform(850.0, 14500.0) # Central clearing free
        theta = random.uniform(0, 2 * math.pi)
        tx = r * math.cos(theta)
        ty = r * math.sin(theta)

        dist = math.sqrt(tx * tx + ty * ty)
        if dist < 4500.0:
            tz = 0.0
        else:
            elevation = math.sin(tx / 3200.0) * math.cos(ty / 3200.0) * 380.0
            edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
            tz = elevation + (edge_factor ** 2) * 1750.0

        tree_count += 1
        scale_var = random.uniform(0.8, 1.4)
        rot_yaw = random.uniform(0, 360)
        tree_mesh = mesh_pine if random.random() < 0.65 else mesh_oak

        tree = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(tx, ty, tz - 15),
            unreal.Rotator(0.0, rot_yaw, 0.0)
        )
        tree.set_actor_label(f"Forest_Tree_{tree_count:03d}")
        tree_sm = tree.get_component_by_class(unreal.StaticMeshComponent)
        if tree_sm:
            tree_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if tree_mesh:
                tree_sm.set_static_mesh(tree_mesh)
            tree.set_actor_scale3d(unreal.Vector(scale_var, scale_var, scale_var))
            tree_sm.set_collision_profile_name("BlockAll")
            tree_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 3. Populate 45 Rock Boulders
    unreal.log("[AGY] Populating Rock Boulders...")
    for r_i in range(45):
        r_dist = random.uniform(1000.0, 13000.0)
        r_theta = random.uniform(0, 2 * math.pi)
        rx = r_dist * math.cos(r_theta)
        ry = r_dist * math.sin(r_theta)

        if r_dist < 4500.0:
            rz = 0.0
        else:
            elevation = math.sin(rx / 3200.0) * math.cos(ry / 3200.0) * 380.0
            edge_factor = max(0.0, (r_dist - 8000.0) / 9500.0)
            rz = elevation + (edge_factor ** 2) * 1750.0

        r_scale = random.uniform(1.2, 3.2)
        rock = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(rx, ry, rz + 10),
            unreal.Rotator(random.uniform(-8, 8), random.uniform(0, 360), random.uniform(-8, 8))
        )
        rock.set_actor_label(f"Forest_RockBoulder_{r_i:02d}")
        r_sm = rock.get_component_by_class(unreal.StaticMeshComponent)
        if r_sm:
            r_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if mesh_rock:
                r_sm.set_static_mesh(mesh_rock)
            rock.set_actor_scale3d(unreal.Vector(r_scale, r_scale, r_scale))
            r_sm.set_collision_profile_name("BlockAll")
            r_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 4. Populate 60 Undergrowth Shrub Bushes
    unreal.log("[AGY] Populating Forest Undergrowth Bushes...")
    for b_i in range(60):
        b_dist = random.uniform(600.0, 12000.0)
        b_theta = random.uniform(0, 2 * math.pi)
        bx = b_dist * math.cos(b_theta)
        by = b_dist * math.sin(b_theta)

        if b_dist < 4500.0:
            bz = 0.0
        else:
            elevation = math.sin(bx / 3200.0) * math.cos(by / 3200.0) * 380.0
            edge_factor = max(0.0, (b_dist - 8000.0) / 9500.0)
            bz = elevation + (edge_factor ** 2) * 1750.0

        b_scale = random.uniform(1.0, 2.2)
        bush = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(bx, by, bz),
            unreal.Rotator(0, random.uniform(0, 360), 0)
        )
        bush.set_actor_label(f"Forest_Bush_{b_i:02d}")
        b_sm = bush.get_component_by_class(unreal.StaticMeshComponent)
        if b_sm:
            b_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if mesh_bush:
                b_sm.set_static_mesh(mesh_bush)
            bush.set_actor_scale3d(unreal.Vector(b_scale, b_scale, b_scale))
            b_sm.set_collision_profile_name("BlockAll")

    # 5. Set WorldSettings GameMode to BP_ThirdPersonGameMode
    for actor in editor_actor_sub.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            gm = editor_asset_sub.load_asset("/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C")
            if gm:
                actor.set_editor_property("default_game_mode", gm)
            break

    # 6. Position PlayerStart in central clearing
    ps_actors = [a for a in editor_actor_sub.get_all_level_actors() if isinstance(a, unreal.PlayerStart)]
    if ps_actors:
        ps_actors[0].set_actor_location(unreal.Vector(0, 0, 100), False, False)
        ps_actors[0].set_actor_rotation(unreal.Rotator(0, 0, 0), False)

    # 7. Save Current Level
    level_editor_sub.save_current_level()
    unreal.log("==================================================")
    unreal.log(f"[AGY] COMPLETE 3D FOREST LEVEL GENERATED & SAVED TO {target_level}!")
    unreal.log("==================================================")
    return True

if __name__ == "__main__":
    build_complete_forest()
