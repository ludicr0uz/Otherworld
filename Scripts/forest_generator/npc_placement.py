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
# The wanderers RUN at the player: 600 cm/s is UE's own default MaxWalkSpeed and
# the speed ABP_Unarmed's locomotion blend space tops out at, so the legs play
# the jog cycle rather than a walk played back too fast.  (It used to be
# 110 cm/s -- an unhurried walk, from when the NPC was scenery rather than a
# threat.)
NPC_RUN_SPEED_CMS = 600.0

# Stop just inside melee reach, not on top of the player: the acceptance radius
# has to be SMALLER than NPC_MELEE_RANGE_CM or the NPC parks itself outside its
# own reach and never lands a hit.
NPC_ACCEPTANCE_RADIUS_CM = 120.0
NPC_REPATH_SECONDS = 0.5           # how often the move order is re-issued

# ── Melee, shared with build_npc_blueprints.py ───────────────────────────────
# Range is measured between actor *origins* (capsule centres), which is what
# Vector_Distance on the two GetActorLocation calls gives.  Two stock Character
# capsules are 34 cm in radius each, so 200 cm centre-to-centre is roughly an
# arm's length of clear air between them -- close enough to read as a hit, loose
# enough that a frame of separation does not cancel the swing.
NPC_MELEE_RANGE_CM = 200.0
# Balance these two against the PACK, not against one attacker: they spawn in
# one band and arrive within a few seconds of each other, so whatever one
# wanderer does is very nearly multiplied by NPC_COUNT -- and NPC_COUNT is now
# ten, so the numbers below are twice as lethal as the run they were tuned in.  Measured in a -game
# run, 12 damage every 1.2 s put five of them at 50 dps and killed a 100 HP
# player in two seconds flat, before a single shot could be fired.  10 every
# 1.5 s is 6.7 dps each: ~33 for a pack of five, ~67 for the ten that spawn
# now. Lethal in about a second and a half if the player stands still and lets
# all ten reach them, which is what the 75 m approach and the sprint key exist
# to give them an answer to.
NPC_MELEE_DAMAGE = 10.0            # 100 HP / 10 = 10 hits from one wanderer
NPC_MELEE_INTERVAL_S = 1.5         # seconds between swings, per NPC
# Played on DefaultSlot, which build_weapons_and_combat.py's layered blend makes
# upper-body only -- so the NPC swings while still running.
#
# An AnimSequence can only be played on an anim instance whose skeleton it was
# authored for, so the wanderers wearing Meshy creatures need the RETARGETED
# swing, not the mannequin's.  The fallback is not decoration: /Game/Sourced is
# git-ignored and rebuilt from assets/cache/meshy, so a fresh clone that has
# not run the asset pipeline has no Meshy anything, and an NPC with no melee
# animation is better than a builder that dies.
NPC_MELEE_MONTAGE_FALLBACK = "/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"
NPC_MELEE_BLEND_S = 0.15

# ── Flinching ────────────────────────────────────────────────────────────────
#
# The six clips a wanderer plays when it is shot and lives, in the order the
# reaction graph indexes them: three Fronts, then Back, Left, Right.  THE ORDER
# IS THE CONTRACT -- combat.hit_reaction.HIT_REACTION_CLIPS imports this
# tuple and bakes positions in it into pin literals, so reordering here silently
# plays a Left clip for a hit in the back.
#
# Bare clip names, because the same six exist once per creature under that
# creature's own Anims folder (an AnimSequence belongs to one skeleton, exactly
# as the melee swing above does).  Scripts/asset_pipeline/build_retarget.py
# produces them from Epic's MM_HitReact_* set -- the flinches Epic ships for
# exactly this; see HIT_SOURCES there for why it is not MM_Death_*.
#
# Epic authored no Left or Right, so the side slots are the two Fronts whose
# head moves AWAY from that side (measured off the source assets, and asserted
# by verify_weapons_and_combat.py rather than trusted to the names):
#   Front_Hvy_01  head 4 cm to the right, chest turned 55 deg left -> hit on the LEFT
#   Front_Lgt_04  head 6 cm to the left,  chest turned 27 deg right -> hit on the RIGHT
NPC_HIT_REACTION_CLIPS = ("MM_HitReact_Front_Lgt_01", "MM_HitReact_Front_Med_01",
                          "MM_HitReact_Front_Lgt_02", "MM_HitReact_Back_Med_01",
                          "MM_HitReact_Front_Hvy_01", "MM_HitReact_Front_Lgt_04")

