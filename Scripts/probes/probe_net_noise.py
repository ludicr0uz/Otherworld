"""Noise for several players: two players firing far apart each draw the
wanderers near them (task M28).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_noise.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_noise.py

The server picks the two calm zombies furthest apart, stops every other
wanderer's tree, and stands one player 25 m from each: past a zombie's sight
and touch, inside the all-round reach of the gun in that player's hand, and
further from the other zombie than that gun carries all round (the shots go
into the sky, so no one on the ground stands in a cone).

  - silent, neither zombie notices anyone;
  - both clients fire into the sky at once: each zombie turns Aggro by
    "sound", and its Target is the player beside it, who made the noise it
    heard;
  - the list held a fresh noise of each player at one moment (the one record
    it replaced held the louder, or the later);
  - the list's own rules, asked of the library on the server: a maker's
    quieter noise does not replace its fresh louder one, another maker's
    noise lands beside it, a listener hears the nearest that reaches it and
    none from out of reach.

Each client then finds its own list empty: a client's shot and footsteps
call the same node, and it writes nothing there.

Single player runs the same staging with its one player and one zombie.
combat/verify/noise.py and npc/verify.py hold the graphs.
"""

SYSTEMS = ('npc', 'net', 'combat')

import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import COMBAT
from combat.weapon_component.tick import FIRE_FORCED_VAR
from npc.paths import AGGRO_REASON_VAR, AGGRO_VAR, TARGET_VAR

# Two players each out of the other's gunshot need more room than 50 m.
LEVEL = "/Game/Maps/Lvl_Forest_200m"

WRITABLE = [(WEAPON_COMP_BP_PATH, FIRE_FORCED_VAR)]

TIMEOUT = 200.0       # wall seconds for the whole probe: three processes on one machine
WAIT = 40.0           # wall seconds: a headless frame can be slow
GAP_CM = 2500.0       # past a zombie's sight (20 m), inside any gun's reach (35 m up)
DRIFT_CM = 300.0      # a strolling zombie is followed once it has moved this far
PASSES = 1.6          # game seconds: three passes of the tree
MAX_ROUNDS = 12
HOLD = COMBAT.noise_hold_s
LOUD_CM, QUIET_CM = 50000.0, 100.0   # louder than any gun; quieter than a step
NOISE = unreal.OtherworldNoiseLibrary
ZERO = unreal.Vector(0.0, 0.0, 0.0)


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _controllers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def _name(a):
    return a.get_name() if a else "no one"


def _gap(a, b):
    return (a.get_actor_location() - b.get_actor_location()).length()


def _same(a, b):
    return bool(a) and bool(b) and a.get_name() == b.get_name()


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _fresh_makers(p):
    """The names of the makers whose noise a listener could still hear."""
    now = _now(p)
    return {_name(n.get_editor_property("maker")) for n in NOISE.noises_held(p.world())
            if now - n.get_editor_property("time") <= HOLD}


def _stage(p, pawns):
    """One calm zombie per pawn, the furthest apart, every other tree stopped,
    and ``follow()``, which keeps each pawn GAP_CM from its zombie. Returns
    ``(pairs, follow)``: pairs of (controller, body, pawn), or None."""
    calm = [c for c in _controllers(p) if not p.get(c, AGGRO_VAR)
            and "Zombie" in c.get_class().get_name()]
    p.check(f"{len(pawns)} calm zombie(s) are there to stage", len(calm) >= len(pawns),
            f"{len(calm)} calm")
    if len(calm) < len(pawns):
        return None, None
    if len(pawns) == 1:
        chosen = calm[:1]
    else:
        chosen = max(((a, b) for a in calm for b in calm if a != b),
                     key=lambda ab: _gap(ab[0].get_controlled_pawn(),
                                         ab[1].get_controlled_pawn()))
    for other in _controllers(p):
        if other not in chosen:
            other.get_editor_property("brain_component").stop_logic("probe")
    pairs = [(c, c.get_controlled_pawn(), pawn) for c, pawn in zip(chosen, pawns)]

    def follow(force=False):
        for _ctrl, body, pawn in pairs:
            if force or abs(_gap(body, pawn) - GAP_CM) > DRIFT_CM:
                here = body.get_actor_location()
                inward = unreal.Vector(-here.x, -here.y, 0.0)
                inward = inward.normal() if inward.length() > 1.0 else unreal.Vector(1.0, 0.0, 0.0)
                pawn.set_actor_location(unreal.Vector(
                    here.x + inward.x * GAP_CM, here.y + inward.y * GAP_CM, here.z + 100.0),
                    False, True)
        return False

    follow(force=True)
    return pairs, follow


def _reach(p, pawn):
    """(all round, down the cone) of the gun in ``pawn``'s hand, in cm."""
    held = p.get(p.component(pawn, WEAPON_COMP_CLASS_PATH), "Held")
    volume = float(p.get(held, "ShotVolume")) if held else 0.0
    return volume, volume * COMBAT.shot_noise_cone_range_scale


