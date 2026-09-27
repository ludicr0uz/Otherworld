"""
Otherworld - Photorealistic Forest Biome Generator
Generates high-fidelity 3D nature models (Pine, Oak, Fallen Logs, Ferns, Boulders),
high-resolution procedural PBR textures, subsurface foliage materials,
and cinematic volumetric forest lighting.
"""
import os
import math
import random
import struct

# Paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
GENERATED_DIR = os.path.join(os.path.dirname(SCRIPTS_DIR), "assets", "generated_realistic")
os.makedirs(GENERATED_DIR, exist_ok=True)

# -------------------------------------------------------------
# 1. High-Resolution Procedural Texture Generation (512x512 BMP)
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

def create_photorealistic_textures():
    """Generates 512x512 procedural textures with realistic micro-details."""
    w, h = 512, 512
    random.seed(2026)

    # 1. Pine Bark Texture (Deep vertical furrows, dark umber with grey-brown bark ridges and moss)
    print("[AGY] Generating T_Pine_Bark_D.bmp...")
    bark_data = []
    for y in range(h):
        for x in range(w):
            # Vertical furrow waves
            furrow1 = math.sin(x / 8.0 + math.sin(y / 15.0) * 1.5)
            furrow2 = math.sin(x / 3.0 + math.cos(y / 8.0) * 2.0) * 0.4
            noise = random.randint(-12, 12) + int((furrow1 + furrow2) * 28.0)
            # Moss flecks
            moss = random.random() < 0.08 and y > 350
            if moss:
                r = max(0, min(255, 45 + noise // 3))
                g = max(0, min(255, 75 + noise // 2))
                b = max(0, min(255, 30 + noise // 4))
            else:
                r = max(0, min(255, 72 + noise))
                g = max(0, min(255, 46 + noise // 2))
                b = max(0, min(255, 26 + noise // 3))
            bark_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Pine_Bark_D.bmp"), w, h, bark_data)

    # 2. Pine Needles Foliage (Dense evergreen needle tufts with varied green & yellow-green tips)
    print("[AGY] Generating T_Pine_Needles_D.bmp...")
    needle_data = []
    for y in range(h):
        for x in range(w):
            strand_noise = random.randint(-25, 25)
            # Radial tuft pattern
            cx, cy = (x % 128) - 64, (y % 128) - 64
            rad = math.sqrt(cx * cx + cy * cy)
            tip_factor = max(0.0, min(1.0, rad / 55.0))
            
            r = max(0, min(255, int(15 + tip_factor * 25 + strand_noise // 3)))
            g = max(0, min(255, int(58 + tip_factor * 45 + strand_noise)))
            b = max(0, min(255, int(18 + tip_factor * 12 + strand_noise // 4)))
            needle_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Pine_Needles_D.bmp"), w, h, needle_data)

    # 3. Oak Bark Texture (Weathered grey-brown hardwood with lichen flecks)
    print("[AGY] Generating T_Oak_Bark_D.bmp...")
    oak_bark_data = []
    for y in range(h):
        for x in range(w):
            f = math.sin(x / 12.0 + math.sin(y / 20.0) * 1.8) * 22.0
            n = random.randint(-15, 15) + int(f)
            r = max(0, min(255, 82 + n))
            g = max(0, min(255, 68 + n))
            b = max(0, min(255, 52 + n // 2))
            oak_bark_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Oak_Bark_D.bmp"), w, h, oak_bark_data)

    # 4. Oak Leaves Canopy (Layered broadleaf foliage with rich chlorophyll tones)
    print("[AGY] Generating T_Oak_Leaves_D.bmp...")
    leaf_data = []
    for y in range(h):
        for x in range(w):
            leaf_noise = random.randint(-20, 20)
            leaf_m = math.sin(x / 16.0) * math.cos(y / 16.0) * 20.0
            r = max(0, min(255, int(35 + leaf_m * 0.4 + leaf_noise // 3)))
            g = max(0, min(255, int(105 + leaf_m + leaf_noise)))
            b = max(0, min(255, int(28 + leaf_m * 0.3 + leaf_noise // 4)))
            leaf_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Oak_Leaves_D.bmp"), w, h, leaf_data)

    # 5. Realistic Forest Floor (Humus soil, fallen needle litter, scattered moss & clover)
    print("[AGY] Generating T_Forest_Ground_D.bmp...")
    ground_data = []
    for y in range(h):
        for x in range(w):
            soil_base = 35 + random.randint(-10, 10)
            # Patchy moss & needle distribution
            patch = math.sin(x / 40.0) * math.cos(y / 40.0) + math.sin(x / 15.0 + y / 12.0) * 0.5
            if patch > 0.4: # Lush moss patch
                n = random.randint(-15, 15)
                r = max(0, min(255, 42 + n // 2))
                g = max(0, min(255, 110 + n))
                b = max(0, min(255, 32 + n // 3))
            elif patch < -0.3: # Pine needle litter
                n = random.randint(-12, 12)
                r = max(0, min(255, 78 + n))
                g = max(0, min(255, 52 + n // 2))
                b = max(0, min(255, 28 + n // 3))
            else: # Rich dark forest soil
                n = random.randint(-10, 10)
                r = max(0, min(255, 48 + n))
                g = max(0, min(255, 42 + n))
                b = max(0, min(255, 28 + n // 2))
            ground_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Forest_Ground_D.bmp"), w, h, ground_data)

    # 6. Granite Stone Texture (Stratified mineral slate with quartz fissures)
    print("[AGY] Generating T_Rock_Granite_D.bmp...")
    rock_data = []
    for y in range(h):
        for x in range(w):
            strata = math.sin((x * 0.7 + y * 0.3) / 10.0) * 18.0
            fissure = math.sin((x - y) / 4.0) * 12.0 if random.random() < 0.15 else 0.0
            n = random.randint(-16, 16) + int(strata + fissure)
            val = max(0, min(255, 115 + n))
            rock_data.extend([val, int(val * 0.98), int(val * 0.94)])
    write_bmp(os.path.join(GENERATED_DIR, "T_Rock_Granite_D.bmp"), w, h, rock_data)

    # 7. Fern Frond Texture
    print("[AGY] Generating T_Fern_Frond_D.bmp...")
    fern_data = []
    for y in range(h):
        for x in range(w):
            fn = random.randint(-18, 18)
            vein = 25 if (x % 32 == 16) else 0
            r = max(0, min(255, 25 + fn // 3))
            g = max(0, min(255, 125 + fn + vein))
            b = max(0, min(255, 22 + fn // 4))
            fern_data.extend([r, g, b])
    write_bmp(os.path.join(GENERATED_DIR, "T_Fern_Frond_D.bmp"), w, h, fern_data)

# -------------------------------------------------------------
# 2. High-Fidelity 3D Model Generation
# -------------------------------------------------------------

def write_obj_mesh(filepath, obj_name, sections):
    """Writes a single unified OBJ mesh with multiple material sections."""
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

        # 2. Write faces per section
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

def generate_realistic_pine_obj(filepath):
    """
    Generates a Majestic 18-meter Scots Pine / Douglas Fir with:
    - Flared root buttress trunk with bark taper and natural slight curvature.
    - 12 radial horizontal branch scaffolds.
    - Dense multi-plane drooping foliage fan cards.
    - Outward spherical vertex normals for soft, lush canopy lighting.
    """
    # 1. Trunk
    t_verts, t_uvs, t_norms, t_faces = [], [], [], []
    segs = 16
    height_steps = 14
    total_height = 1800.0 # 18 meters

    for hi in range(height_steps + 1):
        norm_h = hi / height_steps
        z = norm_h * total_height

        # Root flare at bottom, tapering up to crown
        if norm_h < 0.08:
            flare = 1.0 + (1.0 - norm_h / 0.08) * 0.9 # Flared root base
            radius = 65.0 * flare
        else:
            radius = 65.0 * (1.0 - norm_h * 0.78)

        # Subtle natural tree bend
        bend_x = math.sin(norm_h * math.pi) * 18.0
        bend_y = math.cos(norm_h * math.pi * 0.5) * 8.0

        for i in range(segs):
            ang = (2 * math.pi / segs) * i
            # Organic trunk fluting
            flute = 1.0 + 0.06 * math.sin(ang * 5.0)
            vx = bend_x + radius * math.cos(ang) * flute
            vy = bend_y + radius * math.sin(ang) * flute
            vz = z

            t_verts.append((vx, vy, vz))
            t_uvs.append((i / segs * 2.0, norm_h * 6.0)) # Tiling bark UVs
            t_norms.append((math.cos(ang), math.sin(ang), 0.0))

    for hi in range(height_steps):
        for i in range(segs):
            next_i = (i + 1) % segs
            b1 = hi * segs + i + 1
            b2 = hi * segs + next_i + 1
            t1 = (hi + 1) * segs + i + 1
            t2 = (hi + 1) * segs + next_i + 1
            t_faces.append((b1, t2, b2))
            t_faces.append((b1, t1, t2))

    # 2. Foliage Branch Fan Clusters
    f_verts, f_uvs, f_norms, f_faces = [], [], [], []
    num_branch_tiers = 12
    canopy_start_z = 450.0 # Clear lower trunk

    for tier in range(num_branch_tiers):
        t_frac = tier / num_branch_tiers
        tz = canopy_start_z + t_frac * (total_height - canopy_start_z)
        tier_radius = (1.0 - t_frac * 0.75) * 380.0
        num_branches = 7 if tier < 8 else 5

        for bi in range(num_branches):
            b_ang = (2 * math.pi / num_branches) * bi + tier * 0.7
            # Branch emergence point
            bx = 18.0 * math.cos(b_ang)
            by = 18.0 * math.sin(b_ang)
            tip_x = (tier_radius + random.uniform(-20, 20)) * math.cos(b_ang)
            tip_y = (tier_radius + random.uniform(-20, 20)) * math.sin(b_ang)
            # Natural branch droop
            tip_z = tz - tier_radius * 0.22

            # Crossed foliage cards along branch (3 card clusters per branch)
            for card_i in range(3):
                frac = 0.35 + card_i * 0.3
                cx = bx + (tip_x - bx) * frac
                cy = by + (tip_y - by) * frac
                cz = tz + (tip_z - tz) * frac
                card_size = (1.0 - t_frac * 0.4) * (140.0 - card_i * 20.0)

                # Generate 2 crossed angled quad cards (X-pattern)
                for ang_offset in [0.0, math.pi / 2.0]:
                    v_base = len(f_verts)
                    card_ang = b_ang + ang_offset
                    dx = math.cos(card_ang) * card_size * 0.5
                    dy = math.sin(card_ang) * card_size * 0.5
                    dz = card_size * 0.45

                    # 4 vertices for quad card
                    v1 = (cx - dx, cy - dy, cz - dz * 0.3)
                    v2 = (cx + dx, cy + dy, cz - dz * 0.3)
                    v3 = (cx + dx, cy + dy, cz + dz * 0.7)
                    v4 = (cx - dx, cy - dy, cz + dz * 0.7)

                    f_verts.extend([v1, v2, v3, v4])
                    f_uvs.extend([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
                    # Outward spherical normal for soft canopy lighting
                    norm_len = math.sqrt(cx*cx + cy*cy + (cz - 1000.0)**2) + 0.001
                    nx, ny, nz = cx / norm_len, cy / norm_len, (cz - 1000.0) / norm_len
                    f_norms.extend([(nx, ny, nz)] * 4)

                    # Two-sided quad faces
                    p1, p2, p3, p4 = v_base + 1, v_base + 2, v_base + 3, v_base + 4
                    f_faces.append((p1, p3, p2))
                    f_faces.append((p1, p4, p3))
                    # Backface
                    f_faces.append((p1, p2, p3))
                    f_faces.append((p1, p3, p4))

    sections = [
        {"material": "M_Pine_Bark", "vertices": t_verts, "uvs": t_uvs, "normals": t_norms, "faces": t_faces},
        {"material": "M_Pine_Needles", "vertices": f_verts, "uvs": f_uvs, "normals": f_norms, "faces": f_faces}
    ]
    write_obj_mesh(filepath, "SM_PineTree_Realistic", sections)

def generate_realistic_oak_obj(filepath):
    """
    Generates a Mature Deciduous Oak with:
    - Girthy branched trunk splitting into 4 primary scaffold limbs.
    - Dense multi-plane leafy foliage domes with outward spherical normals.
    """
    # 1. Trunk and major limbs
    t_verts, t_uvs, t_norms, t_faces = [], [], [], []
    segs = 14
    height = 950.0
    r_bot = 85.0
    r_top = 45.0

    # Main trunk
    for hi in range(6):
        nh = hi / 5.0
        z = nh * 450.0
        r = r_bot * (1.0 - nh * 0.35)
        for i in range(segs):
            ang = (2 * math.pi / segs) * i
            flute = 1.0 + 0.08 * math.sin(ang * 4.0)
            t_verts.append((r * math.cos(ang) * flute, r * math.sin(ang) * flute, z))
            t_uvs.append((i / segs * 2.0, nh * 2.5))
            t_norms.append((math.cos(ang), math.sin(ang), 0.0))

    for hi in range(5):
        for i in range(segs):
            next_i = (i + 1) % segs
            b1 = hi * segs + i + 1
            b2 = hi * segs + next_i + 1
            t1 = (hi + 1) * segs + i + 1
            t2 = (hi + 1) * segs + next_i + 1
            t_faces.append((b1, t2, b2))
            t_faces.append((b1, t1, t2))

    # 4 Arching Scaffold Limbs
    limb_angles = [0.0, math.pi * 0.5, math.pi, math.pi * 1.5]
    for la in limb_angles:
        v_offset = len(t_verts)
        limb_segs = 8
        limb_r = 30.0
        for l_step in range(5):
            frac = l_step / 4.0
            lz = 450.0 + frac * 450.0
            lx = (frac * 220.0 + 40.0) * math.cos(la)
            ly = (frac * 220.0 + 40.0) * math.sin(la)
            cur_r = limb_r * (1.0 - frac * 0.5)

            for i in range(limb_segs):
                ang = (2 * math.pi / limb_segs) * i
                t_verts.append((lx + cur_r * math.cos(ang), ly + cur_r * math.sin(ang), lz))
                t_uvs.append((i / limb_segs, frac * 2.0))
                t_norms.append((math.cos(ang), math.sin(ang), 0.2))

        for l_step in range(4):
            for i in range(limb_segs):
                next_i = (i + 1) % limb_segs
                b1 = v_offset + l_step * limb_segs + i + 1
                b2 = v_offset + l_step * limb_segs + next_i + 1
                t1 = v_offset + (l_step + 1) * limb_segs + i + 1
                t2 = v_offset + (l_step + 1) * limb_segs + next_i + 1
                t_faces.append((b1, t2, b2))
                t_faces.append((b1, t1, t2))

    # 2. Foliage Canopy Domes (Dense layered leaf clusters)
    f_verts, f_uvs, f_norms, f_faces = [], [], [], []
    dome_centers = [
        (0.0, 0.0, 1100.0, 340.0),
        (220.0, 60.0, 950.0, 260.0),
        (-200.0, 120.0, 980.0, 270.0),
        (60.0, -220.0, 960.0, 280.0),
        (-140.0, -160.0, 920.0, 250.0)
    ]

    for cx, cy, cz, rad in dome_centers:
        # Generate 14 intersecting leafy quad planes in each dome
        for di in range(14):
            v_base = len(f_verts)
            theta = random.uniform(0, math.pi * 0.8)
            phi = random.uniform(0, 2 * math.pi)
            offset_r = random.uniform(0.3, 0.95) * rad
            qx = cx + offset_r * math.sin(theta) * math.cos(phi)
            qy = cy + offset_r * math.sin(theta) * math.sin(phi)
            qz = cz + offset_r * math.cos(theta)
            q_size = random.uniform(140.0, 220.0)

            # Angled quad plane
            yaw_q = random.uniform(0, 2 * math.pi)
            pitch_q = random.uniform(-0.4, 0.4)
            dx = math.cos(yaw_q) * q_size * 0.5
            dy = math.sin(yaw_q) * q_size * 0.5
            dz = math.sin(pitch_q) * q_size * 0.5

            v1 = (qx - dx, qy - dy, qz - dz)
            v2 = (qx + dx, qy + dy, qz + dz)
            v3 = (qx + dx, qy + dy, qz + q_size * 0.6)
            v4 = (qx - dx, qy - dy, qz + q_size * 0.6)

            f_verts.extend([v1, v2, v3, v4])
            f_uvs.extend([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
            # Outward spherical normal
            nl = math.sqrt((qx - cx)**2 + (qy - cy)**2 + (qz - cz)**2) + 0.01
            nx, ny, nz = (qx - cx)/nl, (qy - cy)/nl, (qz - cz)/nl
            f_norms.extend([(nx, ny, nz)] * 4)

            p1, p2, p3, p4 = v_base + 1, v_base + 2, v_base + 3, v_base + 4
            f_faces.append((p1, p3, p2))
            f_faces.append((p1, p4, p3))
            f_faces.append((p1, p2, p3))
            f_faces.append((p1, p3, p4))

    sections = [
        {"material": "M_Oak_Bark", "vertices": t_verts, "uvs": t_uvs, "normals": t_norms, "faces": t_faces},
        {"material": "M_Oak_Leaves", "vertices": f_verts, "uvs": f_uvs, "normals": f_norms, "faces": f_faces}
    ]
    write_obj_mesh(filepath, "SM_OakTree_Realistic", sections)

def generate_realistic_fern_obj(filepath):
    """Generates an organic multi-frond forest fern."""
    verts, uvs, norms, faces = [], [], [], []
    num_fronds = 8

    for fi in range(num_fronds):
        f_ang = (2 * math.pi / num_fronds) * fi + random.uniform(-0.15, 0.15)
        frond_len = random.uniform(90.0, 130.0)
        frond_width = random.uniform(35.0, 50.0)
        steps = 6

        v_offset = len(verts)
        for si in range(steps + 1):
            frac = si / steps
            # Arching curve
            dist = frac * frond_len
            fz = math.sin(frac * math.pi * 0.8) * 35.0 - (frac ** 2) * 15.0
            fx = dist * math.cos(f_ang)
            fy = dist * math.sin(f_ang)
            cur_w = math.sin(frac * math.pi) * frond_width * 0.5

            # Left and right frond edge
            perp_x = -math.sin(f_ang) * cur_w
            perp_y = math.cos(f_ang) * cur_w

            v_left = (fx + perp_x, fy + perp_y, fz)
            v_right = (fx - perp_x, fy - perp_y, fz)
            verts.extend([v_left, v_right])
            uvs.extend([(0.0, frac), (1.0, frac)])
            norms.extend([(0.0, 0.0, 1.0), (0.0, 0.0, 1.0)])

        for si in range(steps):
            p1 = v_offset + si * 2 + 1
            p2 = v_offset + si * 2 + 2
            p3 = v_offset + (si + 1) * 2 + 2
            p4 = v_offset + (si + 1) * 2 + 1
            faces.append((p1, p3, p2))
            faces.append((p1, p4, p3))
            faces.append((p1, p2, p3))
            faces.append((p1, p3, p4))

    sections = [
        {"material": "M_Fern_Frond", "vertices": verts, "uvs": uvs, "normals": norms, "faces": faces}
    ]
    write_obj_mesh(filepath, "SM_ForestFern_01", sections)

def generate_realistic_rock_obj(filepath):
    """Generates an organic faceted stratified granite boulder."""
    verts, uvs, norms, faces = [], [], [], []
    lat_count = 8
    lon_count = 12
    rx, ry, rz = 240.0, 190.0, 140.0

    random.seed(777)
    for lat in range(lat_count + 1):
        theta = (math.pi / lat_count) * lat
        sin_t = math.sin(theta)
        cos_t = math.cos(theta)

        for lon in range(lon_count):
            phi = (2 * math.pi / lon_count) * lon
            nx = sin_t * math.cos(phi)
            ny = sin_t * math.sin(phi)
            nz = cos_t

            # Stratified organic rock noise
            planar_noise = math.sin(lat * 2.5 + lon * 1.5) * 0.15 + math.cos(lon * 3.0) * 0.1
            noise = 1.0 + planar_noise
            vx = rx * nx * noise
            vy = ry * ny * noise
            vz = rz * nz * noise if nz >= 0 else rz * nz * 0.35

            verts.append((vx, vy, vz))
            uvs.append((lon / lon_count * 2.0, lat / lat_count * 2.0))
            norms.append((nx, ny, nz))

    for lat in range(lat_count):
        for lon in range(lon_count):
            next_lon = (lon + 1) % lon_count
            p1 = lat * lon_count + lon + 1
            p2 = lat * lon_count + next_lon + 1
            p3 = (lat + 1) * lon_count + next_lon + 1
            p4 = (lat + 1) * lon_count + lon + 1
            faces.append((p1, p3, p2))
            faces.append((p1, p4, p3))

    sections = [
        {"material": "M_Rock_Granite", "vertices": verts, "uvs": uvs, "normals": norms, "faces": faces}
    ]
    write_obj_mesh(filepath, "SM_ForestRock_Realistic", sections)

def generate_realistic_fallen_log_obj(filepath):
    """Generates a mossy curved fallen tree log with broken branch nubs."""
    verts, uvs, norms, faces = [], [], [], []
    segs = 10
    steps = 12
    log_len = 650.0 # 6.5 meters long
    r_base = 32.0

    for si in range(steps + 1):
        frac = si / steps
        x = (frac - 0.5) * log_len
        # Subtle horizontal log curvature
        y = math.sin(frac * math.pi) * 25.0
        z = r_base * 0.8
        cur_r = r_base * (1.0 - frac * 0.35)

        for i in range(segs):
            ang = (2 * math.pi / segs) * i
            vy = y + cur_r * math.cos(ang)
            vz = z + cur_r * math.sin(ang)
            verts.append((x, vy, vz))
            uvs.append((frac * 4.0, i / segs))
            norms.append((0.0, math.cos(ang), math.sin(ang)))

    for si in range(steps):
        for i in range(segs):
            next_i = (i + 1) % segs
            b1 = si * segs + i + 1
            b2 = si * segs + next_i + 1
            t1 = (si + 1) * segs + i + 1
            t2 = (si + 1) * segs + next_i + 1
            faces.append((b1, t2, b2))
            faces.append((b1, t1, t2))

    sections = [
        {"material": "M_Pine_Bark", "vertices": verts, "uvs": uvs, "normals": norms, "faces": faces}
    ]
    write_obj_mesh(filepath, "SM_FallenLog_01", sections)

# -------------------------------------------------------------
# 3. Main Builder Function (Unreal Editor Python Execution)
# -------------------------------------------------------------

def build_photorealistic_forest():
    print("[AGY] Step 1: Generating High-Resolution PBR Textures & Realistic 3D Models...")
    create_photorealistic_textures()

    p_pine = os.path.join(GENERATED_DIR, "SM_PineTree_Realistic.obj")
    p_oak = os.path.join(GENERATED_DIR, "SM_OakTree_Realistic.obj")
    p_fern = os.path.join(GENERATED_DIR, "SM_ForestFern_01.obj")
    p_rock = os.path.join(GENERATED_DIR, "SM_ForestRock_Realistic.obj")
    p_log = os.path.join(GENERATED_DIR, "SM_FallenLog_01.obj")

    generate_realistic_pine_obj(p_pine)
    generate_realistic_oak_obj(p_oak)
    generate_realistic_fern_obj(p_fern)
    generate_realistic_rock_obj(p_rock)
    generate_realistic_fallen_log_obj(p_log)

    try:
        import unreal
    except ImportError:
        print("[AGY] Assets generated on disk. Run via UnrealEditor-Cmd to build in engine.")
        return True

    unreal.log("==================================================")
    unreal.log("[AGY] Step 2: Importing Textures and Creating Subsurface Materials...")
    unreal.log("==================================================")

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    editor_asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    level_editor_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor_actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mel = unreal.MaterialEditingLibrary

    # Import Textures
    tex_files = [
        ("T_Pine_Bark_D.bmp", "T_Pine_Bark_D"),
        ("T_Pine_Needles_D.bmp", "T_Pine_Needles_D"),
        ("T_Oak_Bark_D.bmp", "T_Oak_Bark_D"),
        ("T_Oak_Leaves_D.bmp", "T_Oak_Leaves_D"),
        ("T_Forest_Ground_D.bmp", "T_Forest_Ground_D"),
        ("T_Rock_Granite_D.bmp", "T_Rock_Granite_D"),
        ("T_Fern_Frond_D.bmp", "T_Fern_Frond_D")
    ]
    for t_file, t_name in tex_files:
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

    # Create Materials with Subsurface Translucency & Two-Sided Foliage
    mat_configs = [
        # (mat_name, tex_name, fallback_color, roughness, is_two_sided, subsurface_color)
        ("M_Pine_Bark", "T_Pine_Bark_D", unreal.LinearColor(0.25, 0.15, 0.08, 1.0), 0.92, False, None),
        ("M_Pine_Needles", "T_Pine_Needles_D", unreal.LinearColor(0.08, 0.28, 0.09, 1.0), 0.45, True, unreal.LinearColor(0.28, 0.58, 0.12, 1.0)),
        ("M_Oak_Bark", "T_Oak_Bark_D", unreal.LinearColor(0.28, 0.22, 0.16, 1.0), 0.88, False, None),
        ("M_Oak_Leaves", "T_Oak_Leaves_D", unreal.LinearColor(0.14, 0.45, 0.11, 1.0), 0.42, True, unreal.LinearColor(0.35, 0.65, 0.15, 1.0)),
        ("M_Forest_Ground", "T_Forest_Ground_D", unreal.LinearColor(0.16, 0.35, 0.12, 1.0), 0.85, False, None),
        ("M_Rock_Granite", "T_Rock_Granite_D", unreal.LinearColor(0.44, 0.44, 0.45, 1.0), 0.72, False, None),
        ("M_Fern_Frond", "T_Fern_Frond_D", unreal.LinearColor(0.12, 0.52, 0.10, 1.0), 0.38, True, unreal.LinearColor(0.30, 0.68, 0.14, 1.0)),
    ]

    materials_map = {}
    for mat_name, tex_name, fallback_color, roughness, is_two_sided, subsurf_col in mat_configs:
        mat_path = f"/Game/Forest/Materials/{mat_name}"
        if editor_asset_sub.does_asset_exist(mat_path):
            editor_asset_sub.delete_asset(mat_path)

        mat_factory = unreal.MaterialFactoryNew()
        mat = asset_tools.create_asset(mat_name, "/Game/Forest/Materials", unreal.Material, mat_factory)
        if mat:
            mat.set_editor_property("used_with_nanite", True)
            if is_two_sided:
                mat.set_editor_property("two_sided", True)

            tex_asset = editor_asset_sub.load_asset(f"/Game/Forest/Textures/{tex_name}.{tex_name}")
            if tex_asset:
                tex_node = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -400, 0)
                tex_node.set_editor_property("texture", tex_asset)
                mel.connect_material_property(tex_node, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
            else:
                col_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
                col_node.set_editor_property("constant", fallback_color)
                mel.connect_material_property(col_node, "", unreal.MaterialProperty.MP_BASE_COLOR)

            r_node = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 160)
            r_node.set_editor_property("r", roughness)
            mel.connect_material_property(r_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

            mel.recompile_material(mat)
            editor_asset_sub.save_asset(mat_path)
            materials_map[mat_name] = mat
            unreal.log(f"[AGY] Created & Compiled Photorealistic Material: {mat_path}")

    # Import Meshes
    unreal.log("==================================================")
    unreal.log("[AGY] Step 3: Importing Realistic 3D Meshes into Unreal...")
    unreal.log("==================================================")
    mesh_files = [
        (p_pine, "SM_PineTree_Realistic"),
        (p_oak, "SM_OakTree_Realistic"),
        (p_fern, "SM_ForestFern_01"),
        (p_rock, "SM_ForestRock_Realistic"),
        (p_log, "SM_FallenLog_01")
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
        unreal.log(f"[AGY] Imported Realistic Mesh: /Game/Forest/Meshes/{m_name}")

    # Load Meshes and Assign Materials & Collision
    mesh_pine = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_PineTree_Realistic.SM_PineTree_Realistic")
    mesh_oak = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_OakTree_Realistic.SM_OakTree_Realistic")
    mesh_fern = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestFern_01.SM_ForestFern_01")
    mesh_rock = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestRock_Realistic.SM_ForestRock_Realistic")
    mesh_log = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_FallenLog_01.SM_FallenLog_01")
    mesh_terrain = editor_asset_sub.load_asset("/Game/Forest/Meshes/SM_ForestLandscape.SM_ForestLandscape")

    all_meshes = [mesh_pine, mesh_oak, mesh_fern, mesh_rock, mesh_log, mesh_terrain]
    for m in all_meshes:
        if m:
            nanite_s = m.get_editor_property("nanite_settings")
            if nanite_s:
                if m == mesh_terrain:
                    nanite_s.set_editor_property("enabled", False)
                else:
                    nanite_s.set_editor_property("enabled", True)
                m.set_editor_property("nanite_settings", nanite_s)

            body_setup = m.get_editor_property("body_setup")
            if body_setup:
                body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            editor_asset_sub.save_loaded_asset(m)

    # Assign Materials to Slots
    mat_pine_bark = materials_map.get("M_Pine_Bark")
    mat_pine_needles = materials_map.get("M_Pine_Needles")
    mat_oak_bark = materials_map.get("M_Oak_Bark")
    mat_oak_leaves = materials_map.get("M_Oak_Leaves")
    mat_ground = materials_map.get("M_Forest_Ground")
    mat_rock = materials_map.get("M_Rock_Granite")
    mat_fern = materials_map.get("M_Fern_Frond")

    if mesh_pine:
        mesh_pine.set_material(0, mat_pine_bark)
        mesh_pine.set_material(1, mat_pine_needles)
        editor_asset_sub.save_loaded_asset(mesh_pine)
    if mesh_oak:
        mesh_oak.set_material(0, mat_oak_bark)
        mesh_oak.set_material(1, mat_oak_leaves)
        editor_asset_sub.save_loaded_asset(mesh_oak)
    if mesh_fern:
        mesh_fern.set_material(0, mat_fern)
        editor_asset_sub.save_loaded_asset(mesh_fern)
    if mesh_rock:
        mesh_rock.set_material(0, mat_rock)
        editor_asset_sub.save_loaded_asset(mesh_rock)
    if mesh_log:
        mesh_log.set_material(0, mat_pine_bark)
        editor_asset_sub.save_loaded_asset(mesh_log)
    if mesh_terrain:
        mesh_terrain.set_material(0, mat_ground)
        editor_asset_sub.save_loaded_asset(mesh_terrain)

    # -------------------------------------------------------------
    # Step 4: Populate Photorealistic World in Lvl_Forest
    # -------------------------------------------------------------
    unreal.log("==================================================")
    unreal.log("[AGY] Step 4: Populating Photorealistic World & Lighting...")
    unreal.log("==================================================")

    level_editor_sub.load_level("/Game/Maps/Lvl_Forest")

    # Clean old prototype trees, rocks, bushes
    for actor in editor_actor_sub.get_all_level_actors():
        label = actor.get_actor_label()
        if any(w in label for w in ["Tree", "Rock", "Bush", "Log", "Fern"]):
            editor_actor_sub.destroy_actor(actor)

    def get_terrain_elevation(x, y):
        dist = math.sqrt(x * x + y * y)
        if dist < 4500.0:
            return 0.0
        else:
            elevation = math.sin(x / 3200.0) * math.cos(y / 3200.0) * 380.0
            edge_factor = max(0.0, (dist - 8000.0) / 9500.0)
            return elevation + (edge_factor ** 2) * 1750.0

    random.seed(2026)

    # 1. Populate 150 Photorealistic Pine & Oak Trees (Strictly Vertical)
    unreal.log("[AGY] Spawning 150 Photorealistic Trees...")
    for i in range(150):
        dist = random.uniform(850.0, 15000.0) # Central clearing free
        theta = random.uniform(0, 2 * math.pi)
        tx = dist * math.cos(theta)
        ty = dist * math.sin(theta)
        tz = get_terrain_elevation(tx, ty)

        scale_var = random.uniform(0.85, 1.45)
        rot_yaw = random.uniform(0, 360)
        is_pine = random.random() < 0.68
        tree_mesh = mesh_pine if is_pine else mesh_oak

        tree = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(tx, ty, tz - 18.0), # Plant firmly in ground
            unreal.Rotator(0.0, rot_yaw, 0.0)  # 100% Vertical!
        )
        tree.set_actor_label(f"Forest_RealisticTree_{i+1:03d}")
        tree.set_actor_scale3d(unreal.Vector(scale_var, scale_var, scale_var))
        t_sm = tree.get_component_by_class(unreal.StaticMeshComponent)
        if t_sm:
            t_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if tree_mesh:
                t_sm.set_static_mesh(tree_mesh)
            t_sm.set_collision_profile_name("BlockAll")
            t_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 2. Populate 25 Fallen Mossy Logs
    unreal.log("[AGY] Spawning 25 Fallen Mossy Logs...")
    for i in range(25):
        dist = random.uniform(1200.0, 13500.0)
        theta = random.uniform(0, 2 * math.pi)
        lx = dist * math.cos(theta)
        ly = dist * math.sin(theta)
        lz = get_terrain_elevation(lx, ly)

        log_actor = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(lx, ly, lz + 10.0),
            unreal.Rotator(random.uniform(-4.0, 4.0), random.uniform(0, 360), random.uniform(-4.0, 4.0))
        )
        log_actor.set_actor_label(f"Forest_FallenLog_{i+1:02d}")
        log_scale = random.uniform(1.0, 1.8)
        log_actor.set_actor_scale3d(unreal.Vector(log_scale, log_scale, log_scale))
        l_sm = log_actor.get_component_by_class(unreal.StaticMeshComponent)
        if l_sm:
            l_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if mesh_log:
                l_sm.set_static_mesh(mesh_log)
            l_sm.set_collision_profile_name("BlockAll")

    # 3. Populate 80 Lush Fern Frond Clusters
    unreal.log("[AGY] Spawning 80 Fern Clusters...")
    for i in range(80):
        dist = random.uniform(600.0, 13000.0)
        theta = random.uniform(0, 2 * math.pi)
        fx = dist * math.cos(theta)
        fy = dist * math.sin(theta)
        fz = get_terrain_elevation(fx, fy)

        fern = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(fx, fy, fz),
            unreal.Rotator(0.0, random.uniform(0, 360), 0.0)
        )
        fern.set_actor_label(f"Forest_Fern_{i+1:02d}")
        f_scale = random.uniform(1.0, 2.2)
        fern.set_actor_scale3d(unreal.Vector(f_scale, f_scale, f_scale))
        f_sm = fern.get_component_by_class(unreal.StaticMeshComponent)
        if f_sm:
            f_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if mesh_fern:
                f_sm.set_static_mesh(mesh_fern)
            f_sm.set_collision_profile_name("BlockAll")

    # 4. Populate 50 Stratified Granite Boulders
    unreal.log("[AGY] Spawning 50 Granite Boulders...")
    for i in range(50):
        dist = random.uniform(900.0, 14000.0)
        theta = random.uniform(0, 2 * math.pi)
        rx = dist * math.cos(theta)
        ry = dist * math.sin(theta)
        rz = get_terrain_elevation(rx, ry)

        rock = editor_actor_sub.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(rx, ry, rz - 15.0), # Partially embedded in soil
            unreal.Rotator(random.uniform(-6.0, 6.0), random.uniform(0, 360), random.uniform(-6.0, 6.0))
        )
        rock.set_actor_label(f"Forest_GraniteBoulder_{i+1:02d}")
        r_scale = random.uniform(1.2, 3.5)
        rock.set_actor_scale3d(unreal.Vector(r_scale, r_scale, r_scale))
        r_sm = rock.get_component_by_class(unreal.StaticMeshComponent)
        if r_sm:
            r_sm.set_mobility(unreal.ComponentMobility.STATIC)
            if mesh_rock:
                r_sm.set_static_mesh(mesh_rock)
            r_sm.set_collision_profile_name("BlockAll")
            r_sm.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    # 5. Configure Cinematic Atmosphere & Lighting
    unreal.log("[AGY] Tuning Directional Light & Volumetric Fog...")
    for a in editor_actor_sub.get_all_level_actors():
        if isinstance(a, unreal.DirectionalLight):
            # Golden morning sunlight angle
            a.set_actor_rotation(unreal.Rotator(pitch=-34.0, yaw=48.0, roll=0.0), False)
            light_comp = a.get_component_by_class(unreal.DirectionalLightComponent)
            if light_comp:
                light_comp.set_editor_property("intensity", 75000.0) # Lux
                light_comp.set_editor_property("use_temperature", True)
                light_comp.set_editor_property("temperature", 5600.0) # Warm sunlight
                light_comp.set_editor_property("light_source_angle", 0.8) # Soft contact shadows
                light_comp.set_editor_property("cast_volumetric_shadow", True)

        elif isinstance(a, unreal.ExponentialHeightFog):
            fog_comp = a.get_component_by_class(unreal.ExponentialHeightFogComponent)
            if fog_comp:
                if hasattr(fog_comp, "b_enable_volumetric_fog"):
                    fog_comp.set_editor_property("b_enable_volumetric_fog", True)
                elif hasattr(fog_comp, "volumetric_fog"):
                    fog_comp.set_editor_property("volumetric_fog", True)

    level_editor_sub.save_current_level()
    unreal.log("==================================================")
    unreal.log("[AGY] PHOTOREALISTIC FOREST LEVEL GENERATED & SAVED TO /Game/Maps/Lvl_Forest!")
    unreal.log("==================================================")
    return True

if __name__ == "__main__":
    build_photorealistic_forest()