# How much health a wanderer has. The zombie is the yardstick -- 100 HP against
# a pistol that does 26 means four rounds, which is what the weapon damage
# numbers in build_weapons_and_combat.py were tuned against.
NPC_BASE_HEALTH = 100.0

# ── Voices ───────────────────────────────────────────────────────────────────
#
# Synthesised by Scripts/make_creature_sounds.py and imported to /Game/Audio by
# combat.audio.import_sounds().  Several takes per creature and the
# controller draws one at random, because a pack of ten on a 4-9 s timer
# retriggering ONE buffer reads as a machine rather than as a forest.
#
# These are asset *package* paths; the builder resolves them and silently drops
# any that are missing, so a checkout that has not run the sound script still
# gets silent monsters rather than a failed build.
CREATURE_AUDIO_DIR = "/Game/Audio"
ZOMBIE_VOICES = tuple(f"{CREATURE_AUDIO_DIR}/A_ZombieGrowl_{i:02d}" for i in (1, 2, 3))
WENDIGO_VOICES = tuple(f"{CREATURE_AUDIO_DIR}/A_WendigoRoar_{i:02d}" for i in (1, 2, 3))

# How often a wanderer makes a noise, drawn uniformly per utterance. Tuned
# against the PACK and not against one monster: ten of them on a 4-9 s timer is
# a sound roughly every 0.65 s somewhere in the forest, which is a constant
# presence without being a wall. One creature alone is quiet enough to be
# startling.
NPC_VOICE_MIN_S = 4.0
NPC_VOICE_MAX_S = 9.0


# ── Which creature each wanderer wears ───────────────────────────────────────
#
# The wanderers are Meshy monsters, generated by Scripts/asset_pipeline and
# retargeted onto the mannequin's locomotion.  They differ ONLY in mesh: the
# capsule, the run speed, the melee numbers and the whole chase loop are
# inherited from a single parent Blueprint, so there is exactly one place where
# NPC behaviour lives no matter how many creatures get added.  That is also why
# the variants are expressed as child Blueprints rather than as a mesh swap on
# spawn -- a child cannot drift from its parent's stats.
#
# Every fifth wanderer is a wendigo.  With NPC_COUNT at 10 that is two of them,
# which is the intent: the wendigo is the rarer, taller silhouette and reads as
# such only if most of what the player meets is a zombie.
NPC_WENDIGO_EVERY = 5

# ── What makes a wendigo different ───────────────────────────────────────────
#
# It used to be nothing but the mesh: the variants were child Blueprints that
# overrode asset references and were forbidden from touching a stat, so that
# behaviour could not drift between them.  That was the right rule while the
# two were meant to be the same monster in different skin, and it is the wrong
# one now that the wendigo is meant to be the dangerous one.
#
# So the variants carry stats, but only these two, and only as MULTIPLES of the
# base -- the melee damage, the range, the interval, the acceptance radius and
# the whole chase loop are still defined exactly once on the parent.  A wendigo
# is a zombie with more health and more speed, and the code says so in one line
# rather than in a second copy of the behaviour.
#
# 3x health and 1.15x speed, both asked for directly.  What they cost: 300 HP
# is twelve pistol rounds or three sniper shots, and at 690 cm/s the wendigo is
# faster than the player's 600 cm/s walk but still slower than the 900 cm/s
# sprint -- so it cannot be walked away from and can be outrun, which is the
# only arrangement that keeps sprint meaningful.
WENDIGO_HEALTH_MULTIPLIER = 3.0
WENDIGO_SPEED_MULTIPLIER = 1.15


