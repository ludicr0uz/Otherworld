"""Procedural grass-patch and bush geometry. Pure Python (no ``unreal``).

forest_import/foliage_assets.py turns these into StaticMesh assets; the offline
checks and the grass/bush specs read the same numbers (bounds, triangle
counts), so what is verified is what is built.

Why generated, not scanned
--------------------------
The scanned grass clumps (grass_medium_01/02) are 15-32 cm tall cards with an
alpha-masked texture. Stretched to knee height they read as coarse, and masked
foliage is the slow path on Nanite: every masked pixel runs the material in
the programmable rasteriser, the same cost that made the tree canopy the frame
rate's worst case (see forest_import/trees.py). These meshes are real blades
and real leaves with an OPAQUE material -- Nanite's fixed-function raster, no
alpha test, no overdraw from transparent card corners -- so thickness is paid
for in triangles, which Nanite simplifies with distance, instead of in masked
pixels, which it cannot.

Colour is baked per vertex (base-to-tip gradient, dry blades, inner leaves
darker) with the height/depth fraction in alpha for ambient occlusion. The
material (M_ProcFoliage) needs no texture at all.

Units are centimetres, Z up, the mesh origin on the ground at the patch or bush
centre -- the pivot the planting code expects.
"""

import math
import random
from dataclasses import dataclass, field


@dataclass
class MeshBuffers:
    """Flat per-vertex buffers, the shape GeometryScript's SimpleMeshBuffers
    takes. ``colors`` are linear RGBA."""
    vertices: list = field(default_factory=list)   # (x, y, z)
    normals: list = field(default_factory=list)    # (x, y, z), unit
    colors: list = field(default_factory=list)     # (r, g, b, a)
    uvs: list = field(default_factory=list)        # (u, v)
    triangles: list = field(default_factory=list)  # (i, j, k)

    def add(self, pos, nrm, col, uv):
        self.vertices.append(pos)
        self.normals.append(nrm)
        self.colors.append(col)
        self.uvs.append(uv)
        return len(self.vertices) - 1

    @property
    def triangle_count(self):
        return len(self.triangles)

    def bounds(self):
        xs, ys, zs = zip(*self.vertices)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    @property
    def height(self):
        return self.bounds()[1][2]


# ─── Small vector helpers ────────────────────────────────────────────────────

def _norm(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / length, v[1] / length, v[2] / length) if length > 1e-9 else (0.0, 0.0, 1.0)


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _add(a, b, s=1.0):
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


# ─── Grass patch ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GrassPatchRecipe:
    """One grass patch mesh: a disc of blades with a mounded silhouette."""
    name: str                 # asset name, e.g. SM_GrassPatch_A
    seed: int
    blades: int
    radius_cm: float          # footprint radius
    height_cm: float          # the tallest blade, before jitter
    blade_width_cm: tuple = (1.8, 3.2)
    segments: int = 2         # quads per blade below the tip triangle
    seed_stalks: int = 0      # thin stalks with a seed head, above the blades
    dry_share: float = 0.14   # blades tinted straw instead of green


# Colours are linear. The night grade crushes most of this, so the palette is
# about value steps (dark roots, lit tips) more than hue.
_ROOT = (0.020, 0.028, 0.010)
_GREEN_MID = (0.060, 0.105, 0.030)
_GREEN_TIP = (0.130, 0.190, 0.055)
_DRY_MID = (0.140, 0.120, 0.055)
_DRY_TIP = (0.260, 0.220, 0.110)
_STALK = (0.110, 0.100, 0.050)
_SEED = (0.200, 0.160, 0.080)

# Blade normals are bent this far toward straight up. Flat blade normals make
# a patch flicker between lit and black as the view turns; bent ones light the
# patch like one soft volume, which is how thick grass reads.
_GRASS_UP_BEND = 0.55


