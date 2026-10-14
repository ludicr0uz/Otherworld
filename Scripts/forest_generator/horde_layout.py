"""
horde_layout.py — The Horde Survival level's shape: a dense ring of forest, a
sparse clearing in the middle, and a fort of chest-high rocks at its centre
with three openings. Pure Python (no ``unreal``).

A level named in HORDE_LEVELS is generated from this in place of the forest's
radial scatter (generate_forest_level.py): its trees come from
``scatter_horde_trees``, its bushes keep out of the fort, and its fort's rocks
from ``fort_rocks`` are placed by forest_import/fort.py, which also verifies
them in the editor (a ray across the ring at every degree: the wall stops it,
an opening lets it through).

The numbers, each with its reason:
- The ring is as dense as the middle of the 1 km map, measured off that map's
  generated trees: 370 inside 100 m of its centre, 118/ha (its radial scatter
  thins out with distance, 18/ha at the edge). DENSE_TREES_PER_HA is 120.
- The clearing is 60 m across the radius and feathers into the ring over
  15 m, so the forest's edge is not a drawn circle. It keeps 12 trees a
  hectare: about a dozen, scarce, a few for cover.
- The fort's rocks stand on a 13 m ring (26 m across, room for a few players
  and a fire) and nothing grows within 8 m outside it, so a shooter on the
  wall sees what comes. The terrain is flat to 90 m on a 400 m map
  (terrain._make_large_elevation_fn, 45 m x s), so the fort is on level ground.
- A rock shows 125-140 cm above the ground (chest high on the 1.8 m
  character) and is sunk 20 cm so its uneven base never shows daylight.
- Each opening is at least 4 m clear at knee height: two zombies abreast,
  and a narrow enough front to hold. The rocks are rounded, so that is the
  gap between their footprint boxes (opening_box_cm, 3.4 m) and about 0.9 m
  more: measured 5.0-5.7 m at 30 cm with boxes 4.2-4.6 m apart. They face 0, 120 and 240 degrees; the first is ahead of the
  player start (yaw 0).
- Neighbouring rocks overlap by at least 35 % of their length: they are rounded
  scans: at 25 % two notches 11 and 34 cm wide were left at waist height.
"""

import math
import random
from dataclasses import dataclass

from .terrain import get_exact_mesh_z
from .tree_placement import (
    DEFAULT_TREE_SPECS, MAX_SPACING_REDRAWS, MIN_TREE_SPACING_CM, PlacedTree,
    _too_close)


@dataclass(frozen=True)
class RockMesh:
    """One rock the fort is built of, and its bounding box as the mesh holds
    it (measured in the editor: the set's rocks keep the scan's layout, so
    their pivots are off their middles)."""
    path: str
    min_cm: tuple
    max_cm: tuple


_MOSS = "/Game/Forest/Scanned/rock_moss_set_01/rock_moss_set_01_1k/StaticMeshes"
# The Poly Haven moss rock set, committed, 1.9-3.3 k triangles each, collision
# complex-as-simple. Planted as they are: nothing writes to them.
FORT_ROCK_MESHES = (
    RockMesh(f"{_MOSS}/rock_moss_set_01_rock01", (-391.4, -382.4, -65.7), (-167.6, -45.5, 81.6)),
    RockMesh(f"{_MOSS}/rock_moss_set_01_rock02", (-127.3, -376.7, -46.6), (138.2, -50.3, 79.6)),
    RockMesh(f"{_MOSS}/rock_moss_set_01_rock03", (198.2, -314.6, -41.1), (409.1, -106.7, 68.9)),
    RockMesh(f"{_MOSS}/rock_moss_set_01_rock04", (-365.0, 69.0, -66.1), (-152.3, 265.5, 110.7)),
    RockMesh(f"{_MOSS}/rock_moss_set_01_rock05", (-71.1, 12.6, -57.3), (110.7, 312.5, 63.3)),
    RockMesh(f"{_MOSS}/rock_moss_set_01_rock06", (159.9, 9.7, -52.8), (372.5, 285.4, 73.4)),
)


@dataclass(frozen=True)
class HordeLayout:
    world_size_m: float = 400.0
    dense_trees_per_ha: float = 120.0
    sparse_trees_per_ha: float = 12.0
    clearing_radius_cm: float = 6_000.0
    clearing_feather_cm: float = 1_500.0
    fort_radius_cm: float = 1_300.0
    fort_clear_cm: float = 800.0          # nothing grows this far outside the ring
    opening_cm: float = 400.0             # clear at knee height, as the verifier measures it
    opening_box_cm: float = 340.0         # between the two rocks' footprint boxes
    opening_yaws_deg: tuple = (0.0, 120.0, 240.0)
    rock_visible_cm: tuple = (125.0, 140.0)
    rock_sink_cm: float = 20.0
    rock_overlap_min: float = 0.35
    edge_fraction: float = 0.95           # trees inside this share of the half-size, as the forest's

    @property
    def keep_out_cm(self):
        return self.fort_radius_cm + self.fort_clear_cm