@dataclass(frozen=True)
class NpcVariant:
    """One creature the wanderers can wear.

    Every field but ``key`` names a per-creature asset, because a creature IS
    its own skeleton: Meshy shares bone names between monsters but not bind
    poses, so each one carries its own retargeted animation set and, since an
    AnimSequence belongs to exactly one skeleton, its own AI controller holding
    its own attack clip.  See import_characters.py for the measurements.

    Two stats are per creature -- see WENDIGO_HEALTH_MULTIPLIER -- and they are
    the only two.  Everything else about how a wanderer behaves (capsule, melee
    damage, range, interval, acceptance radius, the chase loop itself) is
    defined once on BP_ForestWanderer and inherited, so it cannot drift.

    ``speed_scale`` multiplies the run speed AND the animation rate together.
    Scaling one without the other is foot-sliding: the locomotion blend space
    is authored for a particular ground speed, so a wendigo running 15% faster
    with the stride of a zombie skates.  See gait_scale_for_index, which has
    the same constraint for a different reason.
    """
    key: str
    blueprint: str
    mesh: str
    anim_bp: str
    melee: str
    ai_blueprint: str
    health: float
    speed_scale: float
    voices: tuple
    # This creature's six hit reactions, in NPC_HIT_REACTION_CLIPS order. Its
    # AI controller copies them onto the pawn's health component at possession,
    # for the same reason it writes the health: an inherited component's
    # defaults cannot be overridden per child Blueprint from Python.
    reactions: tuple = ()
    # The creature's own retargeted MM_Attack_01, for when ``melee`` names a
    # clip the asset pipeline has not produced (e.g. the Mixamo packs were
    # never imported). Same skeleton either way.
    melee_fallback: str = ""


def _creature(key, folder, health=NPC_BASE_HEALTH, speed_scale=1.0, voices=(),
              melee=None):
    """The asset layout every creature follows, from one name.

    ``melee`` overrides the retargeted MM_Attack_01, which stays the fallback
    (``melee_fallback``) for a build that has not imported the override.
    """
    anims = f"/Game/Sourced/Characters/Anims/{folder}"
    stock_melee = f"{anims}/A_{folder}_MM_Attack_01"
    return NpcVariant(
        key=key,
        blueprint=f"/Game/Forest/NPC/BP_Wanderer_{key}",
        mesh=f"/Game/Sourced/Characters/SKM_{folder}/SKM_{folder}",
        anim_bp=f"{anims}/A_{folder}_ABP_Unarmed",
        melee=melee or stock_melee,
        melee_fallback=stock_melee,
        ai_blueprint=f"/Game/Forest/NPC/BP_ForestWandererAI_{key}",
        health=health,
        speed_scale=speed_scale,
        voices=voices,
        reactions=tuple(f"{anims}/A_{folder}_{clip}"
                        for clip in NPC_HIT_REACTION_CLIPS),
    )


NPC_VARIANTS = (
    # The zombie swings the Mixamo pack's two-handed lunge
    # (asset_pipeline/import_mixamo.py, which checks this literal against
    # mixamo_paths.MELEE).
    _creature("Zombie", "Zombie01", voices=ZOMBIE_VOICES,
              melee="/Game/Sourced/Mixamo/Zombie01/"
                    "A_Zombie01_Mx_Scary_ZombieAttack"),
    _creature("Wendigo", "Wendigo01",
              health=NPC_BASE_HEALTH * WENDIGO_HEALTH_MULTIPLIER,
              speed_scale=WENDIGO_SPEED_MULTIPLIER,
              voices=WENDIGO_VOICES),
)