def _check_staging(p, pairs):
    for _ctrl, body, pawn in pairs:
        all_round, cone = _reach(p, pawn)
        others = [_gap(b, pawn) for _c, b, q in pairs if q != pawn]
        p.check(f"{_name(pawn)} holds a gun heard at {GAP_CM / 100:.0f} m, and stands "
                f"out of its all-round reach of the other zombie",
                all_round > GAP_CM + DRIFT_CM and all(g > all_round for g in others),
                f"heard {all_round / 100:.0f} m all round, {cone / 100:.0f} m down the cone; "
                f"the other zombie is {[round(g / 100) for g in others]} m off")


def _check_quiet(p, pairs):
    p.check("silent, no zombie notices the player 25 m from it",
            not any(p.get(c, AGGRO_VAR) for c, _b, _q in pairs),
            f"{[(p.get(c, AGGRO_VAR), p.get(c, AGGRO_REASON_VAR)) for c, _b, _q in pairs]}")


def _check_heard(p, pairs):
    for ctrl, body, pawn in pairs:
        p.check(f"{_name(body)} hears the player firing beside it",
                bool(p.get(ctrl, AGGRO_VAR)) and p.get(ctrl, AGGRO_REASON_VAR) == "sound",
                f"Aggro {p.get(ctrl, AGGRO_VAR)}, reason {p.get(ctrl, AGGRO_REASON_VAR)!r}")
        p.check("...and its Target is that player, who made the noise",
                _same(p.get(ctrl, TARGET_VAR), pawn),
                f"{_name(p.get(ctrl, TARGET_VAR))}, beside it {_name(pawn)}")


def _check_rules(p, first, second):
    """The list's own rules, asked of the library where the list is written."""
    world = p.world()
    at, other = first.get_actor_location(), second.get_actor_location()
    made, refused = NOISE.noises_made(world), NOISE.noises_refused(world)
    NOISE.make_noise(world, first, at, LOUD_CM, ZERO, 0.0, 1.0, HOLD)
    NOISE.make_noise(world, first, at, QUIET_CM, ZERO, 0.0, 1.0, HOLD)
    mine = [n for n in NOISE.noises_held(world) if _same(n.get_editor_property("maker"), first)]
    p.check("a maker's quieter noise does not replace its own fresh louder one "
            "(a footstep after a shot)",
            len(mine) == 1 and mine[0].get_editor_property("reach") == LOUD_CM
            and NOISE.noises_refused(world) == refused + 1,
            f"{[n.get_editor_property('reach') for n in mine]}; refused "
            f"{refused} -> {NOISE.noises_refused(world)}")
    NOISE.make_noise(world, second, other, QUIET_CM, ZERO, 0.0, 1.0, HOLD)
    fresh = _fresh_makers(p)
    p.check("...and another maker's quiet noise lands beside it, not under it",
            {_name(first), _name(second)} <= fresh and NOISE.noises_made(world) >= made + 2,
            f"{sorted(fresh)}; made {made} -> {NOISE.noises_made(world)}")
    near = NOISE.hear_noise(world, other, 1.0, HOLD)
    p.check("a listener hears the nearest noise that reaches it: beside the quiet "
            "one, that one, though the loud one reaches it too",
            near is not None and (near[1] - other).length() < 1.0,
            f"{near[1] if near else None}")
    apart = other + unreal.Vector(0.0, 0.0, QUIET_CM * 2.0)
    loud = NOISE.hear_noise(world, apart, 1.0, HOLD)
    p.check("...out of the quiet one's reach, the loud one, and who made it",
            loud is not None and (loud[1] - at).length() < 1.0 and _same(loud[0], first)
            if isinstance(first, unreal.Pawn) else loud is not None,
            f"{(_name(loud[0]), loud[1]) if loud else None}")
    nowhere = at + unreal.Vector(0.0, 0.0, LOUD_CM * 3.0)
    p.check("...and out of every reach, none",
            NOISE.hear_noise(world, nowhere, 1.0, HOLD) is None)
    p.check("a listener with half the hearing hears half as far",
            NOISE.hear_noise(world, at + unreal.Vector(0.0, 0.0, LOUD_CM * 0.75), 0.5, HOLD)
            is None
            and NOISE.hear_noise(world, at + unreal.Vector(0.0, 0.0, LOUD_CM * 0.75), 1.0, HOLD)
            is not None)


def _look_up(p):
    p.players()[0].set_control_rotation(unreal.Rotator(roll=0.0, pitch=70.0, yaw=0.0))


