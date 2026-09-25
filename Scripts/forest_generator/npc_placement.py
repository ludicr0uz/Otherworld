"""
npc_placement.py — Deterministic spawn point for the wandering forest NPC.

Picks a random spot on the terrain for an NPC that then walks to the player.
"Random" still has to satisfy a few things, so this is rejection sampling with
a scoring pass rather than a single draw:

  * far enough from the PlayerStart that the NPC has a real journey to make
  * not standing inside a tree trunk
  * inside the navigable area, clear of the map edge
  * preferably with at least one tree blocking the straight line to the player,
    so the path actually has to bend around something

The last point is what makes the "goes around the trees" behaviour observable
instead of accidental; ``verification.check_npc_route_is_obstructed`` asserts it.
"""

import math
import random
from dataclasses import dataclass

from .terrain import get_exact_mesh_z


# ─── Configuration ───────────────────────────────────────────────────────────

# Matches the stock Character capsule the NPC Blueprint inherits.
NPC_CAPSULE_HALF_HEIGHT_CM = 88.0

# ── Behaviour, shared with build_npc_blueprints.py ───────────────────────────
# Kept here rather than in the builder because this module imports no `unreal`,
# so the host-side generator can read them too and bake them into the checks.
#
# "Slowly": UE's default walk speed is 600 cm/s (a run).  110 cm/s reads as an
# unhurried walk and gives the player time to see the NPC coming.
NPC_WALK_SPEED_CMS = 110.0
NPC_ACCEPTANCE_RADIUS_CM = 150.0   # stop this far from the player
NPC_REPATH_SECONDS = 0.5           # how often the move order is re-issued

# Navmesh agent.  These are the navigation system's *default agent* values, and
# they are deliberately not something else: the nav system overwrites whatever
# is set on a RecastNavMesh actor with its default agent config when the nav
# data registers, so a per-actor override does not survive a level load.  To
# widen the inset around trunks, change Project Settings -> Navigation System ->
# Supported Agents instead of these constants.  A 35 cm inset still clears the
# NPC's 34 cm capsule, and tree spacing is >= 125 cm so every gap stays passable.
NAV_AGENT_RADIUS_CM = 35.0
NAV_AGENT_HEIGHT_CM = 144.0

# ── Navigation volume sizing ─────────────────────────────────────────────────
#
# Recast silently generates *no tiles at all* once the volume gets too big for
# its tile pool -- no warning, no error, just an empty navmesh and an NPC that
# cannot move.  The limits below are an EMPIRICALLY MEASURED envelope, not
# something read out of the engine:
#
#     +/-8500 cm XY, 1500 cm vertical span  -> 176 tiles built, NPC walked (OK)
#     +/-9200 cm XY, 2007 cm vertical span  -> 0 tiles built, NPC immobile
#
# so the caps sit just above the known-good point.  UE 5.8 exposes neither
# `tile_size_uu` nor a readable tile limit to Python, so this cannot currently be
# derived; if the navmesh ever comes up empty again, suspect these first.
NAV_COVERAGE_FRACTION = 0.85
NAV_MAX_HALF_XY_CM = 8500.0
NAV_MAX_VERTICAL_SPAN_CM = 1600.0
# Headroom must exceed the agent height (144 cm) or the surface right under the
# volume's ceiling is treated as too low to stand in.
NAV_VERTICAL_HEADROOM_CM = 200.0

# Rough trunk radius per unit of tree scale.  This is a proxy, used only for
# spawn clearance and the line-of-sight test below — never for collision, which
# comes from the real mesh geometry.
NOMINAL_TRUNK_RADIUS_PER_SCALE_CM = 15.0

# Spawn constraints
MIN_PLAYER_DISTANCE_FRACTION = 0.55  # of the usable radius
TRUNK_CLEARANCE_CM = 220.0           # keep the capsule clear of any trunk
EDGE_MARGIN_FRACTION = 0.80          # stay inside this much of the half-extent
MAX_PLACEMENT_ATTEMPTS = 400