def _blade(buf, rng, base, height, width, facing, lean_dir, lean, segments,
           mid_col, tip_col):
    """One tapered, curved blade: ``segments`` quads and a tip triangle."""
    side = (math.cos(facing), math.sin(facing), 0.0)
    rows = []
    for s in range(segments + 1):
        t = s / (segments + 1)
        # Quadratic bend: straight at the root, lying over toward the tip.
        bend = lean * t * t
        centre = (base[0] + lean_dir[0] * bend * height,
                  base[1] + lean_dir[1] * bend * height,
                  base[2] + height * t * (1.0 - 0.35 * lean * t))
        half_w = width * 0.5 * (1.0 - t * 0.75)
        rows.append((centre, half_w, t))
    tip_t = 1.0
    tip = (base[0] + lean_dir[0] * lean * height,
           base[1] + lean_dir[1] * lean * height,
           base[2] + height * (1.0 - 0.35 * lean))

    face = _norm(_cross(side, _norm((tip[0] - base[0], tip[1] - base[1], tip[2] - base[2]))))
    nrm = _norm(_lerp3(face, (0.0, 0.0, 1.0), _GRASS_UP_BEND))

    def colour(t):
        rgb = _lerp3(_ROOT, mid_col, min(1.0, t * 2.2)) if t < 0.45 else \
            _lerp3(mid_col, tip_col, (t - 0.45) / 0.55)
        return (rgb[0], rgb[1], rgb[2], t)

    idx = []
    for centre, half_w, t in rows:
        left = buf.add(_add(centre, side, -half_w), nrm, colour(t), (0.0, t))
        right = buf.add(_add(centre, side, half_w), nrm, colour(t), (1.0, t))
        idx.append((left, right))
    top = buf.add(tip, nrm, colour(tip_t), (0.5, 1.0))
    for (l0, r0), (l1, r1) in zip(idx, idx[1:]):
        buf.triangles.append((l0, r0, r1))
        buf.triangles.append((l0, r1, l1))
    l_last, r_last = idx[-1]
    buf.triangles.append((l_last, r_last, top))


def _seed_stalk(buf, rng, base, height):
    """A thin stalk carrying an elongated seed head -- the silhouette that
    makes a field read as long grass rather than lawn."""
    facing = rng.uniform(0.0, math.tau)
    lean_dir = (math.cos(facing + 1.2), math.sin(facing + 1.2), 0.0)
    _blade(buf, rng, base, height * 0.82, 0.45, facing, lean_dir,
           rng.uniform(0.05, 0.18), 3, _STALK, _STALK)
    # Seed head: three crossed spindles near the top.
    lean = 0.12
    head_base = (base[0] + lean_dir[0] * lean * height * 0.7,
                 base[1] + lean_dir[1] * lean * height * 0.7,
                 base[2] + height * 0.74)
    for k in range(3):
        _blade(buf, rng, head_base, height * 0.26, 1.4, facing + k * math.pi / 3,
               lean_dir, 0.10, 2, _SEED, _SEED)


def build_grass_patch(recipe: GrassPatchRecipe) -> MeshBuffers:
    rng = random.Random(recipe.seed)
    buf = MeshBuffers()
    for _ in range(recipe.blades):
        # Denser toward the centre, and taller there: a mound, not a cylinder.
        r = recipe.radius_cm * math.sqrt(rng.random()) ** 1.15
        a = rng.uniform(0.0, math.tau)
        base = (r * math.cos(a), r * math.sin(a), 0.0)
        edge = r / recipe.radius_cm
        height = recipe.height_cm * rng.uniform(0.62, 1.0) * (1.0 - 0.30 * edge)
        # Blades lean outward from the centre (more at the rim), plus scatter.
        out = a + rng.uniform(-0.9, 0.9)
        lean_dir = (math.cos(out), math.sin(out), 0.0)
        lean = rng.uniform(0.08, 0.30) + 0.35 * edge
        dry = rng.random() < recipe.dry_share
        _blade(buf, rng, base, height, rng.uniform(*recipe.blade_width_cm),
               rng.uniform(0.0, math.tau), lean_dir, lean, recipe.segments,
               _DRY_MID if dry else _GREEN_MID, _DRY_TIP if dry else _GREEN_TIP)
    for _ in range(recipe.seed_stalks):
        r = recipe.radius_cm * 0.6 * math.sqrt(rng.random())
        a = rng.uniform(0.0, math.tau)
        _seed_stalk(buf, rng, (r * math.cos(a), r * math.sin(a), 0.0),
                    recipe.height_cm * rng.uniform(1.0, 1.12))
    return buf


# ─── Bush ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BushRecipe:
    """One bush mesh: woody stems under an ellipsoid shell of leaves."""
    name: str
    seed: int
    leaves: int
    stems: int
    radius_cm: float          # crown half-width
    height_cm: float          # crown top
    crown_base_cm: float      # lowest leaves
    leaf_len_cm: tuple = (6.0, 10.0)
    leaf_width_ratio: float = 0.45