def _fire(p, stop):
    """Force the fire key, a press a round, into the sky until ``stop()``.
    Returns the rounds spent."""
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield from _await(lambda: p.get(wc, "Held") is not None)
    held = p.get(wc, "Held")
    if held is None:
        return 0
    # Up: nothing is hit, so no zombie is hurt into noticing. Held a moment
    # before the first press: the server's guard refuses a shot whose AimPoint
    # its own copy of this view does not look at yet.
    for _ in range(10):
        _look_up(p)
        yield 0.1
    rounds = 0
    while rounds < MAX_ROUNDS and not stop():
        _look_up(p)
        yield from _await(lambda: _now(p) > p.get(held, "NextFireTime") + 0.05, 5.0)
        was = int(p.get(held, "Loaded"))
        if was <= 0:
            break
        p.set(wc, FIRE_FORCED_VAR, True)
        yield from _await(lambda: int(p.get(held, "Loaded")) < was, 3.0)
        p.set(wc, FIRE_FORCED_VAR, False)
        rounds += int(p.get(held, "Loaded")) < was
        yield 0.05
    return rounds


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield from _await(lambda: len(_controllers(p)) > 1
                      and all(c.get_controlled_pawn() for c in p.players()))
    yield 1.0
    pawns = [c.get_controlled_pawn() for c in p.players()]
    p.check("two players are in the game", len(pawns) == 2, f"{len(pawns)}")
    pairs, follow = _stage(p, pawns) if len(pawns) == 2 else (None, None)
    if not pairs:
        p.post("heard", 0)
        p.post("done", 0)
        return
    yield from _await(lambda: all(
        p.get(p.component(q, WEAPON_COMP_CLASS_PATH), "Held") is not None for q in pawns), 10.0)
    yield lambda: follow() or True
    _check_staging(p, pairs)
    for _ in range(int(PASSES / 0.1)):
        follow()
        yield 0.1
    _check_quiet(p, pairs)
    made = NOISE.noises_made(p.world())

    both = [0]
    names = {_name(q) for q in pawns}

    def listening():
        follow()
        both[0] = max(both[0], len(_fresh_makers(p) & names))
        return all(p.get(c, AGGRO_VAR) for c, _b, _q in pairs)

    p.post("fire")
    yield from _await(listening, 2 * WAIT)
    _check_heard(p, pairs)
    p.check("the list held a fresh noise of each player at one moment: neither "
            "shot replaced the other", both[0] == 2,
            f"{both[0]} of the two players' noises at once; made {made} -> "
            f"{NOISE.noises_made(p.world())}; each player is "
            f"{[round(_gap(b, q) / 100) for _c, b, q in pairs]} m from its zombie")
    p.post("heard")
    yield from _await(lambda: p.posted("client 1", "fired") is not None
                      and p.posted("client 2", "fired") is not None, 30.0)
    p.check("both clients fired", bool(p.posted("client 1", "fired"))
            and bool(p.posted("client 2", "fired")),
            f"{p.posted('client 1', 'fired')}, {p.posted('client 2', 'fired')} round(s)")
    # The shots go stale first: a fresh shot would rightly refuse the quiet
    # noise the rules are asked with.
    yield from _await(lambda: not _fresh_makers(p), 10.0)
    _check_rules(p, pawns[0], pawns[1])
    p.post("done")
    yield 0.5


def probe_client(p):
    yield from _await(lambda: p.posted("server", "fire") is not None
                      or p.posted("server", "done") is not None, 3 * WAIT)
    rounds = yield from _fire(p, lambda: p.posted("server", "heard") is not None)
    p.post("fired", rounds)
    yield from _await(lambda: p.posted("server", "done") is not None, 2 * WAIT)
    world = p.world()
    NOISE.make_noise(world, p.pawn(), p.pawn().get_actor_location(), LOUD_CM, ZERO, 0.0, 1.0, HOLD)
    p.check(f"{p.where} fired {rounds} round(s), and its own list is empty: a noise "
            "is written on the server alone",
            rounds > 0 and NOISE.noises_made(world) == 0 and not NOISE.noises_held(world),
            f"{rounds} round(s); made {NOISE.noises_made(world)}, "
            f"held {len(NOISE.noises_held(world))}")


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    yield from _await(lambda: len(_controllers(p)) > 0 and p.pawn() is not None)
    yield 1.0
    pairs, follow = _stage(p, [p.pawn()])
    if not pairs:
        return
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield from _await(lambda: p.get(wc, "Held") is not None, 10.0)
    yield lambda: follow() or True
    _check_staging(p, pairs)
    for _ in range(int(PASSES / 0.1)):
        follow()
        yield 0.1
    _check_quiet(p, pairs)
    ctrl, body, pawn = pairs[0]
    rounds = yield from _fire(p, lambda: follow() or bool(p.get(ctrl, AGGRO_VAR)))
    yield from _await(lambda: bool(p.get(ctrl, AGGRO_VAR)), 5.0)
    p.check("standalone: the player fired", rounds > 0, f"{rounds} round(s)")
    _check_heard(p, pairs)
    yield from _await(lambda: not _fresh_makers(p), 10.0)
    _check_rules(p, pawn, body)