def compute_nav_bounds(
    world_size_cm: float,
    grid_z,
    grid_size: int,
    coverage_fraction: float = NAV_COVERAGE_FRACTION,
    headroom_cm: float = NAV_VERTICAL_HEADROOM_CM,
    min_half_xy_cm: float = 0.0,
) -> dict:
    """
    Size the NavMeshBoundsVolume from the terrain it actually has to cover.

    Returns ``half_xy_cm``, ``center_z_cm`` and ``half_z_cm`` for the volume,
    plus the terrain band they were derived from.

    Sizing Z from the *terrain* rather than from the map width is the whole
    point: this terrain's edge ramp climbs to ~40 m at the corners, so a
    width-derived Z span covers mostly empty air and unwalkable cliff, and
    Recast then generates nothing.
    """
    half = world_size_cm / 2.0
    # Capped: see NAV_MAX_HALF_XY_CM.  On a map larger than the cap the navmesh
    # covers a central island rather than the whole world -- which is why
    # place_npc() clamps the spawn radius to the same cap.
    half_xy = min(half * coverage_fraction, NAV_MAX_HALF_XY_CM)

    # Sample a DISK of this radius, not the square box.  The box has to contain
    # the disk the NPC spawns in, but its corners sit ~1.41x further out, where
    # this terrain's edge ramp is tens of metres tall.  Letting those corners set
    # the Z band inflates the volume enormously for ground no one can walk on --
    # and an inflated Z band is what stops Recast generating tiles at all.
    # Terrain above the box top simply stays non-navigable, which is correct: it
    # is a cliff.
    step = world_size_cm / grid_size
    radius_sq = half_xy * half_xy
    lo, hi = float("inf"), float("-inf")
    for gi in range(grid_size + 1):
        gx = -half + gi * step
        row = grid_z[gi]
        for gj in range(grid_size + 1):
            gy = -half + gj * step
            if gx * gx + gy * gy > radius_sq:
                continue
            z = row[gj]
            lo = min(lo, z)
            hi = max(hi, z)
    if lo > hi:            # degenerate (tiny map); fall back to a flat band
        lo = hi = 0.0

    span = (hi - lo) + 2.0 * headroom_cm
    # If the terrain band is still too tall, pull the radius in until it fits --
    # the tall ground is the outer edge ramp, so a smaller radius lowers the band.
    while span > NAV_MAX_VERTICAL_SPAN_CM and half_xy > max(min_half_xy_cm, 1000.0):
        half_xy *= 0.9
        radius_sq = half_xy * half_xy
        lo, hi = float("inf"), float("-inf")
        for gi in range(grid_size + 1):
            gx = -half + gi * step
            row = grid_z[gi]
            for gj in range(grid_size + 1):
                gy = -half + gj * step
                if gx * gx + gy * gy > radius_sq:
                    continue
                lo = min(lo, row[gj])
                hi = max(hi, row[gj])
        if lo > hi:
            lo = hi = 0.0
        span = (hi - lo) + 2.0 * headroom_cm

    return {
        "half_xy_cm": half_xy,
        "center_z_cm": (hi + lo) / 2.0,
        "half_z_cm": span / 2.0,
        "terrain_min_z_cm": lo,
        "terrain_max_z_cm": hi,
    }


@dataclass
class PlacedNPC:
    """The NPC's chosen spawn transform plus the facts verification checks."""
    x: float
    y: float
    terrain_z: float            # exact mesh Z under the spawn point
    spawn_z: float              # capsule centre = terrain_z + half height
    yaw_deg: float              # faces the player
    distance_to_player_cm: float
    nearest_trunk_cm: float
    blocking_trees: int         # trees straddling the straight line to player
    attempts: int


def npc_usable_radius(
    world_size_cm: float,
    edge_margin_fraction: float = EDGE_MARGIN_FRACTION,
) -> float:
    """
    The radius the NPC may spawn within — the single source of truth, shared by
    place_npc() and the offline checks so the two cannot drift apart.

    Clamped to the navigable island (see NAV_MAX_HALF_XY_CM).
    """
    half = world_size_cm / 2.0
    return min(half * edge_margin_fraction, NAV_MAX_HALF_XY_CM - 300.0)


