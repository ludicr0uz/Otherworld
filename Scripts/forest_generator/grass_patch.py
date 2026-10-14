"""The grass patch: copies of the library clump, turned and offset, merged
into one mesh 1.1-1.2 m across. Pure Python (no ``unreal``);
forest_import/grass_patch.py builds it from these numbers.

Why a patch (G3). The clump (undergrowth_meshes.GRASS_02_09) is 54 cm across;
G1 planted it 1.55-2.10x wide on the 200 m map, which spread the same blades
thinner into flat spiky stars. No mesh of the pack is a wide, knee-high patch
of the same grass (the widest, lowGrass_06_02, is 1.1 m but 93 cm tall and
another grass), so the patch is built: seven clumps unstretched, so its blades
are as thick as the clump's own.

Its LODs are built from the clump's own lower LODs (render data: the pack's
LOD1-3 are engine reductions with no source geometry), and its last LOD costs
what the clump's does, because nearly every grass instance on screen is drawn
at its last LOD (the clump reaches it about 5 m out):

    LOD0  7 copies of the clump's LOD2   (7 x 538 = 3,766 triangles)
    LOD1  7 copies of its LOD3           (7 x 269 = 1,883), every blade the
          clump keeps at a distance, unstretched
    LOD2  3 copies of its LOD3, 1.6x wide (807)
    LOD3  1 copy of its LOD3, 2.4x wide  (269: the clump's last LOD)

Nearer than 6 m nothing is stretched; past 10 m the patch is G1's wide clump,
where its stars are a few pixels and cannot be told from blades.

The wind. The pack's material bends each blade about its own pivot (Pivot
Painter 2): the mesh's second UV set points at a texel of a small texture
holding that blade's pivot in the mesh's space and its parent's index, and
of a second holding its axis and length. A copy turned and moved needs its
blades' pivots turned and moved too, so the patch has its own pair of
textures: one band of rows per placement (a copy's transform), the clump's
texels transformed into it, and each copy's second UV set moved to its band.
"""

import math
import struct
from dataclasses import dataclass

from .grass_look import PATCH_MATERIAL
from .undergrowth_meshes import GRASS_02_09, GRASS_PATCH

MESH = GRASS_PATCH.mesh
FOLDER = MESH.rsplit("/", 1)[0]
# The patch's material: the dark grass (grass_look.GRASS_MATERIAL) with the
# patch's own pivot textures. A child of it, so its colours are those.
MATERIAL = PATCH_MATERIAL
PIVOT_TEXTURE = f"{FOLDER}/T_Grass_Patch_PIV"
AXIS_TEXTURE = f"{FOLDER}/T_Grass_Patch_VEC"
# The parameters of the pack's material that name the two textures.
PIVOT_PARAM = "Position and Index Texture"
AXIS_PARAM = "X-Vector And X-Extent Texture"

SOURCE = GRASS_02_09.mesh
SOURCE_PIVOT_TEXTURE = ("/Game/PN_GrassLibrary/Textures/grassTextures/"
                        "PivPainterTextures/grass_02_09_PIV")
SOURCE_AXIS_TEXTURE = ("/Game/PN_GrassLibrary/Textures/grassTextures/"
                       "PivPainterTextures/grass_02_09_VEC")
# The clump's textures: 89 x 2 texels, one per blade (178).
TEXELS_WIDE, TEXELS_HIGH = 89, 2
# Its LODs' triangles, as measured (render data).
SOURCE_LOD_TRIANGLES = (2152, 1076, 538, 269)
# Pivot Painter 2 stores a blade's length as alpha x this, in 8 bits.
EXTENT_SCALE_CM = 2048.0
# An index is stored as the half float whose bits are index + this.
INDEX_BIAS = 1024


@dataclass(frozen=True)
class Placement:
    """One copy's transform: a turn, a move and a widening (never taller)."""
    yaw_deg: float
    x_cm: float
    y_cm: float
    width: float = 1.0


# Six round one, 40 cm out: a clump is about 50 cm across, so neighbours
# overlap and the patch is 1.1 by 1.2 m. The turns are uneven so no two
# copies show the same side.
_RING_CM = 40.0
_RING = tuple(Placement(yaw, _RING_CM * math.cos(math.radians(a)),
                        _RING_CM * math.sin(math.radians(a)))
              for a, yaw in ((30, 47), (90, 199), (150, 113), (210, 307),
                             (270, 251), (330, 163)))