HORDE_LEVELS = {"Lvl_Horde_Survival": HordeLayout()}


def layout_for(level_name):
    """The level's horde layout, or None for a forest level."""
    return HORDE_LEVELS.get(level_name)


# ─── Trees ───────────────────────────────────────────────────────────────────

def tree_density_at(layout, x, y):
    """Trees a hectare the layout asks for at (x, y), in cm from the centre."""
    r = math.hypot(x, y)
    if r < layout.keep_out_cm:
        return 0.0
    t = (r - layout.clearing_radius_cm) / layout.clearing_feather_cm
    t = min(1.0, max(0.0, t))
    return layout.sparse_trees_per_ha + t * (layout.dense_trees_per_ha
                                             - layout.sparse_trees_per_ha)


def scatter_horde_trees(layout, world_size_cm, grid_z, grid_size, seed=42,
                        tree_specs=None):
    """Trees by the layout's density field: candidates drawn evenly over the
    box at the densest rate and kept in proportion to the field there, each
    one's species drawn by the specs' own shares. The spacing is the forest's."""
    specs = tree_specs or DEFAULT_TREE_SPECS
    rng = random.Random(seed ^ 0x40DE)
    half = world_size_cm / 2.0 * layout.edge_fraction
    box_ha = (2.0 * half / 100.0) ** 2 / 10_000.0
    peak = layout.dense_trees_per_ha
    weights = [s.count_per_hectare for s in specs]
    placed, cells = [], {}
    for _ in range(int(round(peak * box_ha))):
        tx, ty = _draw(rng, half)
        if rng.random() * peak >= tree_density_at(layout, tx, ty):
            continue
        spec = rng.choices(specs, weights)[0]
        for _attempt in range(MAX_SPACING_REDRAWS):
            if not _too_close(cells, tx, ty):
                break
            tx, ty = _accepted_draw(rng, half, layout)
        else:
            continue
        cells.setdefault((int(math.floor(tx / MIN_TREE_SPACING_CM)),
                          int(math.floor(ty / MIN_TREE_SPACING_CM))), []).append((tx, ty))
        tz = get_exact_mesh_z(tx, ty, grid_z, grid_size, world_size_cm)
        scale = rng.uniform(spec.scale_min, spec.scale_max)
        sink = spec.sink_base_cm * (scale / spec.sink_ref_scale)
        placed.append(PlacedTree(spec_name=spec.name, x=tx, y=ty, terrain_z=tz,
                                 placed_z=tz - sink, yaw_deg=rng.uniform(0.0, 360.0),
                                 scale=scale, sink_cm=sink))
    return placed


def _draw(rng, half):
    return rng.uniform(-half, half), rng.uniform(-half, half)


def _accepted_draw(rng, half, layout):
    """A point drawn by the field (the redraw of one that stood too close)."""
    while True:
        x, y = _draw(rng, half)
        if rng.random() * layout.dense_trees_per_ha < tree_density_at(layout, x, y):
            return x, y


# ─── The fort ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PlacedRock:
    """One rock of the fort's wall. (x, y, z) is the actor's location (the
    mesh's pivot), (cx, cy) the middle of its footprint on the ring; the
    footprint is a box half_len along the ring and half_depth across it,
    turned by ``tangent_deg``."""
    mesh_path: str
    x: float
    y: float
    z: float
    yaw_deg: float
    scale: float
    cx: float
    cy: float
    tangent_deg: float
    half_len: float
    half_depth: float
    terrain_z: float
    top_z: float
    arc: int                  # which stretch of wall, between two openings


def _gap_half_angle(layout):
    # 60 cm a side past the opening: a footprint's inner corners reach
    # further round the ring than its middle does, and a rock stands up to
    # 30 cm off the ring.
    return (layout.opening_box_cm / 2.0 + 60.0) / layout.fort_radius_cm


def _pick(rng, layout):
    mesh = rng.choice(FORT_ROCK_MESHES)
    ext = [mesh.max_cm[i] - mesh.min_cm[i] for i in range(3)]
    scale = (rng.uniform(*layout.rock_visible_cm) + layout.rock_sink_cm) / ext[2]
    long_is_x = ext[0] >= ext[1]
    return mesh, scale, long_is_x, max(ext[0], ext[1]) * scale, min(ext[0], ext[1]) * scale


def _overlap_for(picks, arc_cm):
    """The overlap that makes ``picks`` span ``arc_cm`` exactly, each pair of
    neighbours overlapping by that share of their mean length."""
    lengths = [p[3] for p in picks]
    if len(lengths) < 2:
        return -1.0
    pairs = sum((a + b) / 2.0 for a, b in zip(lengths, lengths[1:]))
    return 1.0 - (arc_cm - lengths[0] / 2.0 - lengths[-1] / 2.0) / pairs


