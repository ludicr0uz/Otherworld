import os
import math

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
GENERATED_DIR = os.path.join(SCRIPTS_DIR, "generated_assets")
os.makedirs(GENERATED_DIR, exist_ok=True)

def generate_clean_terrain_obj(filepath):
    """
    Generates a solid 3D sculpted landscape terrain with:
    1. Clean normalized UVs [0.0, 1.0] across the 400m x 400m landscape.
    2. Proper smoothed upward normals on top surface.
    3. Solid skirt and base for collision.
    """
    verts, uvs, norms, faces = [], [], [], []
    grid_size = 64 # High resolution 64x64 grid (4,096 quads)
    world_size = 40000.0 # 400m x 400m
    step = world_size / grid_size
    base_z = -800.0

    def elev(x, y):
        dist = math.sqrt(x * x + y * y)
        if dist < 4500.0:
            return 0.0
        else:
            elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
            edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
            return elevation + (edge_factor ** 2) * 1750.0

    # Top surface vertices
    top_grid = []
    for gi in range(grid_size + 1):
        row = []
        x = -world_size / 2.0 + gi * step
        u = gi / grid_size
        for gj in range(grid_size + 1):
            y = -world_size / 2.0 + gj * step
            v = gj / grid_size
            z = elev(x, y)

            # Calculate normal from gradient
            eps = 50.0
            dz_dx = (elev(x + eps, y) - elev(x - eps, y)) / (2.0 * eps)
            dz_dy = (elev(x, y + eps) - elev(x, y - eps)) / (2.0 * eps)
            nx, ny, nz = -dz_dx, -dz_dy, 1.0
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
            nx, ny, nz = nx / nlen, ny / nlen, nz / nlen

            idx = len(verts) + 1 # 1-based
            verts.append((x, y, z))
            uvs.append((u, v))
            norms.append((nx, ny, nz))
            row.append(idx)
        top_grid.append(row)

    # Top surface faces
    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = top_grid[gi][gj]
            p2 = top_grid[gi][gj + 1]
            p3 = top_grid[gi + 1][gj + 1]
            p4 = top_grid[gi + 1][gj]
            faces.append((p1, p3, p2))
            faces.append((p1, p4, p3))

    # Bottom surface
    bot_grid = []
    for gi in range(grid_size + 1):
        row = []
        x = -world_size / 2.0 + gi * step
        u = gi / grid_size
        for gj in range(grid_size + 1):
            y = -world_size / 2.0 + gj * step
            v = gj / grid_size
            idx = len(verts) + 1
            verts.append((x, y, base_z))
            uvs.append((u, v))
            norms.append((0.0, 0.0, -1.0))
            row.append(idx)
        bot_grid.append(row)

    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = bot_grid[gi][gj]
            p2 = bot_grid[gi][gj + 1]
            p3 = bot_grid[gi + 1][gj + 1]
            p4 = bot_grid[gi + 1][gj]
            faces.append((p1, p2, p3))
            faces.append((p1, p3, p4))

    # Side wall skirts
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

    with open(filepath, "w") as f:
        f.write("# Clean UV Landscape Mesh\n")
        f.write("o SM_ForestLandscape\n")
        for v in verts:
            f.write(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}\n")
        for vt in uvs:
            f.write(f"vt {vt[0]:.5f} {vt[1]:.5f}\n")
        for vn in norms:
            f.write(f"vn {vn[0]:.4f} {vn[1]:.4f} {vn[2]:.4f}\n")
        f.write("usemtl M_Forest_Ground_PBR\n")
        for face in faces:
            f.write(f"f {face[0]}/{face[0]}/{face[0]} {face[1]}/{face[1]}/{face[1]} {face[2]}/{face[2]}/{face[2]}\n")

obj_file = os.path.join(GENERATED_DIR, "SM_ForestLandscape.obj")
generate_clean_terrain_obj(obj_file)
print(f"Generated clean terrain OBJ: {obj_file} ({os.path.getsize(obj_file)} bytes)")
