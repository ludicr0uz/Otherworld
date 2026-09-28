"""
terrain.py — Procedural terrain mesh generator (pure Python, no Unreal dependency).

Generates a solid 3D landscape OBJ file with:
  - Parameterized world size (in meters)
  - Adaptive grid resolution
  - Sculpted hills with flat spawn area at center
  - Clean normalized UVs [0, 1]
  - Gradient-based smoothed normals
  - Solid collision skirt + base cap

The elevation function and grid layout are exported so that tree-placement
code can compute exact barycentric Z coordinates on the mesh triangles.
"""

import math
import os


# ─── Elevation ───────────────────────────────────────────────────────────────

def make_elevation_fn(world_size_cm: float):
    """
    Returns an elevation function `elev(x, y) -> z` parameterized by
    *world_size_cm* (the total side length in centimeters).

    The terrain is centred at (0, 0).  A flat disk of radius
    ``0.1125 * world_size_cm`` surrounds the origin (player spawn zone).
    Beyond that, gentle sine-cosine hills rise, with steeper edges at
    the perimeter.

    All thresholds scale proportionally with world_size_cm so a 200 m map
    looks like a smaller slice of a 400 m map.
    """
    # Scale factors derived from the reference 400 m (40 000 cm) map
    ref = 40_000.0
    s = world_size_cm / ref  # linear scale
    if world_size_cm > LARGE_MAP_THRESHOLD_CM:
        return _make_large_elevation_fn(world_size_cm, s)

    flat_radius    = 4_500.0 * s
    wave_period    = 3_200.0 * s
    wave_amplitude = 380.0   * s
    edge_onset     = 8_000.0 * s
    edge_ramp      = 9_500.0 * s
    edge_height    = 1_750.0 * s

    def elev(x: float, y: float) -> float:
        dist = math.hypot(x, y)
        if dist < flat_radius:
            return 0.0
        elevation = (math.sin(x / wave_period)
                     * math.cos(y / wave_period)
                     * wave_amplitude)
        edge_factor = max(0.0, (dist - edge_onset) / edge_ramp)
        return elevation + (edge_factor ** 2) * edge_height

    return elev


# Maps wider than 200 m.  Scaling the reference shape linearly breaks twice
# past that size.  First, the radial edge bowl's corners outgrow what Recast
# will build a navmesh over (NAV_MAX_VERTICAL_SPAN_CM): 300 m already asks for
# a 4976 cm band, and 1000 m climbs to ~197 m at the corners.  Second, the
# hills start at full amplitude right at the flat disk's edge, which leaves a
# cliff (9.5 m on a 1000 m map).  So past 200 m the hills keep scaling, but
# they fade in over a blend ring, and the edge is a rim of FIXED size measured
# by box distance.  Box distance keeps the rim equally tall along the sides and
# at the corners.  200 m, the largest map built with the bowl, is unchanged.
LARGE_MAP_THRESHOLD_CM = 20_000.0
LARGE_WAVE_BLEND_CM = 4_000.0    # hills fade in over this ring past the flat disk
LARGE_RIM_WIDTH_CM = 6_000.0     # rim rises over the outermost 60 m of each side
LARGE_RIM_HEIGHT_CM = 2_000.0    # ...to 20 m at the very edge
LARGE_WAVE_AMPLITUDE_CAP_CM = 600.0   # valleys stay 4 m above WORLD_FLOOR_Z (-1000 cm)


