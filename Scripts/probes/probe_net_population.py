"""Wanderer population by mode: on a server the count follows the players
(task M29); single player keeps the level's count.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_population.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_population.py

The budget is C++ (Source/Otherworld/Public/OtherworldPopulation.h); each
wanderer's controller registers it (npc/population.py). The server:

  - at the table's numbers, on this level, the budget leaves the level's
    pack as it is: nothing is removed, nothing added;
  - the two players stood far apart and the range cut to nothing, every
    wanderer is out of range of everyone and is removed;
  - then a small budget (2 zombies near a player, 3 alive, a 35 m range, a
    15-25 m band, a 1 s wait): zombies come to each player, and the count
    stops at the server's cap of 3;
  - the cap raised, each player has 2 within range, 4 alive; none appeared
    nearer any player than the band's near edge, and none stands where a
    player looks at it with a clear line;
  - player 2 brought beside player 1, the two they left behind go and no
    more come: 2 alive, a pair of players share one budget's worth;
  - player 2 sent back, 2 come to them again.

Every wanderer's tree is stopped as it appears, so none walks or bites and
a count is of where the budget put them. Each client finds no budget of its
own (the list is the server's) and sees the zombies near it.

Single player: no budget, nothing registered, and the level's count stands.
"""

SYSTEMS = ('npc', 'net')

import math
import time

import unreal

# Two players out of each other's range need more room than 50 m.
LEVEL = "/Game/Maps/Lvl_Forest_200m"

TIMEOUT = 240.0
WAIT = 45.0            # wall seconds: a headless frame can be slow
PER_PLAYER, CAP = 2, 3
RANGE_CM = 3500.0
BAND_CM = (1500.0, 2500.0)
DELAY_S = 1.0
SEEN_DEG = 70.0        # the budget refuses a point within 75 degrees of a player's look
APART_CM = 2.0 * RANGE_CM + 1500.0    # neither player's range reaches the other's
POP = unreal.OtherworldPopulationLibrary


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _controllers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def _bodies(p, kind=""):
    """The wanderers of this world, by their pawns (a client has no controllers)."""
    pawns = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Pawn)
    return [b for b in pawns if "Wanderer" in b.get_class().get_name()
            and kind in b.get_class().get_name()]


def _gap(a, b):
    return (a.get_actor_location() - b.get_actor_location()).length()


def _near(p, pawn, kind="Zombie"):
    return [b for b in _bodies(p, kind) if _gap(b, pawn) <= RANGE_CM]


def _still(p):
    """Stop every wanderer's tree, the new ones' too."""
    for ctrl in _controllers(p):
        brain = ctrl.get_editor_property("brain_component")
        if brain is not None and brain.is_running():
            brain.stop_logic("probe")
    return False


def _sees(p, pawn, body):
    """Does ``pawn`` look at ``body`` with nothing between? The budget's own
    test, asked again from here: within SEEN_DEG of where the player looks,
    and a Visibility trace from their eyes to its head that hits nothing."""
    eye = pawn.get_actor_location() + unreal.Vector(
        0.0, 0.0, pawn.get_editor_property("base_eye_height"))
    head = body.get_actor_location() + unreal.Vector(0.0, 0.0, 60.0)
    look = pawn.get_controller().get_control_rotation().get_forward_vector()
    if (head - eye).normal().dot(look) < math.cos(math.radians(SEEN_DEG)):
        return False
    hit = unreal.SystemLibrary.line_trace_single(
        p.world(), eye, head, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [pawn, body],
        unreal.DrawDebugTrace.NONE, True)
    return hit is None