# The parent BP_ForestWanderer wears the first creature. It is never spawned
# directly -- every placed wanderer is one of the variants -- but it has to be
# a complete, working character so the children inherit one.
# The creature's own retargeted MM_Attack_01, not an override: the parent is
# never spawned, so it need not wait on an optional import (the Mixamo packs).
NPC_MELEE_MONTAGE = NPC_VARIANTS[0].melee_fallback
NPC_BASE_MESH = NPC_VARIANTS[0].mesh
NPC_BASE_MESH_FALLBACK = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"
NPC_ANIM_BP = NPC_VARIANTS[0].anim_bp
NPC_ANIM_BP_FALLBACK = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"


# ── Per-instance gait variance ───────────────────────────────────────────────
#
# Every wanderer spawns at level load and every one of them starts its blend
# space at normalised time 0.  Epic's locomotion advances through a sync group,
# so identical inputs stay in phase forever: ten monsters walking with the same
# leg on the same frame, which reads as a chorus line rather than a crowd.
#
# The fix is to give each one a slightly different gait.  It scales the
# animation rate AND the walk speed by the *same* factor -- rate alone would
# desynchronise them but slide their feet, since the clips are authored for a
# particular ground speed.  Scaling both keeps the stride planted.
#
# This is per INSTANCE, not per species: BP_Wanderer_Zombie and
# BP_Wanderer_Wendigo still carry byte-identical stats.  The variance is
# applied to the placed actor by the level generator.
NPC_GAIT_VARIANCE = 0.08

# Golden-ratio low-discrepancy sequence: deterministic (so a regenerated level
# is identical), and it never lets neighbouring indices land on close values
# the way index % n would.
_GOLDEN = 0.6180339887498949


def gait_scale_for_index(index):
    """Animation-rate and walk-speed multiplier for the ``index``-th wanderer.

    ``index`` is 1-based.  Returns a value in
    [1 - NPC_GAIT_VARIANCE, 1 + NPC_GAIT_VARIANCE].
    """
    phase = (index * _GOLDEN) % 1.0
    return 1.0 - NPC_GAIT_VARIANCE + 2.0 * NPC_GAIT_VARIANCE * phase


def variant_for_index(index):
    """Which creature the ``index``-th wanderer wears. ``index`` is 1-based.

    1-based to match the generator's own console output and the actor labels,
    so "NPC 5 is the wendigo" means the same thing in the log, in the outliner
    and here.
    """
    if index % NPC_WENDIGO_EVERY == 0:
        return NPC_VARIANTS[1]
    return NPC_VARIANTS[0]

# ── How many, and how far away ───────────────────────────────────────────────
# Ten wanderers, every one of them spawned in a 75-100 m band around the
# PlayerStart: far enough that the player never opens their eyes next to one,
# close enough that the pack arrives within ~15 s at a 600 cm/s run.
#
# Ten rather than five is a real change to the fight, not a bigger number: the
# pack's damage scales with this constant (see NPC_MELEE_DAMAGE above), so ten
# arriving together is ~67 dps against 100 HP -- about a second and a half of
# standing still. Sprint (900 cm/s against their 600) is what that leaves as the
# answer, rather than trading hits.
#
# The band is CLAMPED to the navigable island on small maps (see
# npc_usable_radius): a 200 m map has a usable radius of 80 m, so the band
# there is 75-80 m.  place_npcs() reports the band it actually used and
# verification.check_npc_spawn_band asserts against that, so a clamp is visible
# rather than silent.
NPC_COUNT = 10
NPC_SPAWN_MIN_DISTANCE_CM = 7500.0
NPC_SPAWN_MAX_DISTANCE_CM = 10000.0
# Keep the pack from spawning as a single clump -- they path to the same target
# and would otherwise arrive as one body occupying one capsule's worth of space.
NPC_MIN_SEPARATION_CM = 600.0