def _make_large_elevation_fn(world_size_cm: float, s: float):
    half = world_size_cm / 2.0
    flat_radius = 4_500.0 * s
    wave_period = 3_200.0 * s
    wave_amplitude = min(380.0 * s, LARGE_WAVE_AMPLITUDE_CAP_CM)
    rim_onset = half - LARGE_RIM_WIDTH_CM

    def elev(x: float, y: float) -> float:
        dist = math.hypot(x, y)
        if dist < flat_radius:
            return 0.0
        t = min(1.0, (dist - flat_radius) / LARGE_WAVE_BLEND_CM)
        blend = t * t * (3.0 - 2.0 * t)          # smoothstep: no cliff, no kink
        elevation = (math.sin(x / wave_period)
                     * math.cos(y / wave_period)
                     * wave_amplitude * blend)
        rim = max(0.0, (max(abs(x), abs(y)) - rim_onset) / LARGE_RIM_WIDTH_CM)
        return elevation + (rim ** 2) * LARGE_RIM_HEIGHT_CM

    return elev


# ─── Grid helpers ────────────────────────────────────────────────────────────

def compute_grid(world_size_cm: float, grid_size: int, elev_fn):
    """
    Pre-calculate the Z value at every grid vertex.

    Returns a 2-D list ``grid_z[gi][gj]`` where ``gi`` runs along the X axis
    and ``gj`` along the Y axis.  Indices go from 0 to *grid_size* inclusive.
    """
    step = world_size_cm / grid_size
    half = world_size_cm / 2.0
    grid_z = [[0.0] * (grid_size + 1) for _ in range(grid_size + 1)]
    for gi in range(grid_size + 1):
        gx = -half + gi * step
        for gj in range(grid_size + 1):
            gy = -half + gj * step
            grid_z[gi][gj] = elev_fn(gx, gy)
    return grid_z


def get_exact_mesh_z(x: float, y: float,
                     grid_z, grid_size: int, world_size_cm: float) -> float:
    """
    Exact barycentric interpolation on the triangulated quad grid.

    Each quad ``[gi, gj]`` is split into two triangles along its diagonal.
    This function determines which triangle contains ``(x, y)`` and returns
    the linearly interpolated Z.
    """
    step = world_size_cm / grid_size
    half = world_size_cm / 2.0
    cx = max(-half, min(half, x))
    cy = max(-half, min(half, y))

    u = (cx + half) / step
    v = (cy + half) / step

    gi = max(0, min(grid_size - 1, int(math.floor(u))))
    gj = max(0, min(grid_size - 1, int(math.floor(v))))

    fu = u - gi
    fv = v - gj

    z00 = grid_z[gi][gj]
    z01 = grid_z[gi][gj + 1]
    z11 = grid_z[gi + 1][gj + 1]
    z10 = grid_z[gi + 1][gj]

    if fu <= fv:
        return z00 + fu * (z11 - z01) + fv * (z01 - z00)
    else:
        return z00 + fu * (z10 - z00) + fv * (z11 - z10)


# ─── OBJ writer ─────────────────────────────────────────────────────────────

def grid_size_for_world(world_size_cm: float) -> int:
    """
    Pick a grid resolution that keeps quad edges around 5-6 m.
    Clamped between 16 (tiny maps) and 128 (enormous maps).
    """
    ideal = int(round(world_size_cm / 600.0))
    return max(16, min(128, ideal))


