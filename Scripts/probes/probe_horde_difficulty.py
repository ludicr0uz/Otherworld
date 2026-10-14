"""The Horde Survival level's difficulty (AOtherworldHordeDirector, placed by
forest_import/horde_director.py, its rule forest_generator/npc_horde.py):

  - the level holds one director, and its rule is npc_horde.py's (a level
    every 180 s; 4, 6, 8 ... monsters; a wendigo every four levels);
  - at level 1 the level's placed cast is cut to 4 zombies and no wendigo,
    and the single-player replacement of every one kept is switched off;
  - the level rises with play time (the step shortened), and the count follows:
    6 zombies at level 2, 9 and a wendigo at level 4, 16 and 2 at level 8,
    each new one out on the band, no nearer the player than its near edge;
  - a kill is replaced once, by the director (the dead one's own replacement
    shortened to fire inside the watch, so a second would be seen).

The level is held at 4, then 8, by its top (MaxLevel), so a slow headless
clock cannot run past the level a check is about.
"""

SYSTEMS = ('npc',)

LEVEL = "/Game/Maps/Lvl_Horde_Survival"  # the director is this level's alone

TIMEOUT = 240.0

import time

import unreal

from combat import health_vars as HV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat.respawn import RESPAWN_DELAY_VAR
from forest_generator import npc_horde as H
from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from forest_import.horde_director import (
    DIRECTOR_CLASS_PATH, WENDIGO_CLASS_PATH, ZOMBIE_CLASS_PATH)

WRITABLE = [(HEALTH_BP_PATH, RESPAWN_DELAY_VAR)]

STEP_S = 2.0          # the shortened step: a level every 2 s of game time
DELAY_S = 0.2         # a short level fills almost at once
REPLACE_S = 0.3       # the dead one's own replacement, were it still on
WAIT_WALL_S = 50.0    # wall seconds a count may take to arrive


def _living(p, cls):
    out = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), cls):
        h = p.component(a, HEALTH_CLASS_PATH)
        if h is not None and not p.get(h, "Dead"):
            out.append(a)
    return out


def _counts(p, d):
    return d.living_of(p.load_class(ZOMBIE_CLASS_PATH)), d.living_of(p.load_class(WENDIGO_CLASS_PATH))


def _bounded(cond):
    """A wait that ends on its own after WAIT_WALL_S, so a check can say what
    it found rather than the whole probe timing out."""
    until = time.monotonic() + WAIT_WALL_S
    return lambda: cond() or time.monotonic() > until


def probe(p):
    yield lambda: p.actor_of(DIRECTOR_CLASS_PATH) is not None and p.pawn() is not None
    d = p.actor_of(DIRECTOR_CLASS_PATH)
    player = p.pawn()
    zcls, wcls = p.load_class(ZOMBIE_CLASS_PATH), p.load_class(WENDIGO_CLASS_PATH)

    def nav():
        return unreal.NavigationSystemV1.project_point_to_navigation(
            p.world(), player.get_actor_location(), None, None,
            unreal.Vector(*NAV_REACHABLE_EXTENT_CM)) is not None
    if not nav():
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield nav

    times = (0.0, 179.0, 180.0, 359.0, 540.0, 1440.0, 99999.0)
    got = [d.level_at(t) for t in times]
    want = [H.horde_level(t) for t in times]
    p.check("the director's level is npc_horde.py's (a level every 180 s, at most 20)",
            got == want, f"{got} vs {want}")
    levels = range(1, H.HORDE_MAX_LEVEL + 1)
    got = [(d.zombies_at(n), d.wendigos_at(n)) for n in levels]
    want = [(H.horde_zombies(n), H.horde_wendigos(n)) for n in levels]
    p.check("...and so are its counts (4, 6, 8; 9 + 1 wendigo at 4, 16 + 2 at 8)",
            got == want, f"{got[:8]}")

    yield _bounded(lambda: d.get_editor_property("level") == 1 and _counts(p, d) == (4, 0))
    p.check("level 1: the placed cast is cut to 4 zombies and no wendigo",
            d.get_editor_property("level") == 1 and _counts(p, d) == (4, 0),
            f"level {d.get_editor_property('level')}, (zombies, wendigos) {_counts(p, d)}, "
            f"{d.get_editor_property('removed')} removed")
    kept = _living(p, zcls)
    off = [a for a in kept if p.get(p.component(a, HEALTH_CLASS_PATH), HV.RespawnClass) is None]
    p.check("...and every one kept has its single-player replacement switched off",
            kept and len(off) == len(kept), f"{len(off)} of {len(kept)}")

    d.set_editor_property("step_seconds", STEP_S)
    d.set_editor_property("delay", DELAY_S)
    d.set_editor_property("max_level", 2)
    d.restart()
    seen = {a.get_name() for a in _living(p, zcls) + _living(p, wcls)}
    near = []

    def watch_new():
        for a in _living(p, zcls) + _living(p, wcls):
            if a.get_name() not in seen:
                seen.add(a.get_name())
                near.append(a.get_actor_location().distance(player.get_actor_location()))
        return True

    for top, counts in ((2, (6, 0)), (4, (9, 1)), (8, (16, 2))):
        d.set_editor_property("max_level", top)
        yield _bounded(lambda: watch_new() and d.get_editor_property("level") == top
                       and _counts(p, d) == counts)
        p.check(f"level {top}: {counts[0]} zombies and {counts[1]} wendigo(s)",
                d.get_editor_property("level") == top and _counts(p, d) == counts,
                f"level {d.get_editor_property('level')}, {_counts(p, d)}, "
                f"{d.get_editor_property('spawned')} spawned")
    p.check("every new one came on the band, no nearer the player than its near edge",
            near and min(near) >= H.HORDE_SPAWN_MIN_CM * 0.95,
            f"{len(near)} new, nearest {min(near or [0]) / 100:.0f} m")

    victim = _living(p, zcls)[0]
    health = p.component(victim, HEALTH_CLASS_PATH)
    p.set(health, RESPAWN_DELAY_VAR, REPLACE_S)
    spawned, removed = d.get_editor_property("spawned"), d.get_editor_property("removed")
    health.take_hit(100000.0, victim.get_actor_location(), None, None)
    yield lambda: p.get(health, "Dead")
    yield _bounded(lambda: d.get_editor_property("spawned") > spawned)
    yield 3.0  # the replacement's 0.3 s ten times over, and three passes
    p.check("a kill is replaced once, by the director: the count stands, nothing extra",
            _counts(p, d) == (16, 2) and d.get_editor_property("spawned") == spawned + 1
            and d.get_editor_property("removed") == removed,
            f"{_counts(p, d)}, spawned +{d.get_editor_property('spawned') - spawned}, "
            f"removed +{d.get_editor_property('removed') - removed}")