_LEAF_DARK = (0.012, 0.030, 0.010)
_LEAF_MID = (0.035, 0.075, 0.020)
_LEAF_LIGHT = (0.070, 0.120, 0.035)
_BARK = (0.045, 0.032, 0.020)

# Leaf normals bent toward the crown's outward direction. Same reasoning as
# the grass: a thousand randomly facing leaves lit by their own normals is
# noise; lit as one rounded volume it is a bush.
_LEAF_SPHERE_BEND = 0.65


def _stem(buf, base, tip, r0, r1, sides=3, segments=3, sag=0.0):
    """A tapered prism along a gently arched path from ``base`` to ``tip``."""
    axis = _norm((tip[0] - base[0], tip[1] - base[1], tip[2] - base[2]))
    ref = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.95 else (1.0, 0.0, 0.0)
    u = _norm(_cross(axis, ref))
    v = _cross(axis, u)
    rings = []
    for s in range(segments + 1):
        t = s / segments
        centre = _lerp3(base, tip, t)
        centre = (centre[0], centre[1], centre[2] - sag * 4.0 * t * (1.0 - t))
        radius = r0 + (r1 - r0) * t
        ring = []
        for k in range(sides):
            ang = math.tau * k / sides
            d = _add((math.cos(ang) * u[0], math.cos(ang) * u[1], math.cos(ang) * u[2]),
                     v, math.sin(ang))
            ring.append(buf.add(_add(centre, d, radius), _norm(d),
                                (_BARK[0], _BARK[1], _BARK[2], 0.2 + 0.5 * t),
                                (k / sides, t)))
        rings.append(ring)
    for r0_idx, r1_idx in zip(rings, rings[1:]):
        for k in range(sides):
            a, b = r0_idx[k], r0_idx[(k + 1) % sides]
            c, d = r1_idx[(k + 1) % sides], r1_idx[k]
            buf.triangles.append((a, b, c))
            buf.triangles.append((a, c, d))


def _leaf(buf, rng, centre, outward, length, width, depth):
    """A four-point leaf (two triangles) facing roughly ``outward``."""
    # Random in-plane direction, tilted so leaves droop a little.
    ref = (0.0, 0.0, 1.0) if abs(outward[2]) < 0.9 else (1.0, 0.0, 0.0)
    t1 = _norm(_cross(outward, ref))
    t2 = _cross(outward, t1)
    ang = rng.uniform(0.0, math.tau)
    along = _norm(_add((t1[0] * math.cos(ang), t1[1] * math.cos(ang), t1[2] * math.cos(ang)),
                       t2, math.sin(ang)))
    along = _norm((along[0], along[1], along[2] - 0.35))
    across = _norm(_cross(outward, along))
    face = _norm(_cross(along, across))
    if face[0] * outward[0] + face[1] * outward[1] + face[2] * outward[2] < 0:
        face = (-face[0], -face[1], -face[2])
    nrm = _norm(_lerp3(face, outward, _LEAF_SPHERE_BEND))

    # Inner leaves dark, outer lit; depth in [0 inner, 1 shell].
    rgb = _lerp3(_LEAF_DARK, _LEAF_MID, depth)
    rgb = _lerp3(rgb, _LEAF_LIGHT, max(0.0, depth - 0.6) * rng.uniform(0.8, 2.2))
    col = (rgb[0], rgb[1], rgb[2], 0.25 + 0.75 * depth)

    stem_end = _add(centre, along, -length * 0.5)
    tip = _add(centre, along, length * 0.5)
    left = _add(centre, across, -width * 0.5)
    right = _add(centre, across, width * 0.5)
    i0 = buf.add(stem_end, nrm, col, (0.5, 0.0))
    i1 = buf.add(right, nrm, col, (1.0, 0.5))
    i2 = buf.add(tip, nrm, col, (0.5, 1.0))
    i3 = buf.add(left, nrm, col, (0.0, 0.5))
    buf.triangles.append((i0, i1, i2))
    buf.triangles.append((i0, i2, i3))