def generate_terrain_obj(filepath: str, world_size_cm: float,
                         grid_size: int | None = None) -> dict:
    """
    Write a complete OBJ file for the terrain mesh and return metadata.

    Parameters
    ----------
    filepath : str
        Absolute path for the output ``.obj`` file.
    world_size_cm : float
        Total side length of the square terrain in centimetres.
    grid_size : int or None
        Number of quads per side.  ``None`` picks automatically.

    Returns
    -------
    dict
        ``{"grid_size", "world_size_cm", "obj_path", "bytes", "elev_fn",
           "grid_z"}``
    """
    if grid_size is None:
        grid_size = grid_size_for_world(world_size_cm)

    step = world_size_cm / grid_size
    half = world_size_cm / 2.0
    base_z = -800.0

    elev_fn = make_elevation_fn(world_size_cm)

    verts, uvs, norms, faces = [], [], [], []

    # ── top surface ──────────────────────────────────────────────────────
    top_grid = []
    for gi in range(grid_size + 1):
        row = []
        x = -half + gi * step
        u_coord = gi / grid_size
        for gj in range(grid_size + 1):
            y = -half + gj * step
            v_coord = gj / grid_size
            z = elev_fn(x, y)

            eps = 50.0
            dz_dx = (elev_fn(x + eps, y) - elev_fn(x - eps, y)) / (2.0 * eps)
            dz_dy = (elev_fn(x, y + eps) - elev_fn(x, y - eps)) / (2.0 * eps)
            nx, ny, nz = -dz_dx, -dz_dy, 1.0
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            nx, ny, nz = nx / length, ny / length, nz / length

            idx = len(verts) + 1          # OBJ is 1-based
            verts.append((x, y, z))
            uvs.append((u_coord, v_coord))
            norms.append((nx, ny, nz))
            row.append(idx)
        top_grid.append(row)

    for gi in range(grid_size):
        for gj in range(grid_size):
            p1 = top_grid[gi][gj]
            p2 = top_grid[gi][gj + 1]
            p3 = top_grid[gi + 1][gj + 1]
            p4 = top_grid[gi + 1][gj]
            faces.append((p1, p3, p2))
            faces.append((p1, p4, p3))

    # ── bottom cap ───────────────────────────────────────────────────────
    bot_grid = []
    for gi in range(grid_size + 1):
        row = []
        x = -half + gi * step
        u_coord = gi / grid_size
        for gj in range(grid_size + 1):
            y = -half + gj * step
            v_coord = gj / grid_size
            idx = len(verts) + 1
            verts.append((x, y, base_z))
            uvs.append((u_coord, v_coord))
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

    # ── side skirts ──────────────────────────────────────────────────────
    def _skirt(edge_top, edge_bot, reverse=False):
        n = len(edge_top) - 1
        for k in range(n):
            t1, t2 = edge_top[k], edge_top[k + 1]
            b1, b2 = edge_bot[k], edge_bot[k + 1]
            if reverse:
                faces.append((t1, b2, b1))
                faces.append((t1, t2, b2))
            else:
                faces.append((t1, b1, b2))
                faces.append((t1, b2, t2))

    _skirt([top_grid[0][j] for j in range(grid_size + 1)],
           [bot_grid[0][j] for j in range(grid_size + 1)], reverse=False)
    _skirt([top_grid[grid_size][j] for j in range(grid_size + 1)],
           [bot_grid[grid_size][j] for j in range(grid_size + 1)], reverse=True)
    _skirt([top_grid[i][0] for i in range(grid_size + 1)],
           [bot_grid[i][0] for i in range(grid_size + 1)], reverse=True)
    _skirt([top_grid[i][grid_size] for i in range(grid_size + 1)],
           [bot_grid[i][grid_size] for i in range(grid_size + 1)], reverse=False)

    # ── write file ───────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write("# Procedural Forest Terrain Mesh\n")
        f.write("o SM_ForestLandscape\n")
        for v in verts:
            f.write(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}\n")
        for vt in uvs:
            f.write(f"vt {vt[0]:.5f} {vt[1]:.5f}\n")
        for vn in norms:
            f.write(f"vn {vn[0]:.4f} {vn[1]:.4f} {vn[2]:.4f}\n")
        f.write("usemtl M_Forest_Ground_PBR\n")
        for face in faces:
            f.write(f"f {face[0]}/{face[0]}/{face[0]} "
                    f"{face[1]}/{face[1]}/{face[1]} "
                    f"{face[2]}/{face[2]}/{face[2]}\n")

    grid_z = compute_grid(world_size_cm, grid_size, elev_fn)

    return {
        "grid_size":     grid_size,
        "world_size_cm": world_size_cm,
        "obj_path":      filepath,
        "bytes":         os.path.getsize(filepath),
        "elev_fn":       elev_fn,
        "grid_z":        grid_z,
    }