# Where a *replacement* appears after one dies.  The same band, but measured
# from wherever the player is standing at that moment rather than from the
# PlayerStart, so the 75-100 m rule keeps holding once the player moves.  The
# nav snap radius is generous because the far edge of the band can fall outside
# the navigable island: 30 m is enough to reach back onto it from a point 100 m
# out on a 200 m map.
NPC_RESPAWN_NAV_SNAP_CM = 3000.0
# How long after a wanderer dies its replacement appears, so a kill thins the
# pack for a while instead of being undone on the spot.  Well under the 60 s a
# corpse lies there (combat/death.py), which is what the wait hangs on.
NPC_RESPAWN_DELAY_S = 10.0

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
# The navmesh covers the WHOLE terrain.  It did not always: the volume used to
# be sized at 0.85 of the map with a 1600 cm ceiling on its vertical span, on
# the belief that a larger volume overruns Recast's tile pool and silently
# generates *no tiles at all*.  That belief came from one measurement --
#
#     +/-8500 cm XY, 1500 cm vertical span  -> 176 tiles, NPC walked
#     +/-9200 cm XY, 2007 cm vertical span  -> 0 tiles,   NPC immobile
#
# -- which moved two variables at once and blamed the wrong one.  Re-measured
# directly on Lvl_Forest_200m by resizing the volume in a live editor, running
# RebuildNavigation, and then projecting points onto the result:
#
#     +/-10000 cm XY, 4586 cm vertical span -> navmesh reaches the terrain edge
#                                              on all 48 sampled headings, with
#                                              no heading short by even 4 m
#
# So the cap was not a Recast limit, it was a self-inflicted dead zone: a ring
# of walkable ground 15 m wide with no navigation data on it, which is exactly
# where NPCs stopped following.  Cover the terrain and the ring does not exist.
#
# The caps below are guard rails rather than targets, and each sits at a
# measured-good point: +/-50000 XY was measured on Lvl_Forest_1000m the same way
# (401/401 probe points on the navmesh).  If a map comes up with an empty
# navmesh, measure before believing anything here: UE 5.8
# exposes neither `tile_size_uu` nor a readable tile limit to Python, so the
# only honest way to know is to resize, rebuild, and project.
NAV_COVERAGE_FRACTION = 1.0
# Raised from 10000 for Lvl_Forest_1000m: a +/-10000 cap left 96% of that map
# without navigation, i.e. nowhere the pack could follow.  Recast's own tile
# limit (TileNumberHardLimit, 1 << 20) is far above the ~10k tiles +/-50000
# needs, and pending tiles build nearest-the-player first (SortPendingBuildTiles
# with seed locations), so the ground around the spawn is ready first.
NAV_MAX_HALF_XY_CM = 50000.0
NAV_MAX_VERTICAL_SPAN_CM = 5000.0
# Headroom must exceed the agent height (144 cm) or the surface right under the
# volume's ceiling is treated as too low to stand in.
NAV_VERTICAL_HEADROOM_CM = 200.0