def _trunk_radius(tree) -> float:
    return NOMINAL_TRUNK_RADIUS_PER_SCALE_CM * tree.scale


def _segment_blockers(x0, y0, x1, y1, placed_trees, pad_cm: float) -> int:
    """
    Count trees whose trunk (plus agent padding) straddles the segment
    (x0,y0)->(x1,y1) — i.e. obstacles a straight walk would hit.
    """
    dx, dy = x1 - x0, y1 - y0
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-6:
        return 0

    blockers = 0
    for t in placed_trees:
        # Distance from the trunk centre to the segment.
        s = ((t.x - x0) * dx + (t.y - y0) * dy) / seg_len_sq
        s = max(0.0, min(1.0, s))
        cx, cy = x0 + s * dx, y0 + s * dy
        reach = _trunk_radius(t) + pad_cm
        if (t.x - cx) ** 2 + (t.y - cy) ** 2 < reach * reach:
            blockers += 1
    return blockers


def place_npc(
    world_size_cm: float,
    grid_z,
    grid_size: int,
    seed: int = 42,
    placed_trees=None,
    player_start=(0.0, 0.0),
    min_distance_fraction: float = MIN_PLAYER_DISTANCE_FRACTION,
    trunk_clearance_cm: float = TRUNK_CLEARANCE_CM,
    edge_margin_fraction: float = EDGE_MARGIN_FRACTION,
) -> PlacedNPC | None:
    """
    Choose the NPC's spawn point.  Returns None only if no candidate satisfies
    the hard constraints, which would mean the map is too small or too dense.

    Candidates are drawn uniformly by area (``sqrt`` on the radius, so the
    distribution does not bunch up at the centre) and the first one that both
    satisfies the hard constraints *and* has a tree blocking the direct route
    wins.  If none is obstructed, the best legal candidate is used and the
    offline check reports it rather than failing the build.
    """
    placed_trees = placed_trees or []
    rng = random.Random(seed ^ 0x4E7C)  # decorrelated from trees and grass

    half = world_size_cm / 2.0
    # Never spawn outside the navmesh: nav coverage is capped, so on a large map
    # the navigable region is a central island, and a spawn beyond it would leave
    # the NPC permanently off-mesh and immobile.
    usable = npc_usable_radius(world_size_cm, edge_margin_fraction)
    min_dist = usable * min_distance_fraction
    px, py = player_start

    fallback = None

    for attempt in range(1, MAX_PLACEMENT_ATTEMPTS + 1):
        # Uniform over the annulus between min_dist and usable.
        frac = rng.random()
        dist = math.sqrt(min_dist ** 2 + frac * (usable ** 2 - min_dist ** 2))
        theta = rng.uniform(0.0, 2.0 * math.pi)
        nx = px + dist * math.cos(theta)
        ny = py + dist * math.sin(theta)

        if abs(nx) > usable or abs(ny) > usable:
            continue

        nearest = min((math.hypot(t.x - nx, t.y - ny) - _trunk_radius(t)
                       for t in placed_trees), default=float("inf"))
        if nearest < trunk_clearance_cm:
            continue

        nz = get_exact_mesh_z(nx, ny, grid_z, grid_size, world_size_cm)
        blockers = _segment_blockers(nx, ny, px, py, placed_trees,
                                     NAV_AGENT_RADIUS_CM)

        candidate = PlacedNPC(
            x=nx, y=ny,
            terrain_z=nz,
            spawn_z=nz + NPC_CAPSULE_HALF_HEIGHT_CM,
            yaw_deg=math.degrees(math.atan2(py - ny, px - nx)) % 360.0,
            distance_to_player_cm=math.hypot(nx - px, ny - py),
            nearest_trunk_cm=nearest,
            blocking_trees=blockers,
            attempts=attempt,
        )

        if blockers > 0:
            return candidate
        if fallback is None:
            fallback = candidate

    return fallback