def _stand(pawn, spot):
    pawn.set_actor_location(unreal.Vector(spot.x, spot.y, spot.z + 100.0), False, True)


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    world = p.world()
    yield from _await(lambda: len(_controllers(p)) > 1 and len(p.players()) == 2
                      and all(c.get_controlled_pawn() for c in p.players()))
    yield 1.0
    pawns = [c.get_controlled_pawn() for c in p.players()]
    p.check("two players are in the game, and the count is a budget here",
            len(pawns) == 2 and POP.population_is_budget(world), f"{len(pawns)}")
    zombies = _bodies(p, "Zombie")
    if len(pawns) != 2 or not zombies:
        p.post("full", 0)
        p.post("done", 0)
        return
    one, two = pawns
    zombie, base = zombies[0].get_class(), unreal.Pawn
    placed = len(_bodies(p))
    p.check("every wanderer the level placed is registered with the budget",
            POP.population_count(world, base) == placed and placed > 0,
            f"{POP.population_count(world, base)} of {placed}")
    yield 4.0
    p.check("at the table's numbers the budget leaves this level's pack as it is",
            POP.population_spawned(world) == 0 and POP.population_removed(world) == 0
            and len(_bodies(p)) == placed,
            f"spawned {POP.population_spawned(world)}, removed {POP.population_removed(world)}, "
            f"{len(_bodies(p))} of {placed}")

    # The two wanderers furthest apart mark the two spots: ground that is there.
    _still(p)
    here, there = max(((a, b) for a in _bodies(p) for b in _bodies(p)),
                      key=lambda ab: _gap(ab[0], ab[1]))
    spot_a, spot_b = here.get_actor_location(), there.get_actor_location()
    p.check(f"the level has two spots {APART_CM / 100:.0f} m apart to stand the players on",
            (spot_a - spot_b).length() >= APART_CM, f"{(spot_a - spot_b).length() / 100:.0f} m")

    def hold(b_at):
        _still(p)
        if (one.get_actor_location() - spot_a).length() > 300.0:
            _stand(one, spot_a)
        if (two.get_actor_location() - b_at).length() > 300.0:
            _stand(two, b_at)
        return False

    def stray():
        return [b for b in _bodies(p) if min(_gap(b, one), _gap(b, two)) > RANGE_CM + 100.0]

    def count():
        return (len(_near(p, one)), len(_near(p, two)), len(_bodies(p, "Zombie")))

    # --- no player within range: removed ----------------------------------------
    # A range of 10 cm and a budget of none: every wanderer is out of range of
    # everyone, the pair the spots were read from included, so what stands
    # afterwards is what the budget put there.
    kinds = {b.get_class() for b in _bodies(p)}
    for kind in kinds:
        POP.set_population_budget(world, kind, 0, 0, 10.0, BAND_CM[0], BAND_CM[1], DELAY_S)
    yield from _await(lambda: hold(spot_b) or not _bodies(p))
    p.check(f"standing {_gap(one, two) / 100:.0f} m apart with no wanderer in range of a "
            f"player: all {placed} are removed",
            not _bodies(p) and POP.population_removed(world) == placed
            and POP.population_count(world, base) == 0,
            f"{len(_bodies(p))} left; removed {POP.population_removed(world)}")

    # --- far apart, under the server's cap -----------------------------------
    for kind in kinds:
        mine = kind == zombie
        POP.set_population_budget(world, kind, PER_PLAYER if mine else 0, CAP if mine else 0,
                                  RANGE_CM, BAND_CM[0], BAND_CM[1], DELAY_S)
    yield from _await(lambda: hold(spot_b) or count()[2] >= CAP)
    for _ in range(30):         # ...and it stays there
        hold(spot_b)
        yield 0.1
    a, b, alive = count()
    p.check(f"given a budget, zombies come to each player, {RANGE_CM / 100:.0f} m round "
            f"them, and the count stops at the server's cap of {CAP}",
            alive == CAP and a >= 1 and b >= 1 and a + b == CAP and not stray()
            and POP.population_count(world, zombie) == CAP
            and POP.population_spawned(world) == CAP,
            f"{a} near player 1, {b} near player 2, {alive} alive; "
            f"spawned {POP.population_spawned(world)}")

    # --- the cap raised: a budget's worth each --------------------------------
    POP.set_population_budget(world, zombie, PER_PLAYER, 10, RANGE_CM, BAND_CM[0], BAND_CM[1],
                              DELAY_S)
    full = (PER_PLAYER, PER_PLAYER, 2 * PER_PLAYER)
    yield from _await(lambda: hold(spot_b) or count() == full)
    for _ in range(30):
        hold(spot_b)
        yield 0.1
    p.check(f"the cap raised, each player has {PER_PLAYER} zombies within range and no more",
            count() == full, f"{count()} (near 1, near 2, alive)")
    nearest = POP.population_nearest_spawn(world)
    p.check(f"none appeared nearer any player than the band's near edge "
            f"({BAND_CM[0] / 100:.0f} m): out of sight is also out of reach",
            POP.population_spawned(world) > 0 and nearest >= BAND_CM[0],
            f"nearest {nearest / 100:.1f} m over {POP.population_spawned(world)} spawn(s)")
    seen = [(q.get_name(), b.get_name()) for q in pawns for b in _bodies(p) if _sees(p, q, b)]
    p.check("...and each stands where no player is looking at it with a clear line: "
            "behind them, or behind something",
            not seen, f"{seen}; {len(_bodies(p))} standing")
    p.post("full")
    yield from _await(lambda: hold(spot_b) or all(
        p.posted(f"client {n}", "seen") is not None for n in (1, 2)), 30.0)

    # --- player 2 walks over to player 1 ---------------------------------------
    beside = unreal.Vector(spot_a.x + 300.0, spot_a.y, spot_a.z)
    removed = POP.population_removed(world)
    together = (PER_PLAYER, PER_PLAYER, PER_PLAYER)
    yield from _await(lambda: hold(beside) or (count() == together and not stray()))
    for _ in range(30):
        hold(beside)
        yield 0.1
    p.check("player 2 beside player 1: the zombies they left are removed, and two "
            "players in one place share one budget's worth",
            count() == together and POP.population_removed(world) >= removed + PER_PLAYER,
            f"{count()} (near 1, near 2, alive); removed {removed} -> "
            f"{POP.population_removed(world)}")

    # --- and back ----------------------------------------------------------------
    yield from _await(lambda: hold(spot_b) or count() == full)
    p.check(f"player 2 sent back: {PER_PLAYER} come to them again",
            count() == full, f"{count()} (near 1, near 2, alive)")
    p.post("done")
    yield 0.5