# ── Chasing off the navmesh ──────────────────────────────────────────────────
#
# With the volume covering the whole terrain (above) there is no dead zone left
# to speak of, but the navmesh edge and the terrain edge are still not the same
# line to the centimetre: Recast will not build on ground steeper than the
# agent's slope limit, so the corner ramps keep a few metres that a player can
# scramble onto and a path cannot be found to.  The chase therefore still asks,
# twice a second, whether pathfinding applies at all, and issues the same move
# order with pathfinding switched off when it does not -- which path-follows a
# straight line and works anywhere there is ground.
#
# This is a net, not the mechanism.  When it WAS the mechanism -- a 15 m ring
# of un-navigable ground around the whole map -- it showed: the fallback and
# the pathfinding order flip-flopped as the projection test flickered along the
# island edge, each flip cancelling the move request the other had just issued,
# and the pack visibly stuttered at an invisible line before crossing it.  A
# navmesh that reaches the terrain edge is what fixes that; the fallback then
# only ever fires for the last metre or two of a corner.
#
# Straight-line chasing is the right fallback specifically HERE and it is worth
# saying why, because in general it is not: trees are scattered only within
# EDGE_MARGIN_FRACTION (0.80) of the half-extent, so the ground it covers is
# open.  There is very little out there to walk into.
#
# The test is "does this point project onto the navmesh within this box", and
# the box has to be TIGHT or it answers yes for a player well outside the
# navmesh by snapping to its edge -- which was the original bug, restated.
# 200 cm in XY is far tighter than anything that reads as "off the mesh".
#
# Z is generous for a reason that has already bitten this project once: a
# navmesh polygon can sit up to 86 cm below the real ground (Recast voxelises
# and then simplifies), and the point being projected is an actor location,
# i.e. a capsule CENTRE, another 88 cm above the surface.  A tight Z box would
# report a player standing squarely on the navmesh as being off it, and the
# whole pack would abandon pathfinding in the middle of the forest.
NAV_REACHABLE_EXTENT_CM = (200.0, 200.0, 400.0)

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
    point: a width-derived span covers mostly empty air, and an empty band is
    voxelised at full height for every tile for no benefit.  The band this
    terrain actually asks for on a 200 m map is -190..3995 cm -- the corner
    ramps -- plus headroom at each end.
    """
    half = world_size_cm / 2.0
    # Capped: see NAV_MAX_HALF_XY_CM.  At the default coverage of 1.0 the cap
    # only bites on a map wider than 200 m, and then the navmesh covers a
    # central island rather than the whole world -- which is why place_npc()
    # clamps the spawn radius to the same cap.
    half_xy = min(half * coverage_fraction, NAV_MAX_HALF_XY_CM)

    # Sample the BOX, corners included, because the box is what gets built.
    # This used to sample an inscribed disk so that the tall corner ramps could
    # not inflate the Z band -- on the theory that a tall band is what stops
    # Recast generating tiles.  Measurement says otherwise (see
    # NAV_MAX_VERTICAL_SPAN_CM): the 4586 cm band this terrain's corners ask for
    # builds fine, and sampling the disk instead left the corners sticking out
    # through the volume's ceiling, where they were not navigable.
    step = world_size_cm / grid_size
    lo, hi = float("inf"), float("-inf")
    for gi in range(grid_size + 1):
        gx = -half + gi * step
        if abs(gx) > half_xy:
            continue
        row = grid_z[gi]
        for gj in range(grid_size + 1):
            gy = -half + gj * step
            if abs(gy) > half_xy:
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
        lo, hi = float("inf"), float("-inf")
        for gi in range(grid_size + 1):
            gx = -half + gi * step
            if abs(gx) > half_xy:
                continue
            row = grid_z[gi]
            for gj in range(grid_size + 1):
                gy = -half + gj * step
                if abs(gy) > half_xy:
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

    Clamped to NAV_MAX_HALF_XY_CM as well, which on a 200 m map is slack --
    the 0.80 margin binds first -- and only matters on a map too wide for the
    navmesh to cover.
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


def spawn_band(
    world_size_cm: float,
    edge_margin_fraction: float = EDGE_MARGIN_FRACTION,
    min_distance_cm: float = NPC_SPAWN_MIN_DISTANCE_CM,
    max_distance_cm: float = NPC_SPAWN_MAX_DISTANCE_CM,
) -> tuple[float, float, bool]:
    """
    The annulus the NPCs spawn in, clamped to what the map can actually hold.

    Returns ``(min_cm, max_cm, clamped)``.  This is the single source of truth
    for the band: place_npcs() draws from it and
    ``verification.check_npc_spawn_band`` asserts against it, so the two cannot
    disagree about what "75-100 m" meant on a map too small to hold it.

    The clamp is not cosmetic.  A 200 m map's usable radius is 80 m (see
    npc_usable_radius -- nav coverage is capped, and a spawn beyond the navmesh
    leaves the NPC immobile), so the honest band there is 75-80 m.  A request
    that cannot be met at all collapses to a ring just inside the usable radius
    rather than silently spawning NPCs off the navmesh.
    """
    usable = npc_usable_radius(world_size_cm, edge_margin_fraction)
    # 0.5% back from the edge: the rejection test below is on |x| and |y|, and a
    # candidate exactly on the radius fails it at theta = 0 for float reasons.
    hi = min(max_distance_cm, usable * 0.995)
    lo = min(min_distance_cm, hi)
    if lo >= hi:
        lo = hi * 0.9
    clamped = (hi < max_distance_cm - 1e-6) or (lo < min_distance_cm - 1e-6)
    return lo, hi, clamped


def place_npcs(
    world_size_cm: float,
    grid_z,
    grid_size: int,
    seed: int = 42,
    placed_trees=None,
    player_start=(0.0, 0.0),
    count: int = NPC_COUNT,
    min_distance_cm: float = NPC_SPAWN_MIN_DISTANCE_CM,
    max_distance_cm: float = NPC_SPAWN_MAX_DISTANCE_CM,
    trunk_clearance_cm: float = TRUNK_CLEARANCE_CM,
    edge_margin_fraction: float = EDGE_MARGIN_FRACTION,
    min_separation_cm: float = NPC_MIN_SEPARATION_CM,
) -> list[PlacedNPC]:
    """
    Choose spawn points for ``count`` wanderers, all inside the spawn band.

    Rejection sampling per NPC, with the same hard constraints as before --
    clear of trunks, inside the navigable area -- plus one new one: no two
    wanderers within ``min_separation_cm``, so the pack starts spread around the
    player rather than stacked in one spot (they all path to the same target, so
    a clump never unclumps).

    Distance is drawn uniformly *by area* within the band, which is why it is a
    sqrt rather than a plain uniform: a plain uniform bunches spawns toward the
    inner edge.  A candidate whose straight line to the player is blocked by a
    tree is preferred -- that is what makes "walks around the trees" observable
    -- but an unobstructed one is accepted rather than failing the build, and
    the offline check reports which happened.

    Returns as many NPCs as it could place; fewer than ``count`` means the map
    is too small or too dense for the band, and check_npc_count fails.
    """
    placed_trees = placed_trees or []
    usable = npc_usable_radius(world_size_cm, edge_margin_fraction)
    lo, hi, _clamped = spawn_band(world_size_cm, edge_margin_fraction,
                                  min_distance_cm, max_distance_cm)
    px, py = player_start

    placed: list[PlacedNPC] = []
    for index in range(count):
        # Each NPC gets its own decorrelated stream, so adding a sixth wanderer
        # does not move the first five.
        rng = random.Random((seed ^ 0x4E7C) + index * 7919)
        fallback = None

        for attempt in range(1, MAX_PLACEMENT_ATTEMPTS + 1):
            frac = rng.random()
            dist = math.sqrt(lo ** 2 + frac * (hi ** 2 - lo ** 2))
            theta = rng.uniform(0.0, 2.0 * math.pi)
            nx = px + dist * math.cos(theta)
            ny = py + dist * math.sin(theta)

            if abs(nx) > usable or abs(ny) > usable:
                continue

            if any(math.hypot(o.x - nx, o.y - ny) < min_separation_cm
                   for o in placed):
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
                fallback = candidate
                break
            if fallback is None:
                fallback = candidate

        if fallback is not None:
            placed.append(fallback)

    return placed


def place_npc(
    world_size_cm: float,
    grid_z,
    grid_size: int,
    seed: int = 42,
    placed_trees=None,
    player_start=(0.0, 0.0),
    **kwargs,
) -> PlacedNPC | None:
    """
    One wanderer, for callers that only want one.  Kept as a thin wrapper over
    place_npcs() so there is exactly one implementation of "where may an NPC
    stand", not two that drift apart.
    """
    placed = place_npcs(world_size_cm, grid_z, grid_size, seed=seed,
                        placed_trees=placed_trees, player_start=player_start,
                        count=1, **kwargs)
    return placed[0] if placed else None