def fort_rocks(layout, world_size_cm, grid_z, grid_size, seed=42):
    """The rocks of the fort's wall, stretch by stretch between the openings."""
    rng = random.Random(seed ^ 0xF027)
    radius = layout.fort_radius_cm
    yaws = sorted(layout.opening_yaws_deg)
    half_gap = _gap_half_angle(layout)
    rocks = []
    for k, yaw in enumerate(yaws):
        a0 = math.radians(yaw) + half_gap
        a1 = math.radians(yaws[(k + 1) % len(yaws)] + (360.0 if k == len(yaws) - 1 else 0.0)) - half_gap
        arc_cm = (a1 - a0) * radius
        picks = [_pick(rng, layout), _pick(rng, layout)]
        while _overlap_for(picks, arc_cm) < layout.rock_overlap_min:
            picks.append(_pick(rng, layout))
        overlap = _overlap_for(picks, arc_cm)
        s = picks[0][3] / 2.0
        for i, pick in enumerate(picks):
            if i:
                s += (picks[i - 1][3] + pick[3]) / 2.0 * (1.0 - overlap)
            rocks.append(_place(rng, layout, pick, a0 + s / radius, k,
                                world_size_cm, grid_z, grid_size))
    return rocks


def _place(rng, layout, pick, phi, arc, world_size_cm, grid_z, grid_size):
    mesh, scale, long_is_x, length, depth = pick
    r = layout.fort_radius_cm + rng.uniform(-30.0, 30.0)
    cx, cy = r * math.cos(phi), r * math.sin(phi)
    tangent = math.degrees(phi) + 90.0
    yaw = (tangent if long_is_x else tangent - 90.0) + rng.uniform(-6.0, 6.0)
    yaw += rng.choice((0.0, 180.0))
    # The pivot is off the mesh's middle: put the middle on the ring.
    mx = (mesh.min_cm[0] + mesh.max_cm[0]) / 2.0 * scale
    my = (mesh.min_cm[1] + mesh.max_cm[1]) / 2.0 * scale
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    ground = get_exact_mesh_z(cx, cy, grid_z, grid_size, world_size_cm)
    z = ground - layout.rock_sink_cm - mesh.min_cm[2] * scale
    return PlacedRock(mesh_path=mesh.path, x=cx - (mx * c - my * s),
                      y=cy - (mx * s + my * c), z=z, yaw_deg=yaw % 360.0,
                      scale=scale, cx=cx, cy=cy, tangent_deg=tangent,
                      half_len=length / 2.0, half_depth=depth / 2.0,
                      terrain_z=ground, top_z=z + mesh.max_cm[2] * scale, arc=arc)


def fort_rock_data(rocks):
    """What the generated scripts carry of each PlacedRock."""
    return [{"mesh": r.mesh_path, "x": round(r.x, 2), "y": round(r.y, 2),
             "z": round(r.z, 2), "yaw": round(r.yaw_deg, 2),
             "scale": round(r.scale, 4), "ground": round(r.terrain_z, 2),
             "top": round(r.top_z, 2)} for r in rocks]


def footprint(rock):
    """The four corners of a rock's footprint box, round in order."""
    t = math.radians(rock.tangent_deg)
    ux, uy = math.cos(t), math.sin(t)
    vx, vy = -uy, ux
    return [(rock.cx + a * rock.half_len * ux + b * rock.half_depth * vx,
             rock.cy + a * rock.half_len * uy + b * rock.half_depth * vy)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _seg_point(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (ax * ax + ay * ay)))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def box_gap_cm(r1, r2):
    """The clear distance between two rocks' footprint boxes (0 when they
    touch or overlap)."""
    p1, p2 = footprint(r1), footprint(r2)
    if _overlaps(p1, p2):
        return 0.0
    return min(min(_seg_point(p, a, b) for a, b in zip(q, q[1:] + q[:1]))
               for ps, q in ((p1, p2), (p2, p1)) for p in ps)


def _overlaps(p1, p2):
    for poly in (p1, p2):
        for a, b in zip(poly, poly[1:] + poly[:1]):
            nx, ny = a[1] - b[1], b[0] - a[0]
            s1 = [nx * x + ny * y for x, y in p1]
            s2 = [nx * x + ny * y for x, y in p2]
            if max(s1) < min(s2) or max(s2) < min(s1):
                return False
    return True


def neighbour_overlap(r1, r2):
    """How far two neighbours of one stretch overlap along the ring, as a
    share of the shorter one."""
    gap = math.hypot(r2.cx - r1.cx, r2.cy - r1.cy)
    return (r1.half_len + r2.half_len - gap) / (2.0 * min(r1.half_len, r2.half_len))


def stretches(rocks):
    """The rocks by stretch, each in order round the ring."""
    out = {}
    for rock in rocks:
        out.setdefault(rock.arc, []).append(rock)
    return [out[k] for k in sorted(out)]


def opening_widths_cm(rocks):
    """Each opening's clear width: the gap between the last rock of one
    stretch and the first of the next."""
    arcs = stretches(rocks)
    return [box_gap_cm(arcs[k][-1], arcs[(k + 1) % len(arcs)][0])
            for k in range(len(arcs))]
