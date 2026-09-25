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

# Rough trunk radius per unit of tree scale.  This is a proxy, used only for
# spawn clearance and the line-of-sight test below — never for collision, which
# comes from the real mesh geometry.
NOMINAL_TRUNK_RADIUS_PER_SCALE_CM = 15.0

# Spawn constraints
MIN_PLAYER_DISTANCE_FRACTION = 0.55  # of the usable radius
TRUNK_CLEARANCE_CM = 220.0           # keep the capsule clear of any trunk
EDGE_MARGIN_FRACTION = 0.88          # stay inside this much of the half-extent
MAX_PLACEMENT_ATTEMPTS = 400


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
    usable = half * edge_margin_fraction
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