def build_bush(recipe: BushRecipe) -> MeshBuffers:
    rng = random.Random(recipe.seed)
    buf = MeshBuffers()
    crown_mid = (recipe.height_cm + recipe.crown_base_cm) * 0.5
    crown_half_h = (recipe.height_cm - recipe.crown_base_cm) * 0.5

    # Woody stems fanning from the root to points inside the crown.
    for i in range(recipe.stems):
        a = math.tau * i / recipe.stems + rng.uniform(-0.3, 0.3)
        spread = rng.uniform(0.35, 0.75) * recipe.radius_cm
        tip = (spread * math.cos(a), spread * math.sin(a),
               crown_mid + crown_half_h * rng.uniform(-0.2, 0.6))
        base = (rng.uniform(-4, 4), rng.uniform(-4, 4), -2.0)
        _stem(buf, base, tip, rng.uniform(0.9, 1.4), 0.3, sag=rng.uniform(2.0, 6.0))

    # Leaves on an ellipsoid, weighted to the outer shell (the silhouette) but
    # with enough inside that the bush is not a hollow balloon when close.
    for _ in range(recipe.leaves):
        while True:
            d = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            m2 = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
            if 1e-4 < m2 <= 1.0:
                break
        dirn = _norm(d)
        depth = max(0.25, rng.random() ** 0.45)  # most leaves near the shell
        # Flatten the bottom so the crown sits on its stems, not on a point.
        dz = dirn[2] if dirn[2] > -0.55 else -0.55 + (dirn[2] + 0.55) * 0.3
        centre = (dirn[0] * recipe.radius_cm * depth,
                  dirn[1] * recipe.radius_cm * depth,
                  crown_mid + dz * crown_half_h * depth)
        outward = _norm((dirn[0], dirn[1], dz * 0.8 + 0.2))
        length = rng.uniform(*recipe.leaf_len_cm)
        _leaf(buf, rng, centre, outward, length,
              length * recipe.leaf_width_ratio * rng.uniform(0.8, 1.2), depth)
    return buf


# ─── The recipes the game ships ──────────────────────────────────────────────

# Two patch variants so neighbouring patches do not repeat. A is lush and
# even; B is looser with seed heads standing out of it. Both authored at knee
# height, so planting scales them by ~0.8-1.1 rather than stretching them.
GRASS_PATCH_A = GrassPatchRecipe("SM_GrassPatch_A", seed=1101, blades=320,
                                 radius_cm=55.0, height_cm=58.0)
GRASS_PATCH_B = GrassPatchRecipe("SM_GrassPatch_B", seed=2202, blades=270,
                                 radius_cm=52.0, height_cm=55.0,
                                 blade_width_cm=(1.6, 2.8), seed_stalks=12,
                                 dry_share=0.24)

BUSH_ROUND = BushRecipe("SM_Bush_Round", seed=3303, leaves=1650, stems=9,
                        radius_cm=85.0, height_cm=120.0, crown_base_cm=18.0,
                        leaf_len_cm=(11.0, 17.0))
BUSH_TALL = BushRecipe("SM_Bush_Tall", seed=4404, leaves=1500, stems=7,
                       radius_cm=65.0, height_cm=165.0, crown_base_cm=35.0,
                       leaf_len_cm=(12.0, 18.0), leaf_width_ratio=0.40)

GRASS_RECIPES = (GRASS_PATCH_A, GRASS_PATCH_B)
BUSH_RECIPES = (BUSH_ROUND, BUSH_TALL)

# Where the built assets live.
PROC_FOLIAGE_DIR = "/Game/Forest/Procedural"
PROC_MATERIAL = f"{PROC_FOLIAGE_DIR}/M_ProcFoliage"
MI_GRASS = f"{PROC_FOLIAGE_DIR}/MI_ProcGrass"
MI_BUSH = f"{PROC_FOLIAGE_DIR}/MI_ProcBush"

# Triangle budgets per mesh. Nanite simplifies with distance, but every patch
# near the camera is drawn at full detail, and there are hundreds of them.
GRASS_TRI_BUDGET = 1800
BUSH_TRI_BUDGET = 4000


def asset_path(recipe):
    return f"{PROC_FOLIAGE_DIR}/{recipe.name}.{recipe.name}"


def build(recipe):
    return build_grass_patch(recipe) if isinstance(recipe, GrassPatchRecipe) \
        else build_bush(recipe)


_HEIGHTS = {}


def mesh_height_cm(recipe):
    """Authored bounds height, cached: the specs read it at import time."""
    if recipe.name not in _HEIGHTS:
        _HEIGHTS[recipe.name] = build(recipe).height
    return _HEIGHTS[recipe.name]