def probe_client(p):
    yield from _await(lambda: p.posted("server", "full") is not None, 4 * WAIT)
    if p.posted("server", "full") == 0 or p.posted("server", "full") is None:
        p.post("seen", 0)
        return
    world = p.world()
    yield from _await(lambda: p.pawn() is not None
                      and len(_near(p, p.pawn())) == PER_PLAYER, 20.0)
    seen = len(_near(p, p.pawn())) if p.pawn() else -1
    p.check(f"{p.where} sees the {PER_PLAYER} zombies the budget put near it, and has "
            "no budget of its own",
            seen == PER_PLAYER and not POP.population_is_budget(world)
            and POP.population_count(world, unreal.Pawn) == 0,
            f"{seen} within {RANGE_CM / 100:.0f} m; "
            f"registered here {POP.population_count(world, unreal.Pawn)}")
    p.post("seen", seen)
    yield from _await(lambda: p.posted("server", "done") is not None, 3 * WAIT)


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    world = p.world()
    yield from _await(lambda: len(_controllers(p)) > 0 and p.pawn() is not None)
    yield 1.0
    placed = len(_bodies(p))
    # A budget this small would empty a server's level; here it is not even kept.
    for kind in {b.get_class() for b in _bodies(p)}:
        POP.set_population_budget(world, kind, 0, 0, 100.0, 100.0, 200.0, 0.1)
    yield 4.0
    p.check("standalone: the count is not a budget, and no wanderer is registered",
            not POP.population_is_budget(world) and POP.population_count(world, unreal.Pawn) == 0,
            f"budget {POP.population_is_budget(world)}, "
            f"registered {POP.population_count(world, unreal.Pawn)}")
    p.check(f"standalone: the level's {placed} wanderers stand, none removed, none added",
            placed > 0 and len(_bodies(p)) == placed and POP.population_spawned(world) == 0
            and POP.population_removed(world) == 0,
            f"{len(_bodies(p))} of {placed}; spawned {POP.population_spawned(world)}, "
            f"removed {POP.population_removed(world)}")
