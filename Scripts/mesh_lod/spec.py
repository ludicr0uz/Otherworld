"""What a game-ready mesh is built to: the defaults, and the arithmetic that
turns them into numbers for one mesh. Pure Python (no ``unreal``).

A job is one source mesh and a LodSpec. Every field has a default, and a job
overrides only what it names (jobs.py, or --set on the command line).

Triangles. LOD0 is ``lod0_triangles`` and each mesh LOD after it is
``lod_ratio`` of the one before; a source with fewer keeps what it has. A
LOD's budget is shared among the material slots by their share of the source,
and no slot is cut under ``slot_floor`` (itself scaled down the chain): a
trunk is 800 triangles of 200 thousand and the first thing seen at eye level.

Foliage. A slot whose material is masked is foliage: thousands of
disconnected pieces (a leaf, a needle card). It is cut as
forest_generator/tree_meshes.py found it must be: each piece is simplified
down to ``triangles_per_piece`` and, when that is not enough, pieces are
dropped and the survivors grown until the slot covers ``foliage_area`` of
what it did. Which pieces go is a hash of the piece, spread evenly through
the crown.

Distances. A LOD is chosen by screen size, which depends on how big the mesh
is, so the spec says it in metres (``lod_distances_m``: where LOD1, LOD2, ...
and the impostor start) and screen_sizes() converts with the mesh's radius,
``planted_scale`` and the camera. r.StaticMeshLODDistanceScale moves them all.

The impostor is ``impostor_planes`` upright cards through the trunk, each a
picture of the mesh from straight on (atlas.py lays them out), and it is the
last LOD.
"""

import hashlib
import math
from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True)
class LodSpec:
    lod0_triangles: int = 40_000
    lod_ratio: float = 0.4
    mesh_lods: int = 3
    slot_floor: int = 600
    triangles_per_piece: float = 4.0
    foliage_area: float = 1.0
    foliage_slots: tuple = ()        # empty: the slots whose material is masked
    lod_distances_m: tuple = (30.0, 60.0, 110.0)
    planted_scale: float = 1.0
    fov_deg: float = 90.0
    aspect: float = 16.0 / 9.0
    impostor: bool = True
    impostor_planes: int = 3
    atlas_px: int = 1024
    capture_px: int = 1024           # the longer side of one plane's capture
    impostor_brightness: float = 1.0
    impostor_subsurface: float = 0.4
    impostor_mask_clip: float = 0.4
    revision: int = 1                # bump to rebuild when the builder changes

    @property
    def lod_count(self):
        return self.mesh_lods + (1 if self.impostor else 0)

    @property
    def stamp(self):
        return hashlib.sha1(repr(self).encode()).hexdigest()[:16]

    def problems(self):
        """Why this spec cannot be built; empty when it can."""
        out = []
        if self.mesh_lods < 1:
            out.append("mesh_lods must be at least 1")
        if not 0.0 < self.lod_ratio < 1.0:
            out.append("lod_ratio must be between 0 and 1")
        if len(self.lod_distances_m) != self.lod_count - 1:
            out.append(f"lod_distances_m needs {self.lod_count - 1} distances "
                       f"(one per LOD after the first), has {len(self.lod_distances_m)}")
        elif list(self.lod_distances_m) != sorted(set(self.lod_distances_m)):
            out.append("lod_distances_m must grow")
        if self.impostor and self.impostor_planes < 2:
            out.append("impostor_planes must be at least 2")
        if self.atlas_px & (self.atlas_px - 1):
            out.append("atlas_px must be a power of two (the atlas needs mips)")
        return out


def with_overrides(spec, overrides):
    """``spec`` with the fields of ``overrides`` ({name: value}) replaced. A
    value is coerced to the field's own type, so "60000" from a command line
    and [20, 40] from JSON both do."""
    kinds = {f.name: type(getattr(spec, f.name)) for f in fields(spec)}
    clean = {}
    for name, value in overrides.items():
        if name not in kinds:
            raise ValueError(f"no such setting: {name} (there are: {', '.join(sorted(kinds))})")
        kind = kinds[name]
        if kind is tuple:
            if isinstance(value, str):
                value = [v for v in value.replace(",", " ").split() if v]
            value = tuple(float(v) if name == "lod_distances_m" else int(v) for v in value)
        elif kind is bool:
            if isinstance(value, str):
                value = value.strip().lower() in ("1", "true", "yes", "on")
            value = bool(value)
        else:
            value = kind(value)
        clean[name] = value
    return replace(spec, **clean)


def to_dict(spec):
    return asdict(spec)


def from_dict(data):
    return with_overrides(LodSpec(), data)


def lod_targets(spec, source_triangles):
    """The triangle budget of each mesh LOD."""
    first = min(spec.lod0_triangles, source_triangles)
    return [max(1, int(first * spec.lod_ratio ** i)) for i in range(spec.mesh_lods)]


def slot_budgets(spec, slot_triangles, target, lod):
    """``target`` shared among the slots ({slot: source triangles}) by their
    share, none under its floor. The floors may take the total over
    ``target``: the floor wins."""
    total = sum(slot_triangles.values())
    if total <= target:
        return dict(slot_triangles)
    floor = max(12, int(spec.slot_floor * spec.lod_ratio ** lod))
    budgets = {}
    for slot, triangles in slot_triangles.items():
        share = int(target * triangles / total)
        budgets[slot] = min(triangles, max(share, floor))
    return budgets


@dataclass(frozen=True)
class FoliageCut:
    keep_pieces: float               # the share of the pieces kept
    triangles: int                   # what the kept pieces are simplified to
    simplify: bool                   # False: the pieces are left as they are


def foliage_cut(spec, triangles, pieces, target):
    """How a foliage slot of ``pieces`` pieces gets from ``triangles`` to
    ``target``: fewer triangles a piece first, fewer pieces after."""
    if triangles <= target or pieces <= 0:
        return FoliageCut(1.0, triangles, False)
    now = triangles / pieces
    per_piece = min(now, max(spec.triangles_per_piece, target / pieces))
    keep = min(1.0, target / (pieces * per_piece))
    return FoliageCut(keep, int(target), per_piece < now - 1e-6)


def screen_size(spec, radius_cm, distance_m):
    """The screen size (UE's: 1.0 fills the view) of a sphere of ``radius_cm``
    planted at ``planted_scale``, ``distance_m`` away. It is
    ComputeBoundsScreenSize: twice the radius over the distance, times half
    the larger projection scale. Over 1.0 for a tree taller than the view,
    which the engine compares like any other."""
    across = 1.0 / math.tan(math.radians(spec.fov_deg) / 2.0)
    multiple = 0.5 * max(across, across * spec.aspect)
    return 2.0 * multiple * radius_cm * spec.planted_scale / (distance_m * 100.0)


def screen_sizes(spec, radius_cm):
    """One per LOD: LOD0's, then the size at each distance. LOD0's is only
    ever a ceiling, so it is 1.0 or whatever clears LOD1's."""
    rest = [screen_size(spec, radius_cm, d) for d in spec.lod_distances_m]
    return [max(1.0, rest[0] * 2.0) if rest else 1.0] + rest