DENSE = (Placement(0.0, 0.0, 0.0),) + _RING
# Three, 30 cm out and 1.6x wide: 0.86 m each, the patch's 1.4 m.
THREE = tuple(Placement(yaw, 30.0 * math.cos(math.radians(a)),
                        30.0 * math.sin(math.radians(a)), 1.6)
              for a, yaw in ((90, 20), (210, 140), (330, 260)))
# One, as wide as the patch.
ONE = (Placement(75.0, 0.0, 0.0, 2.4),)


@dataclass(frozen=True)
class PatchLod:
    source_lod: int          # the clump's LOD each copy is
    placements: tuple
    from_m: float            # drawn from this far (nominal; see screen_sizes)


# Near: the patch is 2.2 to the m2, so about 60 instances stand within 3 m,
# 250 within 6 m and 700 within 10 m; past that each costs what a clump did.
LODS = (
    PatchLod(2, DENSE, 0.0),
    PatchLod(3, DENSE, 3.0),
    PatchLod(3, THREE, 6.0),
    PatchLod(3, ONE, 10.0),
)

# Every distinct placement, in the order of their bands in the textures.
PLACEMENTS = tuple(dict.fromkeys(p for lod in LODS for p in lod.placements))


def lod_triangles():
    """The triangles each patch LOD is built with."""
    return [SOURCE_LOD_TRIANGLES[lod.source_lod] * len(lod.placements) for lod in LODS]


def band(placement):
    """The placement's band of rows in the patch's textures."""
    return PLACEMENTS.index(placement)


def texture_size():
    """(wide, high) of the patch's textures: a band of the clump's per placement."""
    return TEXELS_WIDE, TEXELS_HIGH * len(PLACEMENTS)


def uv_scale_and_offset(placement):
    """The second UV set's (scale V, then add V) that moves a copy's texels
    into its band; U is unchanged."""
    n = len(PLACEMENTS)
    return 1.0 / n, band(placement) / n


def _matrix(p):
    """Rows of the 3x3 that widens (X and Y, before the turn), then turns."""
    c, s = math.cos(math.radians(p.yaw_deg)), math.sin(math.radians(p.yaw_deg))
    w = p.width
    return ((c * w, -s * w, 0.0), (s * w, c * w, 0.0), (0.0, 0.0, 1.0))


def _apply(m, v):
    return tuple(sum(m[r][i] * v[i] for i in range(3)) for r in range(3))


def move_point(p, xyz):
    """A point of the clump where the copy puts it."""
    x, y, z = _apply(_matrix(p), xyz)
    return x + p.x_cm, y + p.y_cm, z


def pack_index(index):
    """Pivot Painter 2's index as the float its texture holds."""
    return struct.unpack("<e", struct.pack("<H", index + INDEX_BIAS))[0]


def unpack_index(value):
    return struct.unpack("<H", struct.pack("<e", value))[0] - INDEX_BIAS


def move_pivot(p, rgba):
    """One texel of the pivot texture, for the copy: its pivot moved, its
    parent's index moved into the copy's band."""
    x, y, z = move_point(p, rgba[:3])
    parent = unpack_index(rgba[3]) + band(p) * TEXELS_WIDE * TEXELS_HIGH
    return x, y, z, pack_index(parent)


def move_axis(p, rgba):
    """One texel of the axis texture (0-1 colour: axis * 0.5 + 0.5, length /
    EXTENT_SCALE_CM), for the copy: the axis turned and widened, the length
    stretched with it."""
    axis = tuple(c * 2.0 - 1.0 for c in rgba[:3])
    moved = _apply(_matrix(p), axis)
    length = math.sqrt(sum(c * c for c in moved)) or 1.0
    unit = tuple(c / length for c in moved)
    extent = min(1.0, rgba[3] * length)
    return tuple(min(1.0, max(0.0, c * 0.5 + 0.5)) for c in unit) + (extent,)


def screen_sizes(radius_cm, projection=1.78):
    """The LOD screen sizes that switch at each LOD's ``from_m``. A HISM
    leaves a LOD at the distance projection x radius / screen size (the
    projection's larger scale: 1.78 for a 90-degree view at 16:9), so these
    are nominal: another field of view moves them all alike."""
    sizes = []
    for lod in LODS:
        sizes.append(2.0 if lod.from_m <= 0.0 else projection * radius_cm / (lod.from_m * 100.0))
    return sizes
