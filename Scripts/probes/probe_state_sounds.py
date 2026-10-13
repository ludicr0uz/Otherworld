"""The sounds of a state, in the running game (Sound/sound_world.py).

A sound can't be heard in a headless game; this reads what would play it:

  - the player's and a wanderer's footstep component found the level's bushes
    at BeginPlay, and hold the rustle's takes;
  - walked in the open the player is not InBush, and walked from inside a bush
    they are (the rustle's stride is shortened to a centimetre, so a short walk
    asks the bushes many times);
  - a zombie set down in a bush is InBush as it walks out of it: the rustle is
    anyone's;
  - a tree with low leaves rustles too (forest_generator/low_leaves.py): the
    component found the level's saplings, the player walking up to one is not
    InBush until they reach its needles and is by the time those stop them, and
    walked beside the trunk of a tree that is not one (a fir, an island tree),
    under its crown, they are not;
  - at full health the heartbeat never comes due; badly hurt, it is played and
    next due HEARTBEAT_S on, and not before;
  - with the run key up the breath never comes due (no key can be injected, so
    the spent sprint itself is verify/sound_states.py's).
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('sound',)

import time

import unreal

from combat import footstep_vars as FV
from combat import health_vars as HV
from combat.paths import (
    FOOTSTEP_BP_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH)
from combat.weapon_component import vars as WV
from forest_generator.bush_placement import DEFAULT_BUSH_SPECS
from forest_generator.low_leaves import LOW_LEAF_TREE_SPECS
from forest_generator.tree_placement import DEFAULT_TREE_SPECS
from probes.probe_wendigo_quiet import _zombies
from Sound.sound_world import GRASS_RUSTLE, HEARTBEAT_S, LEAF_REACH_CM, LOW_HEALTH_FRACTION

WRITABLE = [(FOOTSTEP_BP_PATH, FV.RustleStrideCm), (HEALTH_BP_PATH, HV.Health)]

# A sapling's needles reach this far from its stem at scale 1, and its bounds
# this far at the corner (forest_generator/low_leaves.py; 40 x 37 cm).
NEEDLES_CM = 47.0
BOUNDS_CM = 55.0
CAPSULE_CM = 34.0
# Walked up to from here: clear of the largest sapling's needles (2.6 m).
APPROACH_CM = 420.0
APPROACH_S = 6.0

# Short walks from spots known to be on the ground, on a centimetre's stride:
# a 10 m walk up to a bush from a point set down beside it went 3 cm in 2000
# frames on the 1 km map (the start was not on the ground there).
STRIDE_CM = 1.0
WALK_CM = 25.0
WALL_S = 20.0
STAND_CM = 96.0        # the capsule's centre over a bush's foot (it is sunk 6 cm)
HIGH_TREE_STAND_CM = 150.0   # beside a trunk, clear of it, well under the crown
SETTLE_S = 0.5         # set down at a tree, before the walk is measured
MIN_FRAMES = 5         # a walk of fewer is a jolt, not a walk


def _feet(pawn):
    found = [c for c in pawn.get_components_by_class(unreal.ActorComponent)
             if c.get_class().get_name().startswith("BP_FootstepComponent")]
    return found[0] if found else None


def _package(mesh_path):
    return mesh_path.split(".")[0]


def _points(comps):
    """Where every instance of ``comps`` stands (world space)."""
    points = []
    for comp in comps:
        for i in range(comp.get_instance_count()):
            points.append(comp.get_instance_transform(i, True).translation)
    return points


def _high_tree_points(player):
    """Where the level's trees with no low leaves stand: every cell of them,
    found in the level itself (the footstep component does not hold them)."""
    names = {_package(s.mesh_path).rsplit("/", 1)[-1] for s in DEFAULT_TREE_SPECS
             if s not in LOW_LEAF_TREE_SPECS}
    cells = [a.get_component_by_class(unreal.InstancedStaticMeshComponent)
             for a in unreal.GameplayStatics.get_all_actors_of_class(player, unreal.Actor)]
    return _points(c for c in cells
                   if c and c.static_mesh and c.static_mesh.get_name() in names)


def _walk(p, player, feet, seen):
    """Walk the player forward from where they stand until they have gone
    WALK_CM or WALL_S is up, noting InBush after each frame in ``seen``."""
    start = player.get_actor_location()
    end = time.time() + WALL_S
    while time.time() < end:
        player.add_movement_input(player.get_actor_forward_vector(), 1.0)
        yield 0.0
        seen.append(p.get(feet, FV.InBush))
        if (player.get_actor_location() - start).length() >= WALK_CM:
            return


def probe(p):
    yield 0.5
    player = p.pawn()
    feet = _feet(player)
    p.check("the player wears a footstep component", feet is not None)
    if feet is None:
        return
    meshes = {_package(s.mesh_path) for s in DEFAULT_BUSH_SPECS}
    bushes = list(p.get(feet, FV.Bushes))
    p.check("it found the level's bushes at BeginPlay, and nothing that is not one",
            bool(bushes) and all(
                _package(c.static_mesh.get_path_name()) in meshes for c in bushes),
            f"{len(bushes)} component(s)")
    low = {_package(s.mesh_path).rsplit("/", 1)[-1] for s in LOW_LEAF_TREE_SPECS}
    saplings = list(p.get(feet, FV.LeafTrees))
    p.check("...and its trees with low leaves, and no other tree",
            bool(saplings) and all(c.static_mesh.get_name() in low for c in saplings),
            f"{len(saplings)} component(s)")
    got = [s.get_name() for s in p.get(feet, FV.RustleSounds) if s]
    p.check("...and holds the rustle's takes", got == list(GRASS_RUSTLE.names), str(got))
    yield lambda: _zombies(p)
    theirs = _feet(_zombies(p)[0].get_controlled_pawn())
    p.check("a wanderer's does too: its bushes and its takes",
            theirs is not None and len(p.get(theirs, FV.Bushes)) == len(bushes)
            and len(p.get(theirs, FV.LeafTrees)) == len(saplings)
            and [s.get_name() for s in p.get(theirs, FV.RustleSounds) if s]
            == list(GRASS_RUSTLE.names))
    if not bushes:
        return

    # --- a walk in the open, and one from inside a bush --------------------------
    # The player starts clear of every bush (bush_placement's spawn clearing).
    points = _points(bushes + saplings)
    home = player.get_actor_location()
    bush = min(_points(bushes), key=lambda b: (b - home).length())
    near = min(points, key=lambda b: (b - home).length())
    p.set(feet, FV.RustleStrideCm, STRIDE_CM)
    seen = []
    yield from _walk(p, player, feet, seen)
    gone = (player.get_actor_location() - home).length()
    p.check("walked in the open, the player is never InBush",
            gone > 2 * STRIDE_CM and not any(seen),
            f"{sum(seen)} of {len(seen)} frames, {gone:.1f} cm walked, the nearest bush "
            f"or sapling {(near - home).length():.0f} cm off")
    player.set_actor_location(bush + unreal.Vector(0.0, 0.0, STAND_CM), False, True)
    at = player.get_actor_location()
    seen = []
    yield from _walk(p, player, feet, seen)
    gone = (player.get_actor_location() - at).length()
    p.check("walked from inside a bush, the player is InBush",
            any(seen), f"{sum(seen)} of {len(seen)} frames, {gone:.1f} cm walked")

    # --- a tree with low leaves, and one without --------------------------------
    # Up to the sapling furthest from everything else that rustles, from open
    # ground: the rustle starts where the needles do, and they stop the walker.
    trees = [(c.get_instance_transform(i, True)) for c in saplings
             for i in range(c.get_instance_count())]
    tree = max(trees, key=lambda t: min(
        [(t.translation - b).length() for b in points if (t.translation - b).length() > 1.0]))
    stem, scale = tree.translation, tree.scale3d.x
    # From the side away from the nearest other tree: nothing in the way.
    others = [t for t in _high_tree_points(player) + _points(saplings)
              if (t - stem).length() > 1.0]
    away = stem - min(others, key=lambda t: (t - stem).length())
    flat = (away.x ** 2 + away.y ** 2) ** 0.5
    side = unreal.Vector(away.x / flat, away.y / flat, 0.0)
    player.set_actor_location(stem + side * APPROACH_CM + unreal.Vector(0.0, 0.0, STAND_CM),
                              False, True)
    yield SETTLE_S

    def off():
        there = player.get_actor_location() - stem
        return (there.x ** 2 + there.y ** 2) ** 0.5
    walk, end = [], time.time() + APPROACH_S
    while time.time() < end:
        player.add_movement_input(side * -1.0, 1.0)
        yield 0.0
        walk.append((off(), p.get(feet, FV.InBush)))
    # InBush is the last asking's answer: the first of this walk is a stride in.
    start = walk[0][0]
    walk = [(d, inside) for d, inside in walk if d < start - 3 * STRIDE_CM]
    first = next((d for d, inside in walk if inside), None)
    # No further out than the bounds' corner and the reach; no nearer than the
    # needles a walker's half-width stops at, less the reach.
    far = BOUNDS_CM * scale + LEAF_REACH_CM + 2 * STRIDE_CM + 15.0
    p.check("walking up to a tree with low leaves, the player is not InBush on the way",
            len(walk) >= MIN_FRAMES and start > far
            and not any(inside for d, inside in walk if d > far),
            f"from {start:.0f} cm off the stem, the rustle no further out than {far:.0f} cm "
            f"(scale {scale:.2f})")
    p.check("...and is at its needles: the rustle starts as they reach them, and they are "
            "still InBush where the needles stop them",
            first is not None and first <= far and walk[-1][1]
            and walk[-1][0] <= NEEDLES_CM * scale + CAPSULE_CM,
            f"first InBush {first and round(first)} cm from the stem, stopped "
            f"{walk[-1][0]:.0f} cm from it; the needles reach {NEEDLES_CM * scale:.0f} cm")
    # Beside the trunk of the tree with no low leaves that is furthest from
    # everything that rustles: under a crown, and not InBush.
    high = max(_high_tree_points(player),
               key=lambda t: min((t - b).length() for b in points))
    clear = min((high - b).length() for b in points)
    seen = []
    player.set_actor_location(
        high + player.get_actor_forward_vector() * HIGH_TREE_STAND_CM
        + unreal.Vector(0.0, 0.0, STAND_CM), False, True)
    yield SETTLE_S
    at = player.get_actor_location()
    yield from _walk(p, player, feet, seen)
    gone = (player.get_actor_location() - at).length()
    p.check("...and walked under a tree whose leaves are overhead, they are not",
            len(seen) >= MIN_FRAMES and gone > 2 * STRIDE_CM and not any(seen)
            and clear > 2 * HIGH_TREE_STAND_CM,
            f"{sum(seen)} of {len(seen)} frames, {gone:.1f} cm walked, the nearest bush "
            f"or sapling {clear:.0f} cm off")

    # --- a zombie in a bush: the rustle is anyone's ------------------------------
    # Set down in the bush with the player in sight, it walks out of it by itself.
    zombie = _zombies(p)[0].get_controlled_pawn()
    p.set(theirs, FV.RustleStrideCm, STRIDE_CM)
    player.set_actor_location(bush + unreal.Vector(600.0, 0.0, STAND_CM), False, True)
    zombie.set_actor_location(bush + unreal.Vector(0.0, 0.0, STAND_CM), False, True)
    at, seen, end = zombie.get_actor_location(), [], time.time() + WALL_S
    while time.time() < end and (zombie.get_actor_location() - at).length() < WALK_CM:
        yield 0.0
        seen.append(p.get(theirs, FV.InBush))
    gone = (zombie.get_actor_location() - at).length()
    p.check("a zombie walking out of a bush is InBush: it rustles as the player does",
            any(seen), f"{sum(seen)} of {len(seen)} frames, {gone:.1f} cm walked")

    # --- the heartbeat -----------------------------------------------------------
    health = p.component(player, HEALTH_CLASS_PATH)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("at full health the heartbeat has never come due, and with the run key up "
            "neither has the breath",
            p.get(health, HV.HeartbeatNextTime) == 0.0 and p.get(wc, WV.BreathNextTime) == 0.0,
            f"{p.get(health, HV.HeartbeatNextTime)}, {p.get(wc, WV.BreathNextTime)}")
    p.set(health, HV.Health, p.get(health, HV.MaxHealth) * LOW_HEALTH_FRACTION * 0.5)
    yield lambda: p.get(health, HV.HeartbeatNextTime) > 0.0
    due = p.get(health, HV.HeartbeatNextTime)
    now = unreal.GameplayStatics.get_time_seconds(player)
    p.check(f"badly hurt, it is played: next due {HEARTBEAT_S:g} s on",
            abs(due - now - HEARTBEAT_S) < 0.5, f"due {due:.2f}, now {now:.2f}")
    yield 0.3
    p.check("...and not again before then",
            p.get(health, HV.HeartbeatNextTime) == due)
    p.check("the player holds the heartbeat's take",
            len([s for s in p.get(health, HV.HeartbeatSounds) if s]) == 1)
